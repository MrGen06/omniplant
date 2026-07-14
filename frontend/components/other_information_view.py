import os

import streamlit as st
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def get_neo4j_credentials():
    """Get Neo4j credentials from Streamlit Cloud or local .env"""

    if "NEO4J_URI" in st.secrets:
        return (
            st.secrets["NEO4J_URI"],
            st.secrets.get("NEO4J_USERNAME", "neo4j"),
            st.secrets["NEO4J_PASSWORD"],
        )

    return (
        os.getenv("NEO4J_URI"),
        os.getenv("NEO4J_USERNAME", "neo4j"),
        os.getenv("NEO4J_PASSWORD"),
    )


def fetch_documents(session):
    query = """
    MATCH (d:Document)

    RETURN
        d.name AS filename
        
    ORDER BY d.name
    """

    return list(session.run(query))


def render_other_information_tab():

    st.subheader("📄 Uploaded PDF Documents")
    st.caption("View all PDF documents stored in the Knowledge Graph.")

    uri, username, password = get_neo4j_credentials()

    if not uri:
        st.error("Neo4j credentials not found.")
        return

    try:

        driver = GraphDatabase.driver(
            uri,
            auth=(username, password),
        )

        with driver.session() as session:
            documents = fetch_documents(session)

        driver.close()

        if not documents:
            st.info("No PDF documents found in the Knowledge Graph.")
            return

        st.success(f"Total Documents : {len(documents)}")

        for idx, doc in enumerate(documents, start=1):

            with st.expander(f"{idx}. {doc['filename']}"):

                st.write(f"**Document Name:** {doc['filename']}")

               
    except Exception as e:
        st.error(f"Error connecting to Neo4j: {e}")