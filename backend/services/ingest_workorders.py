import os
import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables (NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
load_dotenv()

# Configuration
CSV_FILE_PATH = "data/Historical_WorkOrders_2024.csv"
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

def clean_data(file_path):
    """Stage 1: Read and sanitize the CSV using Pandas"""
    print(f"Reading data from {file_path}...")
    
    # Load the CSV
    df = pd.read_csv(file_path)
    
    # Drop rows where critical IDs are missing (Graph needs valid endpoints)
    df.dropna(subset=['Equipment_Tag', 'WO_ID'], inplace=True)
    
    # Strip accidental whitespaces from string columns
    df['Equipment_Tag'] = df['Equipment_Tag'].astype(str).str.strip()
    df['WO_ID'] = df['WO_ID'].astype(str).str.strip()
    
    # Fill missing descriptions or dates with safe fallbacks
    if 'Issue_Description' not in df.columns:
        df['Issue_Description'] = "No description provided."
    else:
        df['Issue_Description'] = df['Issue_Description'].fillna("No description provided.")
        
    if 'Date_Issued' not in df.columns:
        df['Date_Issued'] = "Unknown Date"
    else:
        df['Date_Issued'] = df['Date_Issued'].fillna("Unknown Date")
    
    # Convert the clean DataFrame into a list of dictionaries for Neo4j
    records = df.to_dict(orient='records')
    print(f"Successfully cleaned {len(records)} records ready for ingestion.")
    return records

def insert_workorders_batch(tx, batch):
    cypher_query = """
    UNWIND $batch AS row

    // 1. Create or match the Equipment node
    MERGE (e:Equipment {
        id: toLower(row.Equipment_Tag),
        name: toLower(row.Equipment_Tag)
    })

    // 2. Create or match the WorkOrder node
    MERGE (w:WorkOrder {id: toLower(row.WO_ID)})
    SET
        w.description = row.Issue_Description,
        w.date = row.Date_Issued,
        w.Technician_Name = row.Tech_Name,
        w.Maintenance_Type = row.Maint_Type,
        w.Action_Taken = row.Action_Taken,
        w.Parts_Used = row.Parts_Used,
        w.Cost_INR = row.Cost_INR,
        w.Status = row.Status

    // 3. Establish the relationship
    MERGE (e)-[:MAINTAINED_BY]->(w)

    RETURN w.id AS id
    """
    return tx.run(cypher_query, batch=batch)

def push_to_neo4j(records):
    print("Connecting to Neo4j database...")
    
    # Dynamic Environment Switch: Detects if running on Render cloud container or locally
    is_production = "render" in os.getenv("RENDER_EXTERNAL_URL", "").lower() or NEO4J_URI.startswith("neo4j+s")
    
    if is_production:
        print("Production environment detected. Initializing standard secure driver...")
        driver = GraphDatabase.driver(
            NEO4J_URI, 
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
    else:
        print("Local environment detected. Applying unverified SSL context workaround...")
        import ssl
        custom_ssl_context = ssl.create_default_context()
        custom_ssl_context.check_hostname = False
        custom_ssl_context.verify_mode = ssl.CERT_NONE
        
        driver = GraphDatabase.driver(
            NEO4J_URI, 
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            ssl_context=custom_ssl_context
        )
    
    batch_size = 500
    total_records = len(records)
    
    with driver.session() as session:
        # print(records)
        for i in range(0, total_records, batch_size):
            batch = records[i : i + batch_size]
            session.execute_write(insert_workorders_batch, batch)
            print(f"Pushed records {i} to {i + len(batch)} / {total_records}")
            
    driver.close()
    print("Graph ingestion complete!")
    
def main():
    """Main execution flow: Clean CSV and push to Neo4j."""
    try:
        cleaned_records = clean_data(CSV_FILE_PATH)
        push_to_neo4j(cleaned_records)
    except Exception as e:
        print(f"An error occurred during the pipeline execution: {e}")

if __name__ == "__main__":
    main()