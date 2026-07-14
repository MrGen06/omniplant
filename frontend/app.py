import os
import requests
import streamlit as st
from dotenv import load_dotenv
from streamlit_cookies_controller import CookieController

# Import our custom isolated modular views
from components.auth_cookie import clear_auth_cookie, read_auth_cookie
from components.auth_view import render_auth_tab
from components.dashboard_view import render_dashboard_tab
from components.kg_view import render_kg_tab
from components.blueprint_view import render_blueprint_tab
from components.other_information_view import render_other_information_tab
from components.api_config import get_backend_api_url


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
            st.rerun()
    else:
        st.warning("Authentication Required")

st.title("Industrial Knowledge & Control Center")

# MODIFIED: Added "Interactive Blueprint" as a 4th option in the list
tab_auth, tab_dashboard, tab_kg, tab_blueprint, tab_other_information = st.tabs([
    "Authentication",
    "Tier Dashboard",
    "Knowledge Graph & AI",
    "Interactive P&ID Blueprint", # ADDED THIS TAB
    "Other Information"
])

with tab_auth:
    render_auth_tab(BACKEND_API_URL, cookie_controller)

with tab_dashboard:
    render_dashboard_tab()

with tab_kg:
    render_kg_tab()

with tab_blueprint:
    render_blueprint_tab() # ADDED THIS CALL TO RENDER THE BLUEPRINT VIEW

with tab_other_information:
    render_other_information_tab()
