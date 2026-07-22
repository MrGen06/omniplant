# OmniPlant.AI — System Architecture & Diagram Specification

Welcome to the architectural reference document for **OmniPlant.AI**. This document provides a complete technical breakdown, database schemas, component interactions, data flow sequences, and renderable **Mermaid.js** architectural diagrams to guide engineers, architects, and technical designers.

---

## 1. High-Level System Architecture

OmniPlant.AI is built on a **decoupled, modular architecture** integrating a Streamlit frontend with a FastAPI backend engine, a hybrid storage layer (SQLite relational DB + Neo4j Graph & Vector DB), external cloud services (ImageKit CDN, LlamaParse, HuggingFace Inference API), and LLM reasoning models.

```mermaid
graph TB
    subgraph Frontend_Layer ["Client & Frontend Tier (Streamlit)"]
        UI["Streamlit Web App (app.py:8051)"]
        AuthTab["Auth View / Cookie Mgmt"]
        DashTab["Tier Dashboard View"]
        KGTab["Knowledge Graph & AI Chat View"]
        BlueTab["Interactive P&ID Blueprint View"]
        EmpTab["Manage Employees View (Tier 3)"]
        
        UI --> AuthTab
        UI --> DashTab
        UI --> KGTab
        UI --> BlueTab
        UI --> EmpTab
    end

    subgraph Backend_Layer ["Backend API Engine (FastAPI)"]
        API["FastAPI App (main.py:8000)"]
        AuthMw["Credential Middleware & Security"]
        RouterAuth["/api/auth (OAuth2 / JWT)"]
        RouterUsers["/api/users (RBAC Management)"]
        RouterIngest["/api/ingest (PDF & Data Ingestion)"]
        QueryPipeline["services/query_pipeline.py (Hybrid RAG)"]
        IngestPipeline["services/ingest_synthetic_pdfs.py"]
        
        API --> AuthMw
        API --> RouterAuth
        API --> RouterUsers
        API --> RouterIngest
        RouterIngest --> IngestPipeline
        KGTab --> QueryPipeline
    end

    subgraph External_Services ["AI & Media Cloud Services"]
        LlamaParse["LlamaParse API (PDF Parser)"]
        HF_Embed["HuggingFace API (BAAI/bge-small-en - 384d)"]
        HF_LLM["HuggingFace / Qwen2.5-7B-Instruct (LLM Extraction & Synthesis)"]
        ImageKit["ImageKit.io CDN (P&ID Blueprints & Assets)"]
    end

    subgraph Database_Layer ["Hybrid Storage Layer"]
        SQLite[("SQLite Database (omniplant.db)\n• Users & Passwords\n• Employee Profiles\n• RBAC Tier Data")]
        Neo4j[("Neo4j Graph Database\n• Document & Chunk Nodes\n• Equipment & Part Graph\n• 384d Vector Index (chunkEmbedding)")]
    end

    %% Communications
    UI -- "REST / HTTP (JSON / JWT Bearer)" --> API
    RouterAuth --> SQLite
    RouterUsers --> SQLite
    IngestPipeline --> LlamaParse
    IngestPipeline --> HF_Embed
    IngestPipeline --> HF_LLM
    IngestPipeline --> Neo4j
    QueryPipeline --> HF_Embed
    QueryPipeline --> HF_LLM
    QueryPipeline --> Neo4j
    BlueTab -- "Fetch Assets" --> ImageKit
```

---

## 2. Component Details & Tech Stack

