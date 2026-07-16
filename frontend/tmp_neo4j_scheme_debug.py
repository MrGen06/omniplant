import inspect
from neo4j import GraphDatabase
from neo4j._conf import URI_SCHEME_NEO4J, URI_SCHEME_NEO4J_SECURE, URI_SCHEME_NEO4J_SELF_SIGNED_CERTIFICATE, URI_SCHEME_NEO4J_SELF_SIGNED_CERTIFICATE
from neo4j._conf import SECURITY_TYPE_SECURE, SECURITY_TYPE_SELF_SIGNED_CERTIFICATE, SECURITY_TYPE_SELF_SIGNED_CERTIFICATE
print('GraphDatabase.driver signature:', inspect.signature(GraphDatabase.driver))
print('URI_SCHEME_NEO4J:', URI_SCHEME_NEO4J)
print('URI_SCHEME_NEO4J_SECURE:', URI_SCHEME_NEO4J_SECURE)
print('URI_SCHEME_NEO4J_SELF_SIGNED_CERTIFICATE:', URI_SCHEME_NEO4J_SELF_SIGNED_CERTIFICATE)
print('SECURE constant:', SECURITY_TYPE_SECURE)
print('SELF_SIGNED constant:', SECURITY_TYPE_SELF_SIGNED_CERTIFICATE)
print('available trust types in neo4j:', [a for a in dir(__import__('neo4j')) if 'Trust' in a])
