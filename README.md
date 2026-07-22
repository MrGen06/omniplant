# ⚡ OmniPlant.AI — Industrial Knowledge & Control Center

**OmniPlant.AI** is an enterprise-grade industrial intelligence platform that combines **Interactive P&ID (Piping & Instrumentation Diagram) Blueprints**, **Hybrid Graph-Vector Retrieval-Augmented Generation (RAG)**, **Peer-Approved Employee Maintenance Tips**, and **Role-Based Access Control (RBAC)** to streamline plant operations, maintenance troubleshooting, and equipment diagnostics.

---

## 🌟 Key Features

- **⚡ Interactive P&ID Blueprint Visualizer**: Interactive asset inspection with spatial coordinate mapping and subcomponent drill-downs.
- **🧠 Hybrid Knowledge Graph & Vector AI Assistant**: Combines dense vector similarity search (384-d `BAAI/bge-small-en` embeddings) with Neo4j Property Graph traversal to query complex equipment histories, part dependencies, maintenance tips, and fault causes.
- **💡 Employee Maintenance Tips & Peer-Approval Workflow**:
  - Field technicians and engineers submit operational tips and maintenance notes.
  - Interactive sidebar notification drawer alerts Tier 2+ engineers for peer review.
  - Automatic ingestion into Neo4j graph & vector store once **2 peer approvals** are recorded.
  - Approved tips are dynamically cited by the RAG AI chatbot during diagnostic queries.
- **📄 Automated Document Ingestion Pipeline**: Extracts structured entity-relationship triplets and text embeddings directly from industrial manuals and maintenance PDFs using LlamaParse and LLMs.
- **🔐 Multi-Tier Role-Based Access Control (RBAC)**:
  - **Tier 1 (Operator)**: Blueprint viewing, asset search, AI assistant diagnostics, maintenance tip submission.
  - **Tier 2 (Engineer)**: Peer tip review & approval, tip ingestion, workorder logging.
  - **Tier 3 (Plant Manager / Admin)**: Document ingestion management, employee role assignment, user administration.
- **🍪 Secure Cookie Session Management**: Stateless JWT OAuth2 authentication with persistent browser session handling.

---

## 🏗 System Architecture Overview

OmniPlant.AI uses a decoupled client-server architecture:

- **Frontend**: Streamlit application (`frontend/app.py`) providing a modular multi-tab UI with an interactive sidebar notification drawer.
- **Backend API**: FastAPI engine (`backend/main.py`) managing security, async connections, document ingestion, peer-tip approvals, and hybrid search.
- **Databases**:
  - **SQLite (`omniplant.db`)**: Stores user accounts, hashed credentials, role tiers, and pending employee maintenance tips (`PendingTip` ORM model).
  - **Neo4j Graph & Vector DB**: Stores document nodes, text chunks, equipment entity-relationships, approved maintenance tip nodes, and 384-dimensional vector indexes (`chunkEmbedding`).
- **Cloud AI Services**: LlamaParse (PDF parsing), HuggingFace Inference API (`bge-small-en` & `Qwen2.5-7B-Instruct`), and ImageKit CDN.

