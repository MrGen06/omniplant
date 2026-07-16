import inspect
from neo4j import GraphDatabase
print('signature:', inspect.signature(GraphDatabase.driver))
print('doc begins:\n', GraphDatabase.driver.__doc__[:1000])
print('params:', GraphDatabase.driver.__code__.co_varnames)