| Layer / Component | Technology Stack | Key Responsibilities |
| :--- | :--- | :--- |
| **Frontend UI** | Python, Streamlit, `streamlit_cookies_controller` | Renders user dashboards, P&ID visualizer, AI chat, session cookies, RBAC tabs. |
| **Backend API Engine** | Python, FastAPI, Uvicorn, SQLAlchemy, Pydantic | Provides RESTful endpoints, handles JWT auth, background processing, lifespan lifecycle. |
| **Relational Database** | SQLite (`omniplant.db`), SQLAlchemy ORM | Stores employee accounts, hashed credentials, roles, and administrative data. |
| **Graph & Vector Database**| Neo4j, Cypher, Neo4j Python Driver | Stores equipment knowledge graph nodes, relationships, text chunks, and 384-d vector embeddings. |
| **Document Parser** | LlamaParse API | Converts complex PDF manuals and engineering documents into structured text/markdown chunks. |
| **Embedding Engine** | HuggingFace Inference API (`BAAI/bge-small-en`) | Generates dense 384-dimensional vector embeddings for chunk index and query matching. |
| **LLM Reasoning Engine** | HuggingFace / `Qwen/Qwen2.5-7B-Instruct` | Extracts equipment graph entities/triplets and synthesizes diagnostic answers. |
| **Media CDN** | ImageKit.io | Hosts high-resolution P&ID blueprint image assets and equipment diagrams. |

---

## 3. Data Ingestion Pipeline Sequence

The document ingestion pipeline processes engineering manuals and industrial documentation, converting them into structured knowledge graph nodes and vector embeddings.

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Plant Admin / Engineer
    participant Frontend as Streamlit UI
    participant Router as FastAPI Ingestion Router
    participant LP as LlamaParse Service
    participant HF as HuggingFace (bge-small-en)
    participant LLM as Qwen2.5-7B LLM
    participant Neo4j as Neo4j Graph DB

    Admin->>Frontend: Upload Industrial PDF Document
    Frontend->>Router: POST /api/ingest/upload (PDF File)
    Router->>LP: Send PDF file for deep parsing
    LP-->>Router: Markdown & Text Chunks returned
    
    loop For Each Text Chunk
        Router->>HF: Request Vector Embedding (bge-small-en)
        HF-->>Router: 384-dim Embedding Vector
        Router->>LLM: Prompt for Entity & Relationship Triplets
        LLM-->>Router: JSON (Entities: Equipment/Part, Relations: HAS_PART/CONNECTED_TO/etc.)
    end
    
    Router->>Neo4j: Create (d:Document) Node
    Router->>Neo4j: Create (c:Chunk) Nodes + (d)-[:HAS_CHUNK]->(c)
    Router->>Neo4j: Create (e:Equipment) Nodes + (c)-[:MENTIONS]->(e)
    Router->>Neo4j: Create Entity Relationships (e1)-[:CONNECTED_TO|GOVERNS|CAUSES]->(e2)
    Router->>Neo4j: Update 384d Vector Index `chunkEmbedding`
    Router-->>Frontend: Ingestion Status: Success (Document & Graph Synced)
    Frontend-->>Admin: Visual Confirmation & Ingestion Summary
```

---

## 4. Hybrid RAG & Graph Retrieval Pipeline Sequence

When a user asks a maintenance or operational question, OmniPlant.AI combines dense vector similarity search with graph traversal to deliver context-aware answers.

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator / Engineer
    participant UI as Streamlit Chat Interface
    participant Pipeline as services/query_pipeline.py
    participant HF_Embed as HF Embedding API
    participant LLM_Extract as LLM Equipment Extractor
    participant Neo4j as Neo4j Graph DB
    participant LLM_Synth as LLM Answer Synthesizer

    User->>UI: Submit Query (e.g., "What is the history of workorder on C-101?")
    UI->>Pipeline: Invoke pipeline(query)
    
    par Dual Vector & Entity Extraction
        Pipeline->>HF_Embed: Generate Embedding for Query (384d)
        HF_Embed-->>Pipeline: Query Vector
    and Equipment Entity Extraction
        Pipeline->>LLM_Extract: Extract Equipment ID from Query
        LLM_Extract-->>Pipeline: JSON {"equipment": "C-101"}
    end

    Pipeline->>Neo4j: Vector Search: CALL db.index.vector.queryNodes('chunkEmbedding', 3, $query_vector)
    Neo4j-->>Pipeline: Top 3 Relevant Text Chunks
    
    Pipeline->>Neo4j: Graph Search: MATCH (e:Equipment {name: 'c-101'})-[r]-(neighbor) RETURN e, r, neighbor
    Neo4j-->>Pipeline: Equipment Subgraph & Connected Workorders / Parts
    
    Pipeline->>Pipeline: Combine Chunks + Subgraph Triplets + Workorder History into Context Block
    Pipeline->>LLM_Synth: Generate Answer Prompt (Context + Question)
    LLM_Synth-->>Pipeline: Synthesized Response & Source Citations
    Pipeline-->>UI: Output Answer + Render Graph Visualizer
    UI-->>User: Display Response & Knowledge Graph Nodes
```

