import inspect
from neo4j import GraphDatabase
print('driver signature:', inspect.signature(GraphDatabase.driver))
source = inspect.getsource(GraphDatabase.driver)
lines = source.splitlines()
for i, line in enumerate(lines[:200], 1):
    print(f'{i:03}: {line}')
