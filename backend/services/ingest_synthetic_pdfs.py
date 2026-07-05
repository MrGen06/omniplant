import os
import json
import tempfile

import dotenv
import requests

from connection.llama_parse import parser
from connection.neo_4j import driver
dotenv.load_dotenv()

HEADERS = {
    "Authorization": f"Bearer {os.getenv('HUGGINGFACEHUB_ACCESS_TOKEN')}",
    "Content-Type": "application/json",
}

HF_API_URL = "https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en"

BATCH_SIZE = 16


def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a batch of text chunks.
    """
    payload = {
        "inputs": texts,
        "options": {
            "use_cache": False,
            "wait_for_model": True,
        },
    }

    response = requests.post(
        HF_API_URL,
        headers=HEADERS,
        json=payload,
    )

    if response.status_code == 200:
        return response.json()

    print(f"Embedding Error: {response.status_code}")
    print(response.text)
    return []


def parse_pdf(file_path: str):
    """
    Parse a PDF using LlamaParse.
    """
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

    except Exception as e:
        print(f"Parsing Error: {e}")
        return []


def all_flow(file_path: str, filename: str):
    """
    Parse the PDF and generate embeddings for all chunks.
    """
    
    
    # Step 1: Parse PDF
    documents = parse_pdf(file_path)

    if not documents:
        return [], []

    # Step 2: Extract text
    chunk_texts = [doc.text for doc in documents]

    print(f"Total chunks: {len(chunk_texts)}")

    # Step 3: Generate embeddings in batches
    all_vectors = []

    for i in range(0, len(chunk_texts), BATCH_SIZE):
        batch = chunk_texts[i:i + BATCH_SIZE]

        print(
            f"Embedding batch {i // BATCH_SIZE + 1} "
            f"({len(batch)} chunks)"
        )

        vectors = embed_batch(batch)

        if vectors:
            all_vectors.extend(vectors)

    print(f"Generated {len(all_vectors)} embeddings.")
    
    
    # step 4: push to neo4j
    try:
       with driver.session() as session:

        # Create the document node
            session.run(
            """
            MERGE (d:Document {name: $filename})
            """,
            filename=filename,
        )

        # Create chunks
            for idx, (doc, embedding) in enumerate(zip(documents, all_vectors)):
                session.run(
                """
                MATCH (d:Document {name: $filename})

                CREATE (c:Chunk {
                    chunk_id: $chunk_id,
                    text: $text,
                    embedding: $embedding
                })

                CREATE (d)-[:HAS_CHUNK]->(c)
                """,
                filename=filename,
                chunk_id=idx,
                text=doc.text,
                embedding=embedding,
            )
            print("Data successfully ingested into Neo4j.")
    except Exception as e:
        print(f"Neo4j Ingestion Error: {e}")
        
    
    return documents, all_vectors
            
    

    


def ingest_uploaded_pdf(file_bytes: bytes, filename: str):
    """
    Save uploaded PDF temporarily, parse it, generate embeddings,
    and delete the temporary file.
    """
    temp_path = None

    try:
        # Create a temporary PDF
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        ) as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name

        print(f"Temporary file created: {temp_path}")

        # Parse + Embed
        documents, embeddings = all_flow(temp_path,filename)

        # Example: Store in Neo4j
        # for doc, embedding in zip(documents, embeddings):
        #     create_node(doc.text, embedding)

        return {
            "documents": documents,
            "embeddings": embeddings,
            "count": len(documents),
        }

    except Exception as e:
        print(f"Processing Error: {e}")
        return {
            "documents": [],
            "embeddings": [],
            "count": 0,
        }

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
            print(f"Deleted temporary file: {temp_path}")