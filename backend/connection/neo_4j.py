import os
from neo4j import GraphDatabase
from neo4j.exceptions import ConfigurationError
from dotenv import load_dotenv

# Find the absolute directory path of this file (backend/connection/)
current_dir = os.path.dirname(os.path.abspath(__file__))

# Point explicitly to backend/.env (go up one level from connection/ to backend/)
backend_env_path = os.path.join(current_dir, "..", ".env")

# Load it directly using the exact filesystem path
load_dotenv(dotenv_path=backend_env_path)

# Extract variables safely
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Basic sanity check to prevent empty initialization crashes
if not NEO4J_URI:
    raise ConfigurationError(
        f"Missing NEO4J_URI environment variable. Checked path: {os.path.abspath(backend_env_path)}"
    )

# Initialize driver globally safely
driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
)

# Function to connect to Neo4j database
def connect_to_neo4j():
    try:
        driver.verify_connectivity()
        print("Connected to Neo4j AuraDB Graph Cluster successfully!")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")