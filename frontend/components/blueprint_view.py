import os
import json
import ssl
import base64
from datetime import datetime

import streamlit as st
from neo4j import GraphDatabase, TrustAll
from dotenv import load_dotenv
from st_click_detector import click_detector

load_dotenv()

STATUS_OPTIONS = ["Open", "In Progress", "Completed", "Closed"]
MAINTENANCE_OPTIONS = ["Preventive", "Corrective", "Inspection", "Breakdown", "Predictive"]


def get_neo4j_credentials():
    """Fetch Neo4j credentials from Streamlit secrets or environment variables."""
    if "NEO4J_URI" in st.secrets:
        return (
            st.secrets["NEO4J_URI"],
            st.secrets.get("NEO4J_USERNAME", "neo4j"),
            st.secrets["NEO4J_PASSWORD"],
        )
    return os.getenv("NEO4J_URI"), os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD")


@st.cache_data
def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return None


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

    # Local / self-signed fallback for non-routing URIs
    return GraphDatabase.driver(
        uri,
        auth=(username, password),
        trusted_certificates=TrustAll(),
    )


def load_equipment_nodes(base_dir, frontend_dir):
    json_paths = [
        os.path.join(base_dir, "backend", "data", "blueprint_coords.json"),
        os.path.join(os.path.dirname(frontend_dir), "backend", "data", "blueprint_coords.json"),
        os.path.join(frontend_dir, "data", "blueprint_coords.json"),
        "../backend/data/blueprint_coords.json",
    ]

    for path in json_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
    return None


def fetch_work_orders(session, asset_id):
    query = """
    MATCH (e:Equipment {id:$asset_id})-[:MAINTAINED_BY]->(w:WorkOrder)
    RETURN
        w.id AS id,
        w.description AS description,
        w.date AS date,
        coalesce(w.Techenician_Name) AS technician,
        w.Maintenance_Type AS maintenance_type,
        w.Action_Taken AS action_taken,
        w.Parts_Used AS parts_used,
        w.Cost_INR AS cost,
        w.Status AS status
    ORDER BY w.date DESC
    """
    return list(session.run(query, asset_id=asset_id))