> 📖 For full system diagrams, sequence flows, database schemas, and architectural specs, view [`ARCHITECTURE.md`](file:///d:/omniplant/ARCHITECTURE.md).

---

## 📁 Repository Structure

```
omniplant/
├── ARCHITECTURE.md          # Complete architectural specification & Mermaid diagrams
├── README.md                # Project README & setup instructions
├── backend/                 # FastAPI API Engine & AI Pipeline
│   ├── api/                 # API Endpoints (auth, users, ingest)
│   ├── connection/          # Database & Cloud drivers (Neo4j, LlamaParse)
│   ├── core/                # Auth middleware, DB config, security
│   ├── data/                # Sample datasets & PDF manuals
│   ├── models/              # SQLAlchemy models (User, PendingTip)
│   ├── services/            # Ingestion, query pipeline, tip processing, ImageKit
│   ├── tests/               # Backend tests
│   ├── main.py              # Application entry point (FastAPI)
│   ├── omniplant.db         # SQLite database file
│   └── requirements.txt     # Backend Python dependencies
└── frontend/                # Streamlit Client Application
    ├── assets/              # App images and blueprint graphics
    ├── components/          # Isolated UI tabs
    │   ├── auth_cookie.py           # Browser cookie session handler
    │   ├── auth_view.py             # Login & Registration tab
    │   ├── blueprint_view.py        # Interactive P&ID Blueprint tab
    │   ├── employee_time_view.py    # Employee Maintenance Tips tab [NEW]
    │   ├── kg_view.py               # Knowledge Graph & AI Chatbot tab
    │   ├── manage_employees_view.py # Admin User Management tab (Tier 3)
    │   └── other_information_view.py# System documentation & info tab
    ├── app.py               # Streamlit entry point & notification sidebar
    └── requirements.txt     # Frontend Python dependencies
```

---

## 🛠 Active API Endpoints

### 🔑 Authentication & Users
- `POST /api/auth/login`: Authenticate user and issue JWT bearer token.
- `GET /api/users/me`: Fetch profile details for currently authenticated user.
- `GET /api/users/`: List all registered users (Tier 3 admin required).
- `POST /api/users/register`: Register new employee account (Tier 3 admin required).
- `PUT /api/users/{id}/tier`: Update user role tier (Tier 3 admin required).

### 💡 Maintenance Tips & Peer Review
- `POST /api/ingest/add_tip`: Submit a new pending maintenance tip.
- `GET /api/ingest/all_tips`: Fetch all pending, waiting, and approved tips.
- `GET /api/ingest/my_tips/{employee_id}`: Fetch tips submitted by a specific employee.
- `POST /api/ingest/approve_tip`: Record a peer approval (auto-pushes to Neo4j once 2 approvals are reached).

### 🤖 AI Query & Ingestion
- `POST /api/ingest/pdf`: Upload and process PDF manuals into vector & graph databases.
- `POST /api/ingest/query` (or `/ask_omniplant`): Hybrid RAG query endpoint returning synthesized LLM answers with document & tip citations.

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.10+** installed
- **Neo4j Instance** (Neo4j AuraDB Cloud or local Neo4j Desktop / Docker container)
- API Keys for **HuggingFace**, **LlamaParse**, and **ImageKit** (optional for asset storage)

---

### 1. Backend Setup

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in `backend/`:
   ```env
   NEO4J_URI=neo4j+s://<your-neo4j-uri>
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=<your-neo4j-password>
   NEO4J_DATABASE=neo4j

   LLAMA_CLOUD_API_KEY=<your-llama-cloud-key>
   HUGGINGFACEHUB_ACCESS_TOKEN=<your-hf-access-token>
   GEMINI_API_KEY=<your-gemini-key>
   ```

5. Launch the FastAPI server:
   ```bash
   python main.py
   ```
   *The API will start running at `http://127.0.0.1:8000`.*

---

### 2. Frontend Setup

1. Open a new terminal and navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in `frontend/`:
   ```env
   BACKEND_API_URL=http://127.0.0.1:8000
   ```

5. Launch the Streamlit web app:
   ```bash
   streamlit run app.py
   ```
   *The web interface will open at `http://localhost:8501`.*

---

## 🔑 Pre-seeded Default Accounts

Upon first launch, SQLite automatically seeds default demo accounts with password `password123`:

| Employee ID | Name | Role Tier | Access Level |
| :--- | :--- | :---: | :--- |
| `EMP-1042` | Ramesh | Tier 1 | Operator (Dashboard, AI Assistant, Blueprints, Tip Submission) |
| `EMP-2088` | Priya | Tier 2 | Engineer (Tip Approvals, Peer Review, Blueprints) |
| `EMP-9001` | Mr. Sharma | Tier 3 | Plant Manager / Admin (Full Access + Employee Management) |
| `EMP-2023` | Goutam | Tier 3 | Plant Manager / Admin (Full Access + Employee Management) |

---

## 📚 Technical Documentation

For in-depth architectural details, database schemas, and workflow sequence diagrams, refer to:
- 📖 [`ARCHITECTURE.md`](file:///d:/omniplant/ARCHITECTURE.md)

---
*OmniPlant.AI Engine — Industrial Knowledge & Operations Intelligence*
