import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv
from llama_parse import LlamaParse
from neo4j import GraphDatabase


DEFAULT_HF_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_VECTOR_INDEX = "omniplant_document_chunks"
DEFAULT_NODE_LABEL = "DocumentChunk"
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 150


def load_environment() -> None:
    """Load backend environment variables from backend/.env."""
    backend_root = Path(__file__).resolve().parent
    load_dotenv(backend_root / ".env")


def get_required_env(name: str) -> str:
    """Return a required environment variable or fail fast."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_hugging_face_token() -> str:
    """Return the Hugging Face token from the first supported environment variable."""
    for candidate in ("HUGGINGFACE_API_TOKEN", "HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HUGGINGFACEHUB_ACCESS_TOKEN"):
        token = os.getenv(candidate)
        if token:
            return token

    raise RuntimeError(
        "Missing Hugging Face token. Set HUGGINGFACE_API_TOKEN, HF_TOKEN, HUGGINGFACEHUB_API_TOKEN, or HUGGINGFACEHUB_ACCESS_TOKEN."
    )


def collect_pdf_files(input_path: Path) -> list[Path]:
    """Return the PDFs found at a file path or within a directory tree."""
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            raise ValueError(f"Input file must be a PDF: {input_path}")
        return [input_path]

    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    pdf_files = sorted(path for path in input_path.rglob("*.pdf") if path.is_file())
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found under: {input_path}")

    return pdf_files


def create_parser() -> LlamaParse:
    """Create a configured LlamaParse client."""
    api_key = get_required_env("LLAMA_CLOUD_API_KEY")
    return LlamaParse(api_key=api_key, result_type="markdown")


def parse_pdf(parser: LlamaParse, pdf_path: Path):
    """Parse a single PDF file into LlamaParse documents."""
    documents = parser.load_data(str(pdf_path))
    if not documents:
        raise RuntimeError(f"LlamaParse returned no documents for {pdf_path}")
    return documents


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    """Split normalized text into overlapping chunks for embedding."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(cleaned)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        if end < text_length:
            split_at = cleaned.rfind(" ", start, end)
            if split_at > start + 200:
                end = split_at

        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = max(end - overlap, 0)
        while start < text_length and cleaned[start] == " ":
            start += 1

    return chunks


def _pool_embedding_response(payload):
    """Convert Hugging Face feature-extraction output into one flat vector."""
    if not payload:
        raise RuntimeError("Hugging Face returned an empty embedding payload")

    first_item = payload[0]
    if isinstance(first_item, (int, float)):
        return [float(value) for value in payload]

    if first_item and isinstance(first_item[0], (int, float)):
        return [float(value) for value in first_item]

    token_vectors = payload
    vector_length = len(token_vectors[0])
    pooled_vector = [0.0] * vector_length

    for token_vector in token_vectors:
        for index, value in enumerate(token_vector):
            pooled_vector[index] += float(value)

    token_count = max(len(token_vectors), 1)
    return [value / token_count for value in pooled_vector]


def embed_texts(texts: list[str], model_name: str, token: str) -> list[list[float]]:
    """Request embeddings for each chunk from the Hugging Face inference API."""
    if not texts:
        return []

    endpoint = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_name}"
    headers = {"Authorization": f"Bearer {token}"}
    embeddings: list[list[float]] = []

    for text in texts:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"inputs": text, "options": {"wait_for_model": True}},
            timeout=120,
        )
        response.raise_for_status()
        embeddings.append(_pool_embedding_response(response.json()))

    return embeddings


def build_chunk_records(pdf_path: Path, documents, model_name: str, token: str) -> list[dict]:
    """Turn parsed documents into Neo4j-ready chunk payloads."""
    records: list[dict] = []

    for document_index, document in enumerate(documents):
        text = getattr(document, "text", "") or ""
        metadata = getattr(document, "metadata", {}) or {}
        text_chunks = chunk_text(text)
        embeddings = embed_texts(text_chunks, model_name=model_name, token=token)

        for chunk_index, (chunk_text_value, embedding) in enumerate(zip(text_chunks, embeddings)):
            fingerprint = hashlib.sha1(
                f"{pdf_path.as_posix()}::{document_index}::{chunk_index}::{chunk_text_value}".encode("utf-8")
            ).hexdigest()
            records.append(
                {
                    "chunk_id": fingerprint,
                    "source_file": pdf_path.name,
                    "source_path": pdf_path.as_posix(),
                    "document_index": document_index,
                    "chunk_index": chunk_index,
                    "page_number": metadata.get("page_number") or metadata.get("page") or metadata.get("page_label"),
                    "title": metadata.get("file_name") or metadata.get("title") or pdf_path.stem,
                    "text": chunk_text_value,
                    "embedding": embedding,
                }
            )

    return records


def ensure_vector_index(driver, index_name: str, label: str, dimension: int) -> None:
    """Create the Neo4j vector index if it does not already exist."""
    safe_index_name = index_name.replace("`", "")
    query = f"""
    CREATE VECTOR INDEX `{safe_index_name}` IF NOT EXISTS
    FOR (n:{label}) ON (n.embedding)
    OPTIONS {{
      indexConfig: {{
        `vector.dimensions`: {dimension},
        `vector.similarity_function`: 'cosine'
      }}
    }}
    """
    with driver.session() as session:
        session.run(query)


