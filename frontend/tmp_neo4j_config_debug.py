import inspect
from neo4j import GraphDatabase, Config
print('GraphDatabase.driver signature:', inspect.signature(GraphDatabase.driver))
print('GraphDatabase.driver kwdefaults:', GraphDatabase.driver.__kwdefaults__)
print('Config attrs:', [a for a in dir(Config) if not a.startswith('_')])
print('Config doc snippet:')
print(Config.__doc__[:2000])
