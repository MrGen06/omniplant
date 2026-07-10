import json
import os
from pyexpat.errors import messages
import tempfile

import dotenv
import requests
import re
from connection.llama_parse import parser
# FIX 1: Import the connection module context rather than a static uninitialized value
import connection.neo_4j as neo_4j 
from huggingface_hub import InferenceClient

dotenv.load_dotenv()
HEADERS = {
    "Authorization": f"Bearer {os.getenv('HUGGINGFACEHUB_ACCESS_TOKEN')}",
    "Content-Type": "application/json",
}

HF_API_URL = "https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en"


def create_embedding(query: str):
    print("query:", query)

    payload = {
        "inputs": query,
        "options": {
            "use_cache": False,
            "wait_for_model": True,
        },
    }

    response = requests.post(HF_API_URL, headers=HEADERS, json=payload)
    if response.status_code == 200:
        return response.json()

    print(f"Embedding Error: {response.status_code}")
    print(f"Response: {response.text}")
    raise Exception(f"Failed to create embedding: {response.status_code} - {response.text}")


client = InferenceClient(
    api_key=os.getenv("HUGGINGFACEHUB_ACCESS_TOKEN")
)


def extract_equipment(query):
    prompt = f"""
        You are an industrial equipment classifier.

        Extract ONLY the equipment name mentioned in the user's query.

        Return JSON only.

        Examples:

        Query:
        "The centrifugal pump-101 is vibrating."

        Output:
        {{"equipment":"Pump-101"}}

        Query:
        "Pressure inside Boiler-3 is increasing."

        Output:
        {{"equipment":"Boiler-3"}}

        Query:
        "{query}"

        Output:
        
        """
  
    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct",
        messages=[
            {"role":"user","content":prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content


def retrieve_chunks(session, embedding):
    if not embedding:
        print("Warning: No embedding provided to retrieve_chunks")
        return []

    try:
        query = """
        CALL db.index.vector.queryNodes(
            'chunkEmbedding',
            3,
            $embedding
        )

        YIELD node, score

        RETURN node, score
        """

        result = session.run(query, embedding=embedding)
     
        chunks = [dict(id=record['node']['chunk_id'],score=record['score']) for record in result]
        return chunks
    except Exception as e:
        print(f"Error retrieving chunks: {str(e)}")
        return []


def get_equipment_context(session, equipment):
    result = session.run(
        """
        MATCH (e:Equipment)

        WHERE toLower(e.id)=toLower($equipment)

        OPTIONAL MATCH (e)<-[:MENTIONS]-(c:Chunk)

        OPTIONAL MATCH (e)-[:REQUIRES]->(comp:Component)

        OPTIONAL MATCH (e)-[:MONITORS]->(mon:Component)

        OPTIONAL MATCH (e)-[:INDICATES]->(cond:Condition)

        OPTIONAL MATCH (e)-[:CONNECTED_TO]-(other:Equipment)

        OPTIONAL MATCH (e)-[:MAINTAINED_BY]->(wo:WorkOrder)

        RETURN
       
        collect(DISTINCT c.chunk_id) as chunk_id
      
        """,
        equipment=equipment
    )

    return result.single()


def build_context(chunk_id, session):
    if not chunk_id:
        print("No chunks found for the given equipment.")
        return ""

    query = """
    MATCH (c:Chunk)
    WHERE c.chunk_id IN $chunk_ids
    RETURN c.chunk_id AS chunk_id, c.text AS text
    """

    result = session.run(query, chunk_ids=chunk_id)

    context = "\n".join([record["text"] for record in result])
    return context


ROLE_PROMPTS = {
    "Field Technician": """
You are an industrial maintenance assistant.

Audience:
Field Technician

Always:
- Explain step by step.
- Mention tools required.
- Mention calibration values.
- Mention PPE.
- Mention safety lockout/tagout.
- Mention inspection sequence.
- Keep answers practical.

Never discuss business impact.
""",
    "Plant Manager": """
You are an industrial operations advisor.

Audience:
Plant Manager

Always discuss
- Production impact
- Downtime
- OEE
- Risk
- Maintenance scheduling
- Resource planning
- Preventive maintenance

Avoid low-level repair instructions.
"""
}


def answer_query(query, role, context):
    prompt = f"""
        {ROLE_PROMPTS[role]}

   

        Context:
        {context}

        User Question:
        {query}

        Provide:
        1. Problem Summary
        2. Possible Cause
        3. Relevant Manual Information
        4. Recommended Steps
        5. Safety Precautions
        
        INSTRUCTIONS
        dont greet the user, dont apologize, dont ask for more information, dont ask for confirmation, dont ask for feedback, dont ask for follow-up questions, dont ask for clarification, dont ask for additional details, dont ask for more context, dont ask for more specifics, dont ask for more information about the equipment, dont ask for more information about the issue, dont ask for more information about the symptoms, dont ask for more information about the environment, dont ask for more information about the conditions, dont ask for more information about the operating parameters, dont ask for more information about the maintenance history, dont ask for more information about the previous repairs, dont ask for more information about the previous inspections, dont ask for more information about the previous failures, dont ask for more information about the previous issues, dont ask for more information about the previous problems.

        Only use the supplied context.

        If information is missing, explicitly say so.

        Never invent maintenance procedures.
        """

    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct",
        messages=[
            {"role":"user","content":prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content
    
    
async def pipeline(query, role="Field Technician"):
    # FIX 2: Ensure that if role passes down as a single element list like ['Field Technician'], it strips out cleanly
    if isinstance(role, list):
        role = role[0] if len(role) > 0 else "Field Technician"

    # FIX 3: Dynamic evaluation to check that the connection module's live driver is up
    if neo_4j.driver is None:
        print("Driver is uninitialized. Re-executing system connection sync routine...")
        neo_4j.connect_to_neo4j()

    try:
        # Step 1: Turn the query into an embedding for semantic retrieval.
        embedding = create_embedding(query)
    except Exception as e:
        print(f"Error creating embedding: {str(e)}")
        raise Exception(f"Failed to process query: {str(e)}")

    # FIX 4: Use the dynamic module reference helper to initiate vector sessions safely
    chunks = retrieve_chunks(neo_4j.driver.session(), embedding)
    chunk_id = [chunk['id'] for chunk in chunks]

    # Step 3: Open a session wrapper using the active connection channel reference
    with neo_4j.driver.session() as session:

        # Step 4: Extract the equipment name referenced in the user query.
        raw_equipment = extract_equipment(query)
        try:
            equipment_name = json.loads(raw_equipment)
        except Exception:
            # Fallback parsing regex filter if LLM adds markdown triple backticks around JSON response block strings
            cleaned_json = re.search(r"\{.*\}", raw_equipment, re.DOTALL)
            equipment_name = json.loads(cleaned_json.group(0)) if cleaned_json else {}

        record = None

        if not equipment_name or 'equipment' not in equipment_name:
           print("No equipment found in query parsing evaluation sequence.")
        else:
            # Step 5: Fetch additional context tied to the extracted equipment.
            record = get_equipment_context(session, equipment_name['equipment'])

        # Step 6: Merge semantic chunks with structural data mapping nodes properties
        if not record:
            print(f"No context found for equipment properties evaluation mapping match.")
        else:
            print(f"Context retrieved for equipment records count: {record['chunk_id']}")
            chunk_id += record['chunk_id']
        
        chunk_id = list(set(chunk_id))
        print(f"Total Chunks Retrieved: {len(chunk_id)}")

        # Step 7: Assemble context text strings mapping array
        context = build_context(chunk_id, session)

        # Step 8: Generate final generative answers
        answer = answer_query(query, role, context)
        print(answer)

        return answer