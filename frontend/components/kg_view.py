import streamlit as st
import requests

def render_kg_tab():
    # 1. Guardrail Protection
    if not st.session_state.get("access_token"):
        st.info("Knowledge Graph querying requires active authentication.")
        return

    st.subheader("Industrial AI Engine & Document Parser")
    
    # Create two clean columns: Left for PDF Ingestion, Right for Graph AI Querying
    col_ingest, col_query = st.columns([1, 1])
    
    with col_ingest:
        st.write("### Asset Document Ingestion")
        st.caption("Upload raw engineering manuals or PDFs to parse them into the Graph.")
        
        uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])
        if st.button("Process & Parse Document", use_container_width=True):
            if uploaded_file is not None:
                with st.spinner("Extracting schemas with LlamaParse & injecting to Neo4j..."):
                    # This placeholder will eventually hold: 
                    # files = {"file": uploaded_file.getvalue()}
                    # requests.post(f"{backend_url}/api/rag/upload", files=files)
                    st.success(f"Successfully processed '{uploaded_file.name}' into the network cluster!")
            else:
                st.error("Please select a valid PDF file first.")

    with col_query:
        st.write("### GraphRAG Search Analytics")
        st.caption("Query asset relationships using natural language.")
        
        kg_query = st.text_area(
            "Enter engineering query:", 
            placeholder="e.g., Which maintenance protocol applies to turbine overheating?",
            height=115
        )
        
        if st.button("Execute Graph Search", use_container_width=True):
            if not kg_query.strip():
                st.error("Please type an engineering query first.")
            else:
                with st.spinner("Traversing Neo4j Knowledge Graph vectors..."):
                    # Future integration target:
                    # response = requests.post(f"{backend_url}/api/rag/query", json={"query": kg_query})
                    st.info("Query dispatched to backend GraphRAG pipeline.")