def create_work_order(
    session,
    asset_id,
    wo_id,
    description,
    technician,
    maintenance_type,
    action_taken,
    parts_used,
    cost,
    status,
):
    
    print(f"Creating work order {wo_id} for asset {asset_id} with status {status}")
    query = """
    MERGE (e:Equipment {id:$asset_id})
    MERGE (w:WorkOrder {id:$wo_id})
    SET
        w.description=$description,
        w.date=$date,
        w.Techenician_Name=$technician,
        w.Maintenance_Type=$maintenance_type,
        w.Action_Taken=$action_taken,
        w.Parts_Used=$parts_used,
        w.Cost_INR=$cost,
        w.Status=$status
    MERGE (e)-[:MAINTAINED_BY]->(w)
    """

    session.run(
        query,
        asset_id=asset_id,
        wo_id=wo_id,
        description=description,
        technician=technician,
        maintenance_type=maintenance_type,
        action_taken=action_taken,
        parts_used=parts_used,
        cost=cost,
        status=status,
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def update_work_order(
    session,
    wo_id,
    description,
    technician,
    maintenance_type,
    action_taken,
    parts_used,
    cost,
    status,
):
    query = """
    MATCH (w:WorkOrder {id:$wo_id})
    SET
        w.description=$description,
        w.Techenician_Name=$technician,
        w.Maintenance_Type=$maintenance_type,
        w.Action_Taken=$action_taken,
        w.Parts_Used=$parts_used,
        w.Cost_INR=$cost,
        w.Status=$status
    RETURN w.id AS id
    """

    result = session.run(
        query,
        wo_id=wo_id,
        description=description,
        technician=technician,
        maintenance_type=maintenance_type,
        action_taken=action_taken,
        parts_used=parts_used,
        cost=cost,
        status=status,
    ).single()
    return result is not None


def render_blueprint_tab():
    st.subheader("Interactive P&ID Asset Explorer")
    st.write("Click directly on any highlighted equipment tag on the blueprint drawing to fetch and manage work orders.")

    base_dir = os.path.abspath(os.getcwd())
    current_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.dirname(current_dir)

    option1_img = os.path.join(frontend_dir, "assets", "blueprint.png")
    option2_img = os.path.join(base_dir, "assets", "blueprint.png")
    image_path = option1_img if os.path.exists(option1_img) else option2_img

    img_b64 = get_image_base64(image_path)
    if not img_b64:
        st.error("Missing blueprint image asset inside assets/blueprint.png")
        return

    equipment_nodes = load_equipment_nodes(base_dir, frontend_dir)
    if equipment_nodes is None:
        st.error("Coordinates file blueprint_coords.json was not found.")
        return

    css_styles = """
    <style>
        .blueprint-container { position: relative; width: 100%; max-width: 1200px; margin: auto; }
        .blueprint-img { width: 100%; height: auto; display: block; }
        .interactive-box {
            position: absolute;
            background-color: transparent;
            border: 2px solid transparent;
            cursor: pointer;
            display: block;
            text-decoration: none;
            transition: all 0.2s ease-in-out;
            z-index: 10;
        }
        .interactive-box:hover {
            background-color: rgba(0, 255, 0, 0.25);
            border-color: lime;
        }
    </style>
    """

    html_elements = []
    for node in equipment_nodes:
        try:
            left = float(node["x_min"]) * 100
            top = float(node["y_min"]) * 100
            width = (float(node["x_max"]) - float(node["x_min"])) * 100
            height = (float(node["y_max"]) - float(node["y_min"])) * 100
            tag = str(node["equipment_id"]).strip()
        except (KeyError, TypeError, ValueError):
            continue

        if not tag:
            continue

        overlay = (
            f'<a href="#" id="{tag}" class="interactive-box" '
            f'style="left:{left}%; top:{top}%; width:{width}%; height:{height}%;"></a>'
        )
        html_elements.append(overlay)

    full_html = (
        f'{css_styles}<div class="blueprint-container">'
        f'<img src="data:image/png;base64,{img_b64}" class="blueprint-img" />'
        f'{"".join(html_elements)}</div>'
    )

    clicked_tag = click_detector(full_html)
    if clicked_tag:
        st.session_state["blueprint_selected_asset"] = clicked_tag

    selected_asset = st.session_state.get("blueprint_selected_asset")
    if not selected_asset:
        st.info("Select an equipment item on the blueprint to manage work orders.")
        return

    st.sidebar.markdown("---")
    st.sidebar.header(f"Asset: {selected_asset}")
    st.sidebar.caption("Create and update work orders")

    uri, username, password = get_neo4j_credentials()
    if not uri or not password:
        st.sidebar.error("Neo4j configuration is missing. Add NEO4J_URI and NEO4J_PASSWORD.")
        return

    user = st.session_state.get("user_info") or {}
    default_employee = user.get("name") or user.get("employee_id") or "Operator"
    asset_id = selected_asset.lower()

    driver = None
    try:
        driver = create_neo4j_driver(uri, username, password)
        if "show_workorder_form" not in st.session_state:
            st.session_state.show_workorder_form = False

        if st.sidebar.button("➕ Add Work Order", use_container_width=True):
            st.session_state.show_workorder_form =True

        if st.session_state.show_workorder_form:
                print(f"Rendering work order form for asset {asset_id}")

                st.sidebar.subheader("Add Work Order")
                with st.sidebar.form("create_work_order_form"):
                    new_wo_id = st.text_input("Work Order ID")
                    new_description = st.text_area("Description")
                    new_technician = st.text_input("Technician Name", value=default_employee)
                    new_maintenance_type = st.selectbox("Maintenance Type", MAINTENANCE_OPTIONS)
                    new_action_taken = st.text_area("Action Taken")
                    new_parts_used = st.text_input("Parts Used")
                    new_cost = st.number_input("Cost (INR)", min_value=0.0, step=100.0)
                    new_status = st.selectbox("Status", STATUS_OPTIONS)
                    submit_create = st.form_submit_button("Create Work Order", use_container_width=True)

                if submit_create:
                    print(f"Attempting to create work order {new_wo_id} for asset {asset_id}")
                    if not new_wo_id.strip() or not new_description.strip():
                        st.sidebar.error("Work Order ID and Description are required.")
                    else:
                        with driver.session() as session:
                            create_work_order(
                                session=session,
                                asset_id=asset_id,
                                wo_id=new_wo_id.strip(),
                                description=new_description.strip(),
                                technician=new_technician.strip() or default_employee,
                                maintenance_type=new_maintenance_type,
                                action_taken=new_action_taken.strip(),
                                parts_used=new_parts_used.strip(),
                                cost=float(new_cost),
                                status=new_status,
                            )
                        st.sidebar.success(f"Work order {new_wo_id.strip()} created.")
                        st.rerun()

        with driver.session() as session:
            records = fetch_work_orders(session, asset_id)

        if not records:
            st.sidebar.warning(f"No work orders found for asset {selected_asset}.")
            return

        st.sidebar.success(f"Found {len(records)} work order(s).")
        for idx, item in enumerate(records):
            wo_id = item.get("id")
            if not wo_id:
                continue

            description_value = item.get("description") or ""
            technician_value = item.get("technician") or default_employee
            maintenance_type_value = item.get("maintenance_type") or MAINTENANCE_OPTIONS[0]
            action_taken_value = item.get("action_taken") or ""
            parts_used_value = item.get("parts_used") or ""
            status_value = item.get("status") if item.get("status") in STATUS_OPTIONS else STATUS_OPTIONS[0]

            cost_raw = item.get("cost")
            try:
                cost_value = float(cost_raw) if cost_raw is not None else 0.0
            except (TypeError, ValueError):
                cost_value = 0.0

            with st.sidebar.expander(f"Work Order: {wo_id}"):
                st.write(f"Date: {item.get('date') or 'N/A'}")
                edit_description = st.text_area("Description", value=description_value, key=f"desc_{idx}_{wo_id}")
                edit_technician = st.text_input("Technician", value=technician_value, key=f"tech_{idx}_{wo_id}")
                edit_maintenance = st.selectbox(
                    "Maintenance Type",
                    MAINTENANCE_OPTIONS,
                    index=MAINTENANCE_OPTIONS.index(maintenance_type_value)
                    if maintenance_type_value in MAINTENANCE_OPTIONS
                    else 0,
                    key=f"maint_{idx}_{wo_id}",
                )
                edit_action_taken = st.text_area("Action Taken", value=action_taken_value, key=f"action_{idx}_{wo_id}")
                edit_parts_used = st.text_input("Parts Used", value=parts_used_value, key=f"parts_{idx}_{wo_id}")
                edit_cost = st.number_input(
                    "Cost (INR)",
                    min_value=0.0,
                    value=cost_value,
                    step=100.0,
                    key=f"cost_{idx}_{wo_id}",
                )
                edit_status = st.selectbox(
                    "Status",
                    STATUS_OPTIONS,
                    index=STATUS_OPTIONS.index(status_value),
                    key=f"status_{idx}_{wo_id}",
                )

                if st.button("Update Work Order", key=f"update_{idx}_{wo_id}", use_container_width=True):
                    with driver.session() as session:
                        updated = update_work_order(
                            session=session,
                            wo_id=wo_id,
                            description=edit_description.strip(),
                            technician=edit_technician.strip() or default_employee,
                            maintenance_type=edit_maintenance,
                            action_taken=edit_action_taken.strip(),
                            parts_used=edit_parts_used.strip(),
                            cost=float(edit_cost),
                            status=edit_status,
                        )

                    if updated:
                        st.sidebar.success(f"Updated {wo_id}.")
                        st.rerun()
                    else:
                        st.sidebar.error(f"Could not update {wo_id}.")

    except Exception as db_err:
        st.sidebar.error(f"Failed to fetch data from graph repository: {db_err}")
    finally:
        if driver is not None:
            driver.close()