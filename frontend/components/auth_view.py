import streamlit as st
import requests

from components.auth_cookie import write_auth_cookie
from components.api_config import get_backend_api_url


def render_auth_tab(backend_url=None, cookie_controller=None):
    if backend_url is None:
        backend_url = get_backend_api_url()
    if not st.session_state["access_token"]:
        left_gap, form_container, right_gap = st.columns([1, 2, 1])

        with form_container:
            st.subheader("System Access Login")
            with st.form("login_form"):
                emp_id = st.text_input("Employee ID", placeholder="e.g., EMP-1042")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submit_login = st.form_submit_button("Authenticate", use_container_width=True)

                if submit_login:
                    if not emp_id or not password:
                        st.error("Please provide both Employee ID and Password.")
                    else:
                        try:
                            payload = {"username": emp_id, "password": password}
                            response = requests.post(f"{backend_url}/api/auth/token", data=payload)

                            if response.status_code == 200:
                                data = response.json()
                                st.session_state["access_token"] = data["access_token"]
                                st.session_state["user_info"] = {
                                    "employee_id": data.get("employee_id"),
                                    "name": data.get("name", "Operator"),
                                    "role_tier": data.get("role_tier", "N/A"),
                                }

                                headers = {"Authorization": f"Bearer {data['access_token']}"}
                                try:
                                    user_res = requests.get(f"{backend_url}/api/users/me", headers=headers, timeout=10)
                                    if user_res.status_code == 200:
                                        st.session_state["user_info"] = user_res.json()
                                except requests.exceptions.RequestException:
                                    pass

                                if cookie_controller is not None:
                                    print("Writing auth cookie...")
                                    write_auth_cookie(
                                        cookie_controller,
                                        data["access_token"],
                                        st.session_state["user_info"],
                                    )

                                st.success("Authentication Successful!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Invalid credentials or access denied.")
                        except requests.exceptions.ConnectionError:
                            st.error(f"Could not connect to backend server at {backend_url}.")
    else:
        st.success("You are already securely authenticated into the OmniPlant network.")
