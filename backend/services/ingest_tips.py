import os
import uuid
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Body, File, HTTPException, UploadFile, status
from huggingface_hub import InferenceClient
from neo4j import GraphDatabase

import connection.neo_4j as neo_4j 

client = InferenceClient( api_key=os.getenv("HUGGINGFACEHUB_ACCESS_TOKEN") )


logger = logging.getLogger(__name__)

def extract_equipment(raw_text):

    """
    Extract Equipment and Component entities from a maintenance tip using Qwen 2.5.

    Return JSON in the format:

    {
        "entities": [
            {
                "name": "...",
                "label": "Equipment"
            },
            {
                "name": "...",
                "label": "Component"
            }
        ]
    }
    """

    prompt = f"""
        You are an expert industrial maintenance engineer.

        The maintenance tip may be written in:
        - English
        - Hindi
        - Hinglish
        - Mixed language
        - Short forms
        - Spelling mistakes

        Your task is to identify every Equipment or Component mentioned in the maintenance tip.

        Definitions:

        Equipment:
        - Complete machines or major assets.
        Examples:
        Pump
        Motor
        Generator
        Compressor
        Heat Exchanger
        Transformer
        Boiler
        Conveyor
        Turbine
        Gearbox
        Fan

        Component:
        - Parts that belong to an equipment.
        Examples:
        Bearing
        Impeller
        Runner
        Seal
        Valve
        Coupling
        Shaft
        Guide Vane
        Rotor
        Stator
        Filter
        Gasket
        Bolt
        Nut
        Pipe
        Sensor

        Rules:
        1. Return ONLY valid JSON.
        2. Do NOT explain anything.
        3. The label MUST be either "Equipment" or "Component".
        4. Preserve the equipment/component name exactly as mentioned whenever possible.
        5. Do not invent entities that are not present.
        6. Ignore actions, faults, temperatures, and measurements.
        7. If no entity is found, return:
        {{"entities":[]}}

        Return this JSON format exactly:

        {{
            "entities": [
                {{
                    "name": "Pump-101",
                    "label": "Equipment"
                }},
                {{
                    "name": "Bearing",
                    "label": "Component"
                }}
            ]
        }}

        Maintenance Tip:
        {raw_text}
        """

    try:

        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-7B-Instruct",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0
        )

        result = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if result.startswith("```"):
            result = result.replace("```json", "").replace("```", "").strip()

        data = json.loads(result)

        if "entities" not in data:
            raise ValueError("'entities' key missing.")

        return data

    except json.JSONDecodeError as e:
        logger.error("Invalid JSON returned by LLM.")
        logger.error(result)
        return {"entities": []}

    except Exception as e:
        logger.exception("Equipment extraction failed.")
        return {"entities": []}
    


def store_tip(tx, employee, raw_tip, extracted):

    tip_id = str(uuid.uuid4())

    # Create employee and tip
    tx.run("""
    MERGE (e:Employee {id:$emp_id})
    SET e.name = $name

    CREATE (t:Tip {
        id:$tip_id,
        raw_text:$raw_tip,
        created_at:datetime()
    })

    MERGE (e)-[:SUBMITTED]->(t)
    """,
    emp_id=employee["id"].lower(),
    name=employee["name"].lower(),
    tip_id=tip_id,
    raw_tip=raw_tip.lower()
    )

    for entity in extracted.get("entities", []):

        name = entity["name"].strip().lower()
        label = entity["label"].strip().lower()
        print(f"Storing entity '{name}' with label '{label}' for tip '{tip_id}'.")

        if label == "equipment":

            tx.run("""
            MATCH (t:Tip {id:$tip_id})

            MERGE (n:Equipment {name:$name})
            ON CREATE SET
                n.id = randomUUID()

            MERGE (t)-[:ABOUT]->(n)
            """,
            tip_id=tip_id,
            name=name
            )

        elif label == "component":

            tx.run("""
            MATCH (t:Tip {id:$tip_id})

            MERGE (n:Component {name:$name})
            ON CREATE SET
                n.id = randomUUID()

            MERGE (t)-[:ABOUT]->(n)
            """,
            tip_id=tip_id,
            name=name
            )

        else:
            logger.warning(f"Unknown label '{label}' for entity '{name}'. Skipping.")



def process_tip(employee, raw_tip):

    try:
        # Ensure Neo4j connection exists
        if neo_4j.driver is None:
            logger.info("Neo4j driver not initialized. Connecting...")
            
            neo_4j.connect_to_neo4j()

        if neo_4j.driver is None:
            raise ConnectionError("Failed to connect to Neo4j.")

        # -------- Step 1 : Extract Equipment --------
        print(f"Extracting entities  from tip: {raw_tip}")
        try:
            extracted = extract_equipment(raw_tip)

            if not isinstance(extracted, dict):
                raise ValueError("LLM did not return a dictionary.")

            extracted.setdefault("entities", [])

        except Exception as e:
            raise HTTPException(
                status_=False,
                detail="Equipment extraction failed."
            )
            

        # -------- Step 2 : Store in Neo4j --------
        with neo_4j.driver.session() as session:
            session.execute_write(
                store_tip,
                employee,
                raw_tip,
                extracted
            )

        return {
            
            "success": True,
            "entities_found": len(extracted["entities"]),
            "entities": extracted["entities"]
        }

    except Exception as e:
        raise HTTPException(
            status=False,
            detail=f"Failed to process tip: {str(e)}"
        )
       
