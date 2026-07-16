import os
import requests
import streamlit as st
from dotenv import load_dotenv
from streamlit_cookies_controller import CookieController
import time
# Import our custom isolated modular views
from components.auth_cookie import clear_auth_cookie, read_auth_cookie
from components.auth_view import render_auth_tab
from components.dashboard_view import render_dashboard_tab
from components.kg_view import render_kg_tab
from components.blueprint_view import render_blueprint_tab
from components.other_information_view import render_other_information_tab
from components.manage_employees_view import render_manage_employees_tab
from components.api_config import get_backend_api_url
import time

load_dotenv()
BACKEND_API_URL = get_backend_api_url()

st.set_page_config(
    page_title="OmniPlant.AI Portal",
    page_icon="⚡",
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
    st.title("⚡ OmniPlant.AI")
    st.caption("Decoupled Modular Architecture")
    st.markdown("---")

    if st.session_state["access_token"]:
        user = st.session_state.get("user_info") or {}
        st.success(f"**Logged in as:** {user.get('name') or user.get('employee_id') or 'Operator'}")
        st.info(f"**Role Tier:** Level {user.get('role_tier', 'N/A')}")

        if st.button("Logout", use_container_width=True):
            clear_auth_cookie(cookie_controller)
            st.session_state["access_token"] = None
            st.session_state["user_info"] = None
            time.sleep(1)
            st.rerun()
    else:
        st.warning("Authentication Required")

st.title("Industrial Knowledge & Control Center")

available_tabs = [
    "Authentication",
    "Tier Dashboard",
    "Knowledge Graph & AI",
    "Interactive P&ID Blueprint",
    "Other Information",
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
    "Tier Dashboard": render_dashboard_tab,
    "Knowledge Graph & AI": render_kg_tab,
    "Interactive P&ID Blueprint": render_blueprint_tab,
    "Other Information": render_other_information_tab,
    "Manage Employees": lambda: render_manage_employees_tab(BACKEND_API_URL),
}

for idx, tab_label in enumerate(available_tabs):
    with tabs[idx]:
        tab_mapping[tab_label]()
