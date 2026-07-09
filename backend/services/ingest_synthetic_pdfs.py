import json
import os
import tempfile

import dotenv
import google.generativeai as genai
import requests
import re
from connection.llama_parse import parser
from connection.neo_4j import driver


dotenv.load_dotenv()

HEADERS = {
    "Authorization": f"Bearer {os.getenv('HUGGINGFACEHUB_ACCESS_TOKEN')}",
    "Content-Type": "application/json",
}

HF_API_URL = "https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en"
BATCH_SIZE = 16

ALLOWED_RELATIONS = {
    "HAS_PART",
    "CONNECTED_TO",
    "GOVERNS",
    "LOCATED_IN",
    "MONITORS",
    "REQUIRES",
    "USES",
    "CAUSES",
    "INDICATES",
}


# Gemini is used only for graph extraction, not for embeddings.
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")


def build_extraction_prompt(text: str) -> str:
    """Build the graph extraction prompt for Gemini."""
    return f"""
Extract entities and relationships from this industrial manual.
allow only this relationship
ALLOWED_RELATIONS = {
    "HAS_PART",
    "CONNECTED_TO",
    "GOVERNS",
    "LOCATED_IN",
    "MONITORS",
    "REQUIRES",
    "USES",
    "CAUSES",
    "INDICATES",
}

Return ONLY valid JSON.

Format:

{{
  "entities":[
    {{
      "name":"Pump-101",
      "label":"Equipment"
    }}
  ],
  "relationships":[
    {{
      "source":"Pump-101",
      "type":"CONNECTED_TO",
      "target":"Valve-10"
    }}
  ]
}}

Text:
{text}
"""


