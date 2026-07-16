import inspect
import neo4j
import neo4j._conf as conf
from neo4j import GraphDatabase
print('neo4j module:', neo4j.__file__)
print('conf attrs:', [a for a in dir(conf) if not a.startswith('_')])
print('GraphDatabase.driver signature:', inspect.signature(GraphDatabase.driver))
print('driver doc first 500 chars:\n', GraphDatabase.driver.__doc__[:500])
print('\n=== conf source lines ===\n')
for i, line in enumerate(inspect.getsource(conf).splitlines(), 1):
    if 'URI_SCHEME' in line or 'SECURITY_TYPE' in line or 'Trust' in line or 'parse_neo4j_uri' in line or 'TrustAll' in line:
        print(f'{i:04}: {line}')
try:
    from neo4j._parser import parse_neo4j_uri
    print('\nparser imported successfully')
    print(inspect.getsource(parse_neo4j_uri))
except Exception as e:
    print('parser import error:', e)
