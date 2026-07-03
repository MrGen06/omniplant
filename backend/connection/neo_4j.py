from neo4j import GraphDatabase
from dotenv import load_dotenv
load_dotenv()
import os


# load environment variables from .env file


NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
)


# Function to connect to Neo4j database

def connect_to_neo4j():
    try:
        driver.verify_connectivity()
        print("Connected successfully!")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")   
