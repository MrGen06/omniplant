import os
import requests
import streamlit as st
from dotenv import load_dotenv
from streamlit_cookies_controller import CookieController
import time

# Import our custom isolated modular views
from components.auth_cookie import clear_auth_cookie, read_auth_cookie
from components.auth_view import render_auth_tab
from components.kg_view import render_kg_tab
from components.blueprint_view import render_blueprint_tab
from components.other_information_view import render_other_information_tab
from components.manage_employees_view import render_manage_employees_tab
from components.employee_time_view import render_employee_time_tab
from components.api_config import get_backend_api_url

load_dotenv()
BACKEND_API_URL = get_backend_api_url()

st.set_page_config(
    page_title="OmniPlant.AI Portal",
    layout="wide",
    initial_sidebar_state="expanded"
)

cookie_controller = CookieController()

# Handle cross-tab data caching
if "access_token" not in st.session_state:
    st.session_state["access_token"] = None
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None


def restore_login_from_cookie():
    if st.session_state["access_token"]:
        return

    cookie_payload = read_auth_cookie(cookie_controller)
    if not cookie_payload:
        return

    access_token = cookie_payload["access_token"]
    user_info = cookie_payload.get("user_info") or {}
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        user_res = requests.get(f"{BACKEND_API_URL}/api/users/me", headers=headers, timeout=10)
        if user_res.status_code == 200:
            user_info = user_res.json()
        elif user_res.status_code in (401, 403):
            clear_auth_cookie(cookie_controller)
            return
    except requests.exceptions.RequestException:
        pass

    st.session_state["access_token"] = access_token
    st.session_state["user_info"] = user_info


restore_login_from_cookie()

# Sidebar controller layout
with st.sidebar:
    st.title("OmniPlant.AI")
    st.markdown("---")

    if st.session_state["access_token"]:
        user = st.session_state.get("user_info") or {}
        st.success(f"**Logged in as:** {user.get('name') or user.get('employee_id') or 'Operator'}")
        st.info(f"**Role Tier:** Level {user.get('role_tier', 'N/A')}")

        if st.button("Logout", use_container_width=True):
            clear_auth_cookie(cookie_controller)
            st.session_state.kg_messages=[]
           
            st.session_state["access_token"] = None
            st.session_state["user_info"] = None
            time.sleep(1)
            st.rerun()

        # Notification Sidebar for Tier 2 and above
        try:
            tier = int(user.get('role_tier', 0))
            if tier >= 2:
                st.markdown("---")
                st.subheader("🔔 Tip Approvals")
                try:
                    res = requests.get(f"{BACKEND_API_URL}/api/ingest/all_tips", timeout=5)
                    if res.status_code == 200:
                        all_tips = res.json()
                        if all_tips:
                            action_required = []
                            waiting_on_others = []
                            fully_approved = []
                            
                            current_emp_id = str(user.get('employee_id'))
                            for p in all_tips:
                                approved_list = [x for x in p.get('approved_by', '').split(',') if x]
                                if p.get('status') == 'Approved':
                                    fully_approved.append(p)
                                elif p.get('status') == 'Pending':
                                    if current_emp_id in approved_list:
                                        waiting_on_others.append(p)
                                    else:
                                        action_required.append(p)
                                        
                            if action_required:
                                st.markdown("**Action Required**")
                                for p in action_required:
                                    emp_id_str = f" ({p['employee_id']})" if p.get('employee_id') else ""
                                    with st.expander(f"Tip from {p['employee_name']}{emp_id_str}"):
                                        st.write(p['tip_text'])
                                        st.caption(f"Approvals: {p['approvals_count']}/2")
                                        if st.button("Approve", key=f"approve_{p['id']}", type="primary"):
                                            payload = {"tip_id": p['id'], "approver_id": current_emp_id}
                                            app_res = requests.post(f"{BACKEND_API_URL}/api/ingest/approve_tip", json=payload)
                                            if app_res.status_code == 200:
                                                st.success("Approved!")
                                                time.sleep(1)
                                                st.rerun()
                                            else:
                                                st.error(app_res.text)
                            
                            if waiting_on_others:
                                st.markdown("**Waiting on Others**")
                                for p in waiting_on_others:
                                    emp_id_str = f" ({p['employee_id']})" if p.get('employee_id') else ""
                                    with st.expander(f"Tip from {p['employee_name']}{emp_id_str}"):
                                        st.write(p['tip_text'])
                                        st.caption(f"Approvals: {p['approvals_count']}/2")
                                        st.info("✓ Approved by you")
                                        
                            if fully_approved:
                                st.markdown("**Fully Approved & Ingested**")
                                for p in fully_approved[:5]: # Show only last 5
                                    emp_id_str = f" ({p['employee_id']})" if p.get('employee_id') else ""
                                    with st.expander(f"Tip from {p['employee_name']}{emp_id_str}"):
                                        st.write(p['tip_text'])
                                        st.success("Ingested")
                        else:
                            st.info("No tips found.")
                except Exception as e:
                    st.error("Failed to load notifications.")
        except ValueError:
            pass
    else:
        st.warning("Authentication Required")

st.title("Industrial Knowledge & Control Center")

available_tabs = [
    "Authentication",
    "Knowledge Graph & AI",
    "Interactive P&ID Blueprint",
    "Other Information",
    "Employee Tips",
]

user_tier = 0
if st.session_state.get("user_info") is not None:
    try:
        user_tier = int(st.session_state["user_info"].get("role_tier", 0))
    except (TypeError, ValueError):
        user_tier = 0

if user_tier >= 3:
    available_tabs.append("Manage Employees")

tabs = st.tabs(available_tabs)

# Map tab label to its associated render function
tab_mapping = {
    "Authentication": lambda: render_auth_tab(BACKEND_API_URL, cookie_controller),
    "Knowledge Graph & AI": render_kg_tab,
    "Interactive P&ID Blueprint": render_blueprint_tab,
    "Other Information": render_other_information_tab,
    "Employee Tips": lambda: render_employee_time_tab(BACKEND_API_URL),
    "Manage Employees": lambda: render_manage_employees_tab(BACKEND_API_URL),
}

for idx, tab_label in enumerate(available_tabs):
    with tabs[idx]:
        tab_mapping[tab_label]()
