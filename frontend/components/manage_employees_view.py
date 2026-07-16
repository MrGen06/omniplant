import requests
import streamlit as st
from components.api_config import get_backend_api_url


def _build_auth_headers():
    return {"Authorization": f"Bearer {st.session_state['access_token']}"}


def _fetch_employees(backend_url):
    try:
        response = requests.get(f"{backend_url}/api/users/", headers=_build_auth_headers(), timeout=10)
        if response.status_code == 200:
            return response.json()
        st.error(f"Unable to load employees: {response.status_code} {response.text}")
    except requests.exceptions.RequestException as exc:
        st.error(f"Failed to fetch employees from backend: {exc}")
    return None


def _add_employee(backend_url, employee_id, name, role_tier, password):
    payload = {
        "employee_id": employee_id.strip().upper(),
        "name": name.strip(),
        "role_tier": int(role_tier),
        "password": password,
    }

    try:
        response = requests.post(f"{backend_url}/api/users/", json=payload, headers=_build_auth_headers(), timeout=10)
        if response.status_code == 201:
            return True, response.json()
        return False, response.json().get("detail", response.text)
    except requests.exceptions.RequestException as exc:
        return False, str(exc)


def _delete_employee(backend_url, employee_id):
    try:
        response = requests.delete(
            f"{backend_url}/api/users/{employee_id.strip().upper()}",
            headers=_build_auth_headers(),
            timeout=10,
        )
        if response.status_code == 200:
            return True, response.json().get("detail", "Employee removed.")
        return False, response.json().get("detail", response.text)
    except requests.exceptions.RequestException as exc:
        return False, str(exc)


def render_manage_employees_tab(backend_url=None):
    if backend_url is None:
        backend_url = get_backend_api_url()

    if not st.session_state.get("access_token") or not st.session_state.get("user_info"):
        st.info("Please authenticate first to access employee management.")
        return

    user = st.session_state["user_info"]
    current_tier = int(user.get("role_tier") or 0)
    if current_tier < 3:
        st.warning("Manage Employees is available only to Tier 3 employees.")
        return

    st.subheader("Manage Employees")
    st.caption("Tier 3 administrators can view current employee records, add new employees, and remove existing records.")

    if st.button("Refresh employee list", use_container_width=True):
        st.session_state.pop("employee_management_records", None)

    employees = st.session_state.get("employee_management_records")
    if employees is None:
        employees = _fetch_employees(backend_url)
        st.session_state["employee_management_records"] = employees

    if employees is None:
        return

    st.markdown(f"**Total Employees:** {len(employees)}")
    st.dataframe(employees)

    st.markdown("---")
    st.write("### Employee Details")
    if not employees:
        st.info("No employee records were found.")
    else:
        for record in employees:
            with st.expander(f"{record.get('employee_id', '')} — {record.get('name', '')}"):
                st.write(f"**Employee ID:** {record.get('employee_id', '')}")
                st.write(f"**Name:** {record.get('name', '')}")
                st.write(f"**Role Tier:** {record.get('role_tier', '')}")

    st.markdown("---")
    add_col, delete_col = st.columns(2)

    with add_col:
        st.write("### Add New Employee")
        with st.form("add_employee_form"):
            new_employee_id = st.text_input("Employee ID", placeholder="EMP-5011")
            new_name = st.text_input("Name", placeholder="Amit Kumar")
            new_role_tier = st.selectbox("Role Tier", [1, 2, 3], index=1)
            new_password = st.text_input("Password", type="password", placeholder="Strong password")
            submit_add = st.form_submit_button("Create Employee")

            if submit_add:
                if not new_employee_id or not new_name or not new_password:
                    st.error("Employee ID, name, and password are required.")
                else:
                    success, result = _add_employee(
                        backend_url,
                        new_employee_id,
                        new_name,
                        new_role_tier,
                        new_password,
                    )
                    if success:
                        st.success(f"Employee {result.get('employee_id')} created successfully.")
                        st.session_state.pop("employee_management_records", None)
                        st.rerun()
                    else:
                        st.error(f"Unable to create employee: {result}")

    with delete_col:
        st.write("### Delete Employee")
        employee_ids = [record.get("employee_id", "") for record in employees]
        if employee_ids:
            chosen_employee = st.selectbox("Select employee to remove", employee_ids)
            if st.button("Delete Selected Employee"):
                success, message = _delete_employee(backend_url, chosen_employee)
                if success:
                    st.success(message)
                    st.session_state.pop("employee_management_records", None)
                    st.rerun()
                else:
                    st.error(f"Unable to delete employee: {message}")
        else:
            st.info("No employees are available to remove.")