def extract_graph(text: str) -> dict:
    """Extract entities and relationships from chunk text."""
    try:
        response = model.generate_content(build_extraction_prompt(text))
        if(response.text is None):
            print("Gemini returned no text.")
            return {"entities": [], "relationships": []}
        # print(f"Graph Extraction Response: {response.text}")  # Safe preview
        text = response.text.strip()

        # Remove ```json ... ```
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)

        print(text)

        return json.loads(text)
      
    except Exception as exc:
        print(exc)
        return {"entities": [], "relationships": []}


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of text chunks."""
    payload = {
        "inputs": texts,
        "options": {
            "use_cache": False,
            "wait_for_model": True,
        },
    }

    response = requests.post(HF_API_URL, headers=HEADERS, json=payload)
    if response.status_code == 200:
        return response.json()

    print(f"Embedding Error: {response.status_code}")
    print(response.text)
    return []


def parse_pdf(file_path: str):
    """Parse a PDF using the shared LlamaParse client."""
    if not parser:
        print("LLAMA_CLOUD_API_KEY missing.")
        return []

    try:
        print(f"Parsing {file_path}...")
        documents = parser.load_data(file_path)

        if not documents:
            print("No documents returned.")
            return []

        print(f"Parsing complete. Total documents: {len(documents)}")
        return documents
    except Exception as exc:
        print(f"Parsing Error: {exc}")
        return []


def chunk_documents(documents) -> list[str]:
    """Extract plain text chunks from parsed documents."""
    return [doc.text for doc in documents]


def embed_in_batches(chunk_texts: list[str]) -> list[list[float]]:
    """Embed chunks in fixed-size batches to keep the request flow simple."""
    all_vectors: list[list[float]] = []

    for start_index in range(0, len(chunk_texts), BATCH_SIZE):
        batch = chunk_texts[start_index:start_index + BATCH_SIZE]
        print(f"Embedding batch {start_index // BATCH_SIZE + 1} ({len(batch)} chunks)")

        vectors = embed_batch(batch)
        if vectors:
            all_vectors.extend(vectors)

    return all_vectors


def create_document_node(session, filename: str) -> None:
    """Create or reuse the main document node."""
    session.run(
        """
        MERGE (d:Document {name: $filename})
        """,
        filename=filename,
    )


def create_chunk_node(session, filename: str, index: int, text: str, embedding: list[float]) -> None:
    """Store one chunk node and link it to the document."""
    session.run(
        """
        MATCH (d:Document {name:$filename})

        MERGE (c:Chunk {chunk_id:$chunk_id})

        SET
            c.text=$text,
            c.embedding=$embedding

        MERGE (d)-[:HAS_CHUNK]->(c)
        """,
        filename=filename,
        chunk_id=f"{filename}_{index}",
        text=text,
        embedding=embedding,
    )


def create_entity_links(session, filename: str, chunk_index: int, graph: dict) -> None:
    """Create entity nodes and connect them to the chunk."""

    chunk_id = f"{filename}_{chunk_index}"

    for entity in graph.get("entities", []):
        label = entity["label"].replace(" ", "_")
        name = entity["name"].strip()

        result = session.run(
            f"""
            MATCH (c:Chunk {{chunk_id: $chunk_id}})

            MERGE (e:{label} {{name: $name}})

            MERGE (c)-[:MENTIONS]->(e)

            RETURN c.chunk_id AS chunk,
                   labels(e) AS labels,
                   e.name AS entity
            """,
            chunk_id=chunk_id,
            name=name,
        )

        record = result.single()

        if record is None:
            print(f"❌ Chunk not found: {chunk_id}")
        else:
            print(f"✅ Linked {record['entity']} to {record['chunk']}")


def create_relationship_links(session, graph: dict) -> None:
    """Create relationships between extracted entities."""

    for rel in graph.get("relationships", []):

        rel_type = rel["type"]

        if rel_type not in ALLOWED_RELATIONS:
            print(f"⚠️ Skipping unsupported relation: {rel_type}")
            continue

        source = rel["source"].strip()
        target = rel["target"].strip()

        result = session.run(
            f"""
            MATCH (a {{name: $source}})
            MATCH (b {{name: $target}})

            MERGE (a)-[r:{rel_type}]->(b)

            RETURN a.name AS source,
                   type(r) AS relation,
                   b.name AS target
            """,
            source=source,
            target=target,
        )

        record = result.single()

        if record is None:
            print(f"❌ Could not create: {source} -[{rel_type}]-> {target}")
        else:
            print(
                f"✅ {record['source']} -[{record['relation']}]-> {record['target']}"
            )


def store_in_neo4j(filename: str, documents, all_vectors: list[list[float]]) -> None:
    """Write the parsed chunks, embeddings, and graph data into Neo4j."""
    try:
        with driver.session() as session:
            create_document_node(session, filename)

            for index, (doc, embedding) in enumerate(zip(documents, all_vectors)):
            
                create_chunk_node(session, filename, index, doc.text, embedding)
                graph = extract_graph(doc.text)
                print(graph)
                create_entity_links(session, filename, index, graph)
                create_relationship_links(session, graph)
    except Exception as exc:
        print(f"Neo4j Ingestion Error: {exc}")


def all_flow(file_path: str, filename: str):
    """Run the full ingest flow in a simple, readable sequence."""
    documents = parse_pdf(file_path)
    if not documents:
        return [], []

    chunk_texts = chunk_documents(documents)
    print(f"Total chunks: {len(chunk_texts)}")
    # print(documents)
    # print(chunk_texts)

    all_vectors = embed_in_batches(chunk_texts)
    
    print(f"Generated {len(all_vectors)} embeddings.")

    store_in_neo4j(filename, documents, all_vectors)
    return documents, all_vectors
    
    


def ingest_uploaded_pdf(file_bytes: bytes, filename: str):
    """Save an uploaded PDF temporarily, process it, and remove the temp file."""
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name

        print(f"Temporary file created: {temp_path}")
        documents, embeddings = all_flow(temp_path, filename)

        return {
            "documents": documents,
            "embeddings": embeddings,
            "count": len(documents),
        }
    except Exception as exc:
        print(f"Processing Error: {exc}")
        return {
            "documents": [],
            "embeddings": [],
            "count": 0,
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
            print(f"Deleted temporary file: {temp_path}")