def upsert_chunk_records(driver, records: list[dict], label: str) -> None:
    """Insert or update chunk nodes in Neo4j."""
    if not records:
        return

    merge_query = f"""
    MERGE (chunk:{label} {{chunk_id: $chunk_id}})
    SET chunk.source_file = $source_file,
        chunk.source_path = $source_path,
        chunk.document_index = $document_index,
        chunk.chunk_index = $chunk_index,
        chunk.page_number = $page_number,
        chunk.title = $title,
        chunk.text = $text,
        chunk.embedding = $embedding,
        chunk.updated_at = datetime()
    """

    with driver.session() as session:
        for record in records:
            session.run(merge_query, **record)


def ingest_pdf_file(driver, parser: LlamaParse, pdf_path: Path, model_name: str, token: str, label: str, index_name: str) -> int:
    """Parse, embed, and store one PDF file."""
    documents = parse_pdf(parser, pdf_path)
    records = build_chunk_records(pdf_path, documents, model_name=model_name, token=token)

    if not records:
        print(f"Skipped {pdf_path.name}: no embeddable chunks were produced.")
        return 0

    ensure_vector_index(driver, index_name, label, len(records[0]["embedding"]))
    upsert_chunk_records(driver, records, label)
    print(f"Ingested {len(records)} chunks from {pdf_path.name}")
    return len(records)


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the ingestion job."""
    parser = argparse.ArgumentParser(
        description="Parse synthetic PDFs with LlamaParse, create Hugging Face embeddings, and push chunks into Neo4j."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=Path(__file__).resolve().parent,
        type=Path,
        help="PDF file or directory to ingest. Defaults to the backend folder.",
    )
    parser.add_argument(
        "--hf-model",
        default=os.getenv("HUGGINGFACE_EMBEDDING_MODEL", DEFAULT_HF_MODEL),
        help="Hugging Face inference model to use for feature extraction.",
    )
    parser.add_argument(
        "--vector-index",
        default=os.getenv("NEO4J_VECTOR_INDEX", DEFAULT_VECTOR_INDEX),
        help="Neo4j vector index name to create or reuse.",
    )
    parser.add_argument(
        "--node-label",
        default=os.getenv("NEO4J_VECTOR_LABEL", DEFAULT_NODE_LABEL),
        help="Neo4j node label used to store chunk vectors.",
    )
    return parser


def main() -> None:
    """Run the end-to-end ingestion flow."""
    load_environment()
    args = build_argument_parser().parse_args()

    pdf_files = collect_pdf_files(args.path)
    hf_token = get_hugging_face_token()
    parser = create_parser()

    neo4j_uri = get_required_env("NEO4J_URI")
    neo4j_username = get_required_env("NEO4J_USERNAME")
    neo4j_password = get_required_env("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password))

    total_chunks = 0
    try:
        with driver.session() as session:
            session.run("RETURN 1")

        for pdf_path in pdf_files:
            total_chunks += ingest_pdf_file(
                driver,
                parser,
                pdf_path,
                model_name=args.hf_model,
                token=hf_token,
                label=args.node_label,
                index_name=args.vector_index,
            )

        print(json.dumps({"files": len(pdf_files), "chunks": total_chunks, "vector_index": args.vector_index}))
    finally:
        driver.close()


def ingest_pdf_path(
    pdf_path: Path,
    *,
    hf_model: str | None = None,
    vector_index: str | None = None,
    node_label: str | None = None,
) -> int:
    """Ingest a single PDF path from external callers such as API routes."""
    load_environment()

    hf_token = get_hugging_face_token()
    parser = create_parser()

    neo4j_uri = get_required_env("NEO4J_URI")
    neo4j_username = get_required_env("NEO4J_USERNAME")
    neo4j_password = get_required_env("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password))
    try:
        return ingest_pdf_file(
            driver,
            parser,
            pdf_path,
            model_name=hf_model or os.getenv("HUGGINGFACE_EMBEDDING_MODEL", DEFAULT_HF_MODEL),
            token=hf_token,
            label=node_label or os.getenv("NEO4J_VECTOR_LABEL", DEFAULT_NODE_LABEL),
            index_name=vector_index or os.getenv("NEO4J_VECTOR_INDEX", DEFAULT_VECTOR_INDEX),
        )
    finally:
        driver.close()


def ingest_uploaded_pdf(
    file_bytes: bytes,
    filename: str,
    *,
    hf_model: str | None = None,
    vector_index: str | None = None,
    node_label: str | None = None,
) -> int:
    """Persist an uploaded PDF to a temp file and ingest it."""
    suffix = Path(filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(file_bytes)
        temp_path = Path(temp_file.name)

    try:
        return ingest_pdf_path(
            temp_path,
            hf_model=hf_model,
            vector_index=vector_index,
            node_label=node_label,
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()


if __name__ == "__main__":
    main()