import streamlit as st
import base64
import json
from neo4j import GraphDatabase
import os
import ssl
from dotenv import load_dotenv
from st_click_detector import click_detector  # 1. Import the click detector

# 2. FIX: Explicitly target the backend .env file
load_dotenv("../backend/.env")

st.set_page_config(layout="wide")
st.title("Interactive P&ID Blueprint")

@st.cache_data
def get_image_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

try:
    img_b64 = get_image_base64("assets/blueprint.png")
except FileNotFoundError:
    st.error("Missing assets/blueprint.png file!")
    st.stop()

# Ensure this path matches your folder structure
with open("../backend/data/blueprint_coords.json", "r") as f:
    equipment_nodes = json.load(f)

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
    
    # 3. FIX: Change href to "#" and assign the tag to the HTML 'id' attribute
    overlay = f'<a href="#" id="{tag}" class="interactive-box" style="left: {left}%; top: {top}%; width: {width}%; height: {height}%;"></a>'
    html_elements.append(overlay)

full_html = f'{css_styles}<div class="blueprint-container"><img src="data:image/png;base64,{img_b64}" class="blueprint-img" />{"".join(html_elements)}</div>'

# 4. FIX: Replace st.markdown with click_detector
# This renders the HTML and waits for a user to click an element with an ID
clicked_tag = click_detector(full_html)

# ==========================================
# SIDEBAR LOGIC (No URL parameters needed anymore!)
# ==========================================

# Pull the variables (they will now successfully load from ../backend/.env)
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# If the click detector catches an ID, it stores it in 'clicked_tag'
if clicked_tag:
    st.sidebar.header(f"Asset File: {clicked_tag}")
    st.sidebar.subheader("Live Knowledge Graph Status")
    
    # Quick sanity check to ensure the variables loaded properly
    if not NEO4J_URI:
        st.sidebar.error("Critical Error: NEO4J_URI is empty. Check your ../backend/.env path.")
        st.stop()
        
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