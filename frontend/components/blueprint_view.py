import os
import ssl
import json
import base64
import streamlit as st
from neo4j import GraphDatabase
from dotenv import load_dotenv
from st_click_detector import click_detector  # Make sure to run: pip install st-click-detector

# Explicitly target the backend .env file relative to root/frontend execution
load_dotenv("../backend/.env")

# Pull Neo4j configuration safely from environment
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

@st.cache_data
def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return None

def render_blueprint_tab():
    st.subheader("Interactive P&ID Asset Explorer")
    
    # 1. Inspect the absolute directory layout of your live app
    BASE_DIR = os.path.abspath(os.getcwd())
    
    # Let's check common directory paths where Streamlit might be executing from
    option1 = os.path.join(BASE_DIR, "frontend", "assets", "blueprint.png")
    option2 = os.path.join(BASE_DIR, "assets", "blueprint.png")
    
    # Determine which path actually exists on the cloud server
    if os.path.exists(option1):
        IMAGE_PATH = option1
    elif os.path.exists(option2):
        IMAGE_PATH = option2
    else:
        # If both fail, print the active layout so we know exactly where it is!
        st.error(f"⚠️ File not found. Current executing directory: `{BASE_DIR}`")
        st.info("Here is what the cloud container sees in the current folder:")
        try:
            st.code("\n".join(os.listdir(BASE_DIR)))
        except Exception:
            pass
        return

    # Convert the found path to Base64
    img_b64 = get_image_base64(IMAGE_PATH)
    if not img_b64:
        st.error(f"Failed to decode image at: {IMAGE_PATH}")
        return

    # 2. Load Coordinates Mapping
    try:
        with open("../backend/data/blueprint_coords.json", "r") as f:
            equipment_nodes = json.load(f)
    except FileNotFoundError:
        st.error("Coordinates file data/blueprint_coords.json not found on backend!")
        return

    # 3. CSS for Overlays
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

    # 4. Generate Interactive Elements
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

    # 5. Capture Clicks
    clicked_tag = click_detector(full_html)

    # 6. Sidebar Graph Loading Logic
    if clicked_tag:
        st.sidebar.markdown("---")
        st.sidebar.header(f"Asset File: {clicked_tag}")
        st.sidebar.subheader("Live Knowledge Graph Status")
        
        if not NEO4J_URI:
            st.sidebar.error("Critical Error: NEO4J_URI is empty. Check your ../backend/.env path.")
            return
            
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD), ssl_context=ctx)
            
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
                st.sidebar.success(f"Found {len(records)} historical events linked to this asset:")
                for item in records:
                    with st.sidebar.expander(f"Ticket: {item['wo_id']}"):
                        st.write(f"**Date:** {item['date_issued']}")
                        st.info(f"**Log:** {item['desc']}")
            else:
                st.sidebar.warning(f"No active maintenance logs found for asset ID '{clicked_tag}'.")
                
        except Exception as db_err:
            st.sidebar.error(f"Failed to fetch data from graph repository: {db_err}")