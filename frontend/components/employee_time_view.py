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
                        st.rerun()
                    else:
                        st.error(f"Failed to submit tip: {res.text}")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

    st.markdown("---")
    st.subheader("📜 My Submitted Tips History")
    
    user_info = st.session_state.get("user_info", {})
    emp_id = user_info.get("employee_id")
    
    if emp_id:
        try:
            res = requests.get(f"{api_url}/api/ingest/my_tips/{emp_id}", timeout=5)
            if res.status_code == 200:
                my_tips = res.json()
                if my_tips:
                    for tip in my_tips:
                        status = tip.get("status", "Pending")
                        approvals = tip.get("approvals_count", 0)
                        created_at = tip.get("created_at", "")
                        
                        # Format timestamp if available
                        time_str = created_at.replace("T", " ")[:16] if created_at else ""
                        
                        if status == "Approved":
                            badge = "🟢 **Fully Approved & Ingested into Graph DB**"
                        else:
                            badge = f"🟡 **Pending Approval** (Approvals: {approvals}/2)"
                            
                        with st.expander(f"Tip #{tip['id']} — {time_str} ({status})"):
                            st.markdown(badge)
                            st.write(tip["tip_text"])
                            if tip.get("approved_by"):
                                approved_list = [x for x in tip["approved_by"].split(",") if x]
                                st.caption(f"Approved by Employee ID(s): {', '.join(approved_list)}")
                else:
                    st.info("You haven't submitted any tips yet.")
            else:
                st.error("Failed to load tip history.")
        except Exception as e:
            st.error(f"Could not fetch tip history: {str(e)}")
