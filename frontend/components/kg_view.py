import os
import streamlit as st
import requests

# Point this to your Render backend or localhost during testing
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

def render_kg_tab():
    # 1. Guardrail Protection
    if not st.session_state.get("access_token"):
        st.info("Knowledge Graph querying requires active authentication.")
        return

    st.subheader("Industrial AI Engine & Document Parser")
    
    # Adjusted column width slightly to give the chat interface more breathing room
    col_ingest, col_query = st.columns([1, 1.5]) 
    
    with col_ingest:
        st.write("### Asset Document Ingestion")
        st.caption("Upload raw engineering manuals or PDFs to parse them into the Graph.")
        
        uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])
        if st.button("Process & Parse Document", use_container_width=True):
            if uploaded_file is not None:
                with st.spinner("Extracting schemas with LlamaParse & injecting to Neo4j..."):
                    # Future integration target
                    st.success(f"Successfully processed '{uploaded_file.name}' into the network cluster!")
            else:
                st.error("Please select a valid PDF file first.")

    with col_query:
        st.write("### OmniPlant AI Assistant")
        st.caption("Query asset relationships using natural language.")
        
        # Initialize Chat History in Session State specific to this tab
        if "kg_messages" not in st.session_state:
            st.session_state.kg_messages = []
            
        # Extract the user's role from the login session and map it to the backend's expected role labels.
        user_info = st.session_state.get("user_info") or {}
        role_tier = user_info.get("role_tier")
        if role_tier is None:
            user_role = "Field Technician"
        elif int(role_tier) >= 2:
            user_role = "Plant Manager"
        else:
            user_role = "Field Technician"
            
        # Create a fixed-height, scrollable container for the chat history
        chat_container = st.container(height=450)
        
        # Display existing chat messages on screen inside the container
        with chat_container:
            for message in st.session_state.kg_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Handle New User Input (st.chat_input anchors to the bottom automatically)
        if prompt := st.chat_input("Ask OmniPlant (e.g., 'What is the status of PUMP-101?'):"):
            
            # Add user message to state and display it
            st.session_state.kg_messages.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)

            # Call Person 1's Backend API
            with chat_container:
                with st.chat_message("assistant"):
                    with st.spinner("OmniPlant AI is thinking..."):
                        try:
                            # Send the chat request to the actual FastAPI query route.
                            api_endpoint = f"{BACKEND_API_URL}/api/ingest/query"
                            
                            payload = {
                                "query": prompt,
                                "role": user_role
                            }
                            
                            # Fire the POST request to the backend
                            response = requests.post(api_endpoint, json=payload)
                            
                            if response.status_code == 200:
                                # Assuming Person 1 returns a JSON like {"answer": "..."}
                                answer = response.json().get("answer", "No response generated.")
                            else:
                                answer = f"Backend Error {response.status_code}: {response.text}"
                                
                        except Exception as e:
                            answer = f"Connection failed. Is the backend running? Error: {e}"
                        
                        # Render the AI's response and save to history
                        st.markdown(answer)
                        st.session_state.kg_messages.append({"role": "assistant", "content": answer})