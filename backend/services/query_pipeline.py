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


def build_workorder_context(session, equipment: str | None, query: str):
    """Fetch only maintenance history data when the user asks for work orders."""
    if equipment:
        result = session.run(
            """
            MATCH (e:Equipment)
            WHERE toLower(coalesce(e.id, e.name)) = toLower($equipment)

            OPTIONAL MATCH (e)-[:MAINTAINED_BY]->(wo:WorkOrder)

            RETURN collect(DISTINCT {
                id: wo.id,
                date: wo.date,
                description: wo.description
            }) AS workorders
            """,
            equipment=equipment,
        )
    else:
        # If the equipment name is missing, first try a direct work-order text search.
        result = session.run(
            """
            MATCH (e:Equipment)-[:MAINTAINED_BY]->(wo:WorkOrder)
            WHERE toLower(wo.id) CONTAINS toLower($query)
               OR toLower(wo.description) CONTAINS toLower($query)
               OR toLower(coalesce(e.id, e.name)) CONTAINS toLower($query)
            RETURN collect(DISTINCT {
                equipment: coalesce(e.id, e.name),
                id: wo.id,
                date: wo.date,
                description: wo.description
            }) AS workorders
            """,
            query=query,
        )

        record = result.single()
        if not record or not record["workorders"]:
            # Generic history questions should still return actual maintenance records.
            result = session.run(
                """
                MATCH (e:Equipment)-[:MAINTAINED_BY]->(wo:WorkOrder)
                RETURN collect(DISTINCT {
                    equipment: coalesce(e.id, e.name),
                    id: wo.id,
                    date: wo.date,
                    description: wo.description
                })[0..5] AS workorders
                """
            )

    record = result.single()
    if not record:
        return ""

    workorders = record["workorders"] or []
    if not workorders:
        return ""

    formatted_lines = []
    for workorder in workorders:
        if not workorder:
            continue

        equipment_name = workorder.get("equipment")
        header = [f"Work Order ID: {workorder.get('id', '')}"]
        if equipment_name:
            header.append(f"Equipment: {equipment_name}")
        if workorder.get("date"):
            header.append(f"Date: {workorder.get('date', '')}")

        formatted_lines.append(
            "\n".join(header + [f"Description: {workorder.get('description', '')}"])
        )

    return "\n\n".join(formatted_lines)


def answer_query(query, role, context):
    prompt = f"""
    {ROLE_PROMPTS[role]}

    Context:
    {context}

    User Question:
    {query}

    Use any relevant manual or work-order history information that appears in the context.
    Provide only the information that is available. Do not invent any information. If information is missing, explicitly say so.

    Provide:
    1. Problem Summary
    2. Possible Cause
    3. Relevant Manual Information
    4. Relevant Work Order History
    5. Recommended Steps
    6. Safety Precautions

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
    
    
def pipeline(query, role="Field Technician"):
    # FIX 2: Ensure that if role passes down as a single element list like ['Field Technician'], it strips out cleanly
    if isinstance(role, list):
        role = role[0] if len(role) > 0 else "Field Technician"

    # FIX 3: Dynamic evaluation to check that the connection module's live driver is up
    if neo_4j.driver is None:
        print("Driver is uninitialized. Re-executing system connection sync routine...")
        neo_4j.connect_to_neo4j()

    try:
        # Step 1: Open a session wrapper using the active connection channel reference.
        with neo_4j.driver.session() as session:

            # Step 2: Extract the equipment name referenced in the user query.
            raw_equipment = extract_equipment(query)
            try:
                equipment_name = json.loads(raw_equipment)
            except Exception:
                # Fallback parsing regex filter if LLM adds markdown triple backticks around JSON response block strings
                cleaned_json = re.search(r"\{.*\}", raw_equipment, re.DOTALL)
                equipment_name = json.loads(cleaned_json.group(0)) if cleaned_json else {}

            equipment = equipment_name.get("equipment") if equipment_name else None
            if not equipment:
                print("No equipment found in query parsing evaluation sequence.")

            try:
                print("Retrieving manual context with embeddings and chunk lookup.")
                embedding = create_embedding(query)
            except Exception as e:
                print(f"Error creating embedding: {str(e)}")
                raise Exception(f"Failed to process query: {str(e)}")

            chunks = retrieve_chunks(neo_4j.driver.session(), embedding)
            chunk_id = [chunk['id'] for chunk in chunks]

            record = None
            if not equipment:
                print("No equipment found for manual context enrichment.")
            else:
                record = get_equipment_context(session, equipment)

            if not record:
                print("No context found for equipment properties evaluation mapping match.")
            else:
                print(f"Context retrieved for equipment records count: {record['chunk_id']}")
                chunk_id += record['chunk_id']

            chunk_id = list(set(chunk_id))
            print(f"Total Chunks Retrieved: {len(chunk_id)}")

            manual_context = build_context(chunk_id, session)
            workorder_context = build_workorder_context(session, equipment, query)

            combined_context_parts = []
            if manual_context:
                combined_context_parts.append("Manual Context:\n" + manual_context)
            if workorder_context:
                combined_context_parts.append("Work Order History:\n" + workorder_context)

            context = "\n\n".join(combined_context_parts)
            if not context:
                print("No manual or work-order context found for the supplied query.")
                return (
                    "No manual or work-order history was found in Neo4j for this query. "
                    "Try including an equipment tag, work order ID, or a more specific maintenance term."
                )

            # Step 8: Generate final generative answers.
            answer = answer_query(query, role, context)
            print(answer)

            return answer
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        raise