import os
import ssl
import json
import base64
import streamlit as st
from neo4j import GraphDatabase
from dotenv import load_dotenv
from st_click_detector import click_detector

# Local development fallback path
load_dotenv("../backend/.env")

def get_neo4j_credentials():
    """Safely fetches credentials from Streamlit Secrets (Cloud) or .env (Local)"""
    # 1. Check Streamlit Cloud Secrets first
    if "NEO4J_URI" in st.secrets:
        return st.secrets["NEO4J_URI"], st.secrets.get("NEO4J_USERNAME", "neo4j"), st.secrets["NEO4J_PASSWORD"]
    
    # 2. Fallback to local environment variables
    return os.getenv("NEO4J_URI"), os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD")

@st.cache_data
def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return None

def render_blueprint_tab():
    st.subheader("Interactive P&ID Asset Explorer")
    st.write("Click directly on any highlighted equipment tag on the blueprint drawing to fetch graph records.")

    # Paths layout handling
    BASE_DIR = os.path.abspath(os.getcwd())
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    FRONTEND_DIR = os.path.dirname(CURRENT_DIR)

    option1_img = os.path.join(FRONTEND_DIR, "assets", "blueprint.png")
    option2_img = os.path.join(BASE_DIR, "assets", "blueprint.png")
    IMAGE_PATH = option1_img if os.path.exists(option1_img) else option2_img

    img_b64 = get_image_base64(IMAGE_PATH)
    if not img_b64:
        st.error("Missing blueprint image asset inside 'assets/blueprint.png'!")
        return

    json_paths = [
        os.path.join(BASE_DIR, "backend", "data", "blueprint_coords.json"),
        os.path.join(os.path.dirname(FRONTEND_DIR), "backend", "data", "blueprint_coords.json"),
        os.path.join(FRONTEND_DIR, "data", "blueprint_coords.json"),
        "../backend/data/blueprint_coords.json"
    ]

    equipment_nodes = None
    for path in json_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    equipment_nodes = json.load(f)
                break
            except Exception:
                pass

    if equipment_nodes is None:
        st.error("Coordinates file `blueprint_coords.json` not found anywhere on the server paths!")
        return

    # Render CSS and HTML Layout Map
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
        left = node["x_min"] * 100
        top = node["y_min"] * 100
        width = (node["x_max"] - node["x_min"]) * 100
        height = (node["y_max"] - node["y_min"]) * 100
        tag = node["equipment_id"]
        
        overlay = f'<a href="#" id="{tag}" class="interactive-box" style="left: {left}%; top: {top}%; width: {width}%; height: {height}%;"></a>'
        html_elements.append(overlay)

    full_html = f'{css_styles}<div class="blueprint-container"><img src="data:image/png;base64,{img_b64}" class="blueprint-img" />{"".join(html_elements)}</div>'

    # Capture click
    clicked_tag = click_detector(full_html)

    # Resolve credentials safely
    uri, username, password = get_neo4j_credentials()

    # Handle Sidebar display safely without crashing or looping
    if clicked_tag:
        st.sidebar.markdown("---")
        st.sidebar.header(f"Asset File: {clicked_tag}")
        st.sidebar.subheader("Live Knowledge Graph Status")
        
        if not uri:
            st.sidebar.error("Config Error: Cloud Secrets are missing! Add NEO4J_URI to your Streamlit App Dashboard Settings.")
            return
            
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            # Connect using parameters resolved dynamically
            driver = GraphDatabase.driver(uri, auth=(username, password), ssl_context=ctx)
            
            cypher_query = """
            MATCH (e:Equipment {id: $asset_id})-[:MAINTAINED_BY]->(w:WorkOrder)
            RETURN w.id AS wo_id, w.description AS desc, w.date AS date_issued
            ORDER BY date_issued DESC
            """
            
            with driver.session() as session:
                result = session.run(cypher_query, asset_id=clicked_tag)
                records = [row for row in result]
                
            driver.close()
            
            if records:
                st.sidebar.success(f"Found {len(records)} events linked to this asset:")
                for item in records:
                    with st.sidebar.expander(f"Ticket: {item['wo_id']}"):
                        st.write(f"**Date:** {item['date_issued']}")
                        st.info(f"**Log:** {item['desc']}")
            else:
                st.sidebar.warning(f"No active maintenance logs found for asset ID '{clicked_tag}'.")
                
        except Exception as db_err:
            st.sidebar.error(f"Failed to fetch data from graph repository: {db_err}")