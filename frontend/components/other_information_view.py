import os
import ssl

import streamlit as st
from neo4j import GraphDatabase, TrustAll
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


def create_neo4j_driver(uri, username, password):
    if uri.lower().startswith("neo4j+s://"):
        return GraphDatabase.driver(uri, auth=(username, password))

    if uri.lower().startswith("neo4j://") and "databases.neo4j.io" in uri.lower():
        secure_uri = uri.replace("neo4j://", "neo4j+ssc://", 1)
        return GraphDatabase.driver(secure_uri, auth=(username, password))

    if uri.lower().startswith("bolt+s://"):
        return GraphDatabase.driver(uri, auth=(username, password))

    if uri.lower().startswith("bolt://") and "databases.neo4j.io" in uri.lower():
        secure_uri = uri.replace("bolt://", "bolt+ssc://", 1)
        return GraphDatabase.driver(secure_uri, auth=(username, password))

    return GraphDatabase.driver(
        uri,
        auth=(username, password),
        trusted_certificates=TrustAll(),
    )


def fetch_documents(session):
    query = """
    MATCH (d:Document)

    RETURN
        d.name AS filename,
        d.url AS url
        
    ORDER BY d.name
    """

    return list(session.run(query))


def render_other_information_tab():
    if not st.session_state.get("access_token"):
        st.info("🔒 Authentication required. Please log in via the Authentication tab to view uploaded documents.")
        return

    st.subheader("📄 Uploaded PDF Documents")
    st.caption("View all PDF documents stored in the Knowledge Graph.")

    uri, username, password = get_neo4j_credentials()

    if not uri:
        st.error("Neo4j credentials not found.")
        return

    try:

        driver = create_neo4j_driver(uri, username, password)

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
                if doc.get("url"):
                    st.markdown(f"[🔗 Open/Download PDF]({doc['url']})")
                    st.components.v1.iframe(doc["url"], height=600)
                else:
                    st.warning("No PDF URL found for this document.")

               
    except Exception as e:
        st.error(f"Error connecting to Neo4j: {e}")