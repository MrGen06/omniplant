import os, ssl
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv('NEO4J_URI')
user = os.getenv('NEO4J_USERNAME')
pwd = os.getenv('NEO4J_PASSWORD')
print('URI:', uri)
print('USER:', user)
print('PWD len:', len(pwd) if pwd else 0)
if uri is None:
    raise RuntimeError('NEO4J_URI not set')
if uri.lower().startswith('neo4j+s://'):
    secure_uri = uri
elif uri.lower().startswith('neo4j://') and 'databases.neo4j.io' in uri.lower():
    secure_uri = uri.replace('neo4j://', 'neo4j+s://', 1)
    print('Transformed to:', secure_uri)
else:
    secure_uri = uri
    print('Using URI as provided without secure conversion')

print('Connecting to', secure_uri)
try:
    driver = GraphDatabase.driver(secure_uri, auth=(user, pwd))
    driver.verify_connectivity()
    print('CONNECTED via driver.verify_connectivity()')
    driver.close()
except Exception as e:
    print('CONNECT ERROR:', type(e).__name__, e)
    import traceback
    traceback.print_exc()
    try:
        driver.close()
    except Exception:
        pass