---

## 5. Entity-Relationship & Graph Database Schema

OmniPlant.AI utilizes a dual storage schema: **Relational Tables** for authentication/users, and a **Property Graph Schema** for knowledge graphs.

### A. Relational Database Schema (SQLite `omniplant.db`)

```mermaid
erDiagram
    USERS {
        int id PK
        string employee_id UK "e.g., EMP-1042"
        string name "e.g., Ramesh"
        int role_tier "1: Operator, 2: Engineer, 3: Admin"
        string password_hash "Bcrypt / Hashed Password"
        datetime created_at
    }
```

### B. Graph Database Schema (Neo4j)

```mermaid
classDiagram
    class Document {
        +string name
        +string url
    }
    class Chunk {
        +string chunk_id
        +string text
        +float[] embedding
    }
    class Equipment {
        +string id
        +string name
        +string label
        +float x_coord
        +float y_coord
    }
    class Workorder {
        +string id
        +string date
        +string status
        +string description
    }

    Document "1" -- "*" Chunk : HAS_CHUNK
    Chunk "*" -- "*" Equipment : MENTIONS
    Equipment "1" -- "*" Workorder : HAS_WORKORDER
    Equipment "*" -- "*" Equipment : CONNECTED_TO
    Equipment "*" -- "*" Equipment : HAS_PART
    Equipment "*" -- "*" Equipment : GOVERNS
    Equipment "*" -- "*" Equipment : LOCATED_IN
    Equipment "*" -- "*" Equipment : MONITORS
    Equipment "*" -- "*" Equipment : CAUSES
```

#### Supported Graph Relationship Types:
- `HAS_CHUNK`: Links a Document to its constituent text chunks.
- `MENTIONS`: Connects a text chunk to specific industrial equipment entities.
- `CONNECTED_TO`: Connects two equipment components physically or logically.
- `HAS_PART`: Hierarchical relationship between assembly and subcomponents.
- `GOVERNS`: Control relationships (e.g., control valve governing flow to a pump).
- `LOCATED_IN`: Spatial placement (e.g., Equipment located in Zone B).
- `MONITORS`: Sensor measurement (e.g., pressure sensor monitoring a boiler).
- `REQUIRES`: Operational prerequisite.
- `CAUSES`: Diagnostic fault relationship (e.g., bearing failure causes vibration).
- `INDICATES`: Telemetry indicator relationship.

---

## 6. Security, Authentication & Role-Based Access Control (RBAC)

OmniPlant.AI enforces strict Role-Based Access Control across three operational tiers. Authentication is managed via JWT OAuth2 bearer tokens, persisted locally using HTTP-only/Browser cookies.

