from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn
import os

from connection.neo_4j import connect_to_neo4j
from connection.llama_parse import parse_pdf


load_dotenv()

# connect to Neo4j database
connect_to_neo4j()

# parse PDF file using LlamaParse
parse_pdf()

# create FastAPI app
app=FastAPI()



if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000,reload=True)