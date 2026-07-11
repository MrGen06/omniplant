import os
import ssl
from neo4j import GraphDatabase
from neo4j.exceptions import ConfigurationError
from dotenv import load_dotenv

# Find the absolute directory path of this file (backend/connection/)
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_env_path = os.path.join(current_dir, "..", ".env")

# Load environment variables explicitly
load_dotenv(dotenv_path=backend_env_path)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not NEO4J_URI:
    raise ConfigurationError(
        f"Missing NEO4J_URI environment variable. Checked path: {os.path.abspath(backend_env_path)}"
    )

# Declare global driver placeholder so other pipeline modules can import it cleanly
driver = None
def connect_to_neo4j():
    global driver
    
    # If driver is already initialized, don't recreate it
    if driver is not None:
        return driver
        
    print(f"Initializing Neo4j Connection to: {NEO4J_URI}")
    
    # 1. Determine environment based on the URI scheme
    is_production = NEO4J_URI.startswith("neo4j+s")
    
    try:
        if is_production:
            # Production: Encrypted connection with strict SSL verification (Render cloud behavior)
            driver =   GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
            )
        else:
            # Local Development: Apply the custom unverified SSL context to bypass hotspot/Wi-Fi blocks
            print("Local environment scheme detected. Applying unverified SSL context workaround...")
            custom_ssl_context = ssl.create_default_context()
            custom_ssl_context.check_hostname = False
            custom_ssl_context.verify_mode = ssl.CERT_NONE
            
            driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
                ssl_context=custom_ssl_context
            )
            
        # 2. Verify connection viability
        driver.verify_connectivity()
        print("Connected to Neo4j Graph Cluster successfully!")
        return driver
        
    except Exception as e:
        print(f"Failed to connect to Neo4j database instance: {e}")
        # Reset driver to None so it can try again next cycle if network stabilizes
        driver = None 
        raise e