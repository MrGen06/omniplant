import streamlit as st
import requests

def render_employee_time_tab(api_url):
    if not st.session_state.get("access_token"):
        st.info("🔒 Authentication required. Please log in via the Authentication tab to submit maintenance tips.")
        return

    st.header("Employee Time - Share Your Knowledge")
    
    st.write("Enter maintenance tips, observations, or general knowledge below. You can use English, Hindi, Hinglish, short forms, or mix languages.")
    
    with st.form("tip_submission_form"):
        tip_text = st.text_area("Your Tip", placeholder="E.g., Pump-101 ka bearing awaz kar raha hai, check karna padega...", height=150)
        
        submit_btn = st.form_submit_button("Submit Tip", type="primary")
        
        if submit_btn:
            if not tip_text.strip():
                st.error("Tip cannot be empty.")
            else:
                user_info = st.session_state.get("user_info", {})
                if not user_info:
                    st.error("You must be logged in to submit a tip.")
                    return
                
                payload = {
                    "employee": {
                        "id": user_info.get("employee_id"),
                        "name": user_info.get("name")
                    },
                    "tip": tip_text
                }
                
                try:
                    res = requests.post(f"{api_url}/api/ingest/add_tip", json=payload, timeout=10)
                    if res.status_code == 200:
                        st.success("Tip submitted successfully! It is now pending approval by Tier 2 employees.")
                    else:
                        st.error(f"Failed to submit tip: {res.text}")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