```mermaid
flowchart TD
    Start([User Access Request]) --> CheckAuth{Is Authenticated?}
    CheckAuth -- No --> AuthView[Render Authentication Tab Only]
    CheckAuth -- Yes --> ReadTier[Extract User Role Tier]
    
    ReadTier --> TierCheck{Check Role Tier}
    
    TierCheck -- Tier 1 (Operator) --> T1[Access Allowed:\n• Tier Dashboard\n• Knowledge Graph & AI\n• Interactive P&ID Blueprint\n• Other Information]
    TierCheck -- Tier 2 (Engineer) --> T2[Access Allowed:\n• Tier 1 Capabilities\n• Data & Tip Ingestion\n• Workorder Updates]
    TierCheck -- Tier 3 (Plant Manager / Admin) --> T3[Access Allowed:\n• Tier 1 & 2 Capabilities\n• Full Employee Management\n• Role Tier Assignment\n• System Ingestion Trigger]
```

### RBAC Tier Matrix

| Feature / Action | Tier 1 (Operator) | Tier 2 (Engineer) | Tier 3 (Plant Manager / Admin) |
| :--- | :---: | :---: | :---: |
| View P&ID Interactive Blueprint | ✅ | ✅ | ✅ |
| Query Knowledge Graph & AI Assistant | ✅ | ✅ | ✅ |
| View Equipment Technical Documentation | ✅ | ✅ | ✅ |
| Submit Maintenance Tips & Workorders | ❌ | ✅ | ✅ |
| Trigger Manual PDF Document Ingestion | ❌ | ❌ | ✅ |
| Register New Employees / Users | ❌ | ❌ | ✅ |
| Modify User Roles & Permissions | ❌ | ❌ | ✅ |

---

## 7. Deployment & Network Topology

```mermaid
graph LR
    subgraph Client_Side ["Client Network"]
        Browser["User Web Browser"]
    end

    subgraph Edge_Gateway ["App Gateway / Reverse Proxy"]
        Port8051["Streamlit UI (Port 8051)"]
        Port8000["FastAPI Engine (Port 8000)"]
    end

    subgraph Internal_Network ["Internal Service Mesh"]
        SQLiteDB[("SQLite Database")]
        Neo4jCluster[("Neo4j Graph Database (Bolt/7687)")]
    end

    subgraph External_Cloud ["Cloud Providers"]
        HFCloud["HuggingFace Inference Endpoints"]
        LlamaCloud["LlamaParse Cloud API"]
        ImageKitCloud["ImageKit Media CDN"]
    end

    Browser -- "HTTP / Port 8051" --> Port8051
    Port8051 -- "Internal REST / Port 8000" --> Port8000
    Port8000 -- "SQLAlchemy File Driver" --> SQLiteDB
    Port8000 -- "Bolt Protocol (TLS / SSL)" --> Neo4jCluster
    Port8000 -- "HTTPS REST API" --> HFCloud
    Port8000 -- "HTTPS REST API" --> LlamaCloud
    Port8051 -- "HTTPS Asset Fetch" --> ImageKitCloud
```

---

## 8. Guidelines for Rendering Architectural Diagrams

When exporting or creating visual diagrams for presentations, documentation, or software design reviews, adhere to the following conventions:

1. **Colors & Themes**:
   - **Frontend (Streamlit)**: Primary Accent `#FF4B4B` / Dark Background `#0E1117`.
   - **Backend (FastAPI)**: Teal `#009688` / Dark Slate `#1A202C`.
   - **Graph Database (Neo4j)**: Neo4j Blue `#008CC1` / Node Accents `#4C9AFF`.
   - **Relational DB (SQLite)**: Emerald Green `#2ECC71`.
   - **AI / Cloud Services**: Purple `#8E44AD`.

2. **Diagram Tool Compatibility**:
   - **Mermaid.js**: Copy any of the ```mermaid code blocks in this document into [Mermaid Live Editor](https://mermaid.live) or render directly in GitHub/VSCode.
   - **Draw.io / Lucidchart**: Import the Mermaid syntax directly via *Insert > Advanced > Mermaid*.
   - **PlantUML**: The component and ER breakdown can be converted using standard PlantUML class and sequence structures.

---
*Document Version: 1.0.0 | System Name: OmniPlant.AI Production Engine*
