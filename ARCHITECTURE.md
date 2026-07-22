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
        KGTab["Knowledge Graph & AI Chat View"]
        BlueTab["Interactive P&ID Blueprint View"]
        TipsTab["Employee Tips View"]
        EmpTab["Manage Employees View (Tier 3)"]
        NotifSidebar["Notification Drawer (Tier 2+ Peer Approvals)"]
        
        UI --> AuthTab
        UI --> KGTab
        UI --> BlueTab
        UI --> TipsTab
        UI --> EmpTab
        UI --> NotifSidebar
    end

    subgraph Backend_Layer ["Backend API Engine (FastAPI)"]
        API["FastAPI App (main.py:8000)"]
        AuthMw["Credential Middleware & Security"]
        RouterAuth["/api/auth (OAuth2 / JWT)"]
        RouterUsers["/api/users (RBAC Management)"]
        RouterIngest["/api/ingest (PDF, Tips & Data Ingestion)"]
        QueryPipeline["services/query_pipeline.py (Hybrid RAG)"]
        IngestPipeline["services/ingest_synthetic_pdfs.py"]
        TipPipeline["services/ingest_tips.py"]
        
        API --> AuthMw
        API --> RouterAuth
        API --> RouterUsers
        API --> RouterIngest
        RouterIngest --> IngestPipeline
        RouterIngest --> TipPipeline
        KGTab --> QueryPipeline
    end

    subgraph External_Services ["AI & Media Cloud Services"]
        LlamaParse["LlamaParse API (PDF Parser)"]
        HF_Embed["HuggingFace API (BAAI/bge-small-en - 384d)"]
        HF_LLM["HuggingFace / Qwen2.5-7B-Instruct (LLM Extraction & Synthesis)"]
        ImageKit["ImageKit.io CDN (P&ID Blueprints & Assets)"]
    end

    subgraph Database_Layer ["Hybrid Storage Layer"]
        SQLite[("SQLite Database (omniplant.db)\n• Users & Passwords\n• Pending Employee Tips\n• RBAC Tier Data")]
        Neo4j[("Neo4j Graph Database\n• Document & Chunk Nodes\n• Equipment & Part Graph\n• Approved Tip Nodes\n• 384d Vector Index (chunkEmbedding)")]
    end

    %% Communications
    UI -- "REST / HTTP (JSON / JWT Bearer)" --> API
    RouterAuth --> SQLite
    RouterUsers --> SQLite
    RouterIngest --> SQLite
    IngestPipeline --> LlamaParse
    IngestPipeline --> HF_Embed
    IngestPipeline --> HF_LLM
    IngestPipeline --> Neo4j
    TipPipeline --> HF_Embed
    TipPipeline --> Neo4j
    QueryPipeline --> HF_Embed
    QueryPipeline --> HF_LLM
    QueryPipeline --> Neo4j
    BlueTab -- "Fetch Assets" --> ImageKit
```

---

## 2. Component Details & Tech Stack

| Layer / Component | Technology Stack | Key Responsibilities |
| :--- | :--- | :--- |
| **Frontend UI** | Python, Streamlit, `streamlit_cookies_controller` | Renders user dashboards, P&ID visualizer, AI chat, employee tips, peer notification sidebar, RBAC tabs. |
| **Backend API Engine** | Python, FastAPI, Uvicorn, SQLAlchemy, Pydantic | Provides RESTful endpoints, handles JWT auth, background processing, peer tip approval handling. |
| **Relational Database** | SQLite (`omniplant.db`), SQLAlchemy ORM | Stores employee accounts, hashed credentials, pending tips (`PendingTip`), roles, and admin data. |
| **Graph & Vector Database**| Neo4j, Cypher, Neo4j Python Driver | Stores equipment knowledge graph nodes, relationships, text chunks, approved tips, and 384-d vector embeddings. |
| **Document Parser** | LlamaParse API | Converts complex PDF manuals and engineering documents into structured text/markdown chunks. |
| **Embedding Engine** | HuggingFace Inference API (`BAAI/bge-small-en`) | Generates dense 384-dimensional vector embeddings for chunk/tip indexes and query matching. |
| **LLM Reasoning Engine** | HuggingFace / `Qwen/Qwen2.5-7B-Instruct` | Extracts equipment graph entities/triplets and synthesizes diagnostic answers. |
| **Media CDN** | ImageKit.io | Hosts high-resolution P&ID blueprint image assets and equipment diagrams. |

---

## 3. Peer Maintenance Tip Approval & Ingestion Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Tech as Field Technician (Tier 1)
    actor Eng as Engineer / Admin (Tier 2/3)
    participant UI as Streamlit UI (Frontend)
    participant Router as FastAPI Ingestion Router
    participant DB as SQLite (omniplant.db)
    participant TipSvc as services/ingest_tips.py
    participant HF as HuggingFace (bge-small-en)
    participant Neo4j as Neo4j Graph DB

    Tech->>UI: Submit Maintenance Tip ("Check O-ring on Pump C-101")
    UI->>Router: POST /api/ingest/add_tip
    Router->>DB: Save PendingTip (status="Pending", approvals=0)
    Router-->>UI: Tip Submitted for Review
    
    Note over Eng, UI: Sidebar Drawer alerts Tier 2+ Engineers of pending review
    Eng->>UI: Click "Approve" on Notification Sidebar
    UI->>Router: POST /api/ingest/approve_tip (approver_id)
    Router->>DB: Increment approvals_count

    alt approvals_count < 2
        Router->>DB: Update approved_by list
        Router-->>UI: Approval recorded (Waiting for 2nd peer)
    else approvals_count >= 2
        Router->>DB: Update status = "Approved"
        Router->>TipSvc: Trigger process_tip(employee, tip_text)
        TipSvc->>HF: Generate 384d Embedding Vector
        TipSvc->>Neo4j: Create (t:Tip) Node + (t)-[:SUGGESTS]->(e:Equipment)
        TipSvc->>Neo4j: Index Tip embedding in `chunkEmbedding`
        Router-->>UI: Tip Fully Approved & Ingested into Graph!
    end
```

---

## 4. Hybrid RAG & Graph Retrieval Pipeline Sequence

When a user asks a maintenance or operational question, OmniPlant.AI combines dense vector similarity search across documents and approved tips with graph traversal to deliver context-aware answers.

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
    Neo4j-->>Pipeline: Top Relevant Text Chunks & Approved Tips
    
    Pipeline->>Neo4j: Graph Search: MATCH (e:Equipment {name: 'c-101'})-[r]-(neighbor) RETURN e, r, neighbor
    Neo4j-->>Pipeline: Equipment Subgraph, Connected Workorders & Approved Peer Tips
    
    Pipeline->>Pipeline: Combine Chunks + Subgraph Triplets + Workorder History + Peer Tips into Context Block
    Pipeline->>LLM_Synth: Generate Answer Prompt (Context + Question)
    LLM_Synth-->>Pipeline: Synthesized Response & Source Citations
    Pipeline-->>UI: Output Answer + Render Graph Visualizer
    UI-->>User: Display Response & Knowledge Graph Nodes
```

---

## 5. Entity-Relationship & Graph Database Schema

OmniPlant.AI utilizes a dual storage schema: **Relational Tables** for authentication, pending tips, and user roles, and a **Property Graph Schema** for knowledge graphs.

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

    PENDING_TIPS {
        int id PK
        string employee_id
        string employee_name
        string tip_text
        int approvals_count
        string approved_by "Comma-separated approver IDs"
        string status "Pending / Approved"
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
    class Tip {
        +string tip_id
        +string text
        +string submitted_by
        +float[] embedding
    }

    Document "1" -- "*" Chunk : HAS_CHUNK
    Chunk "*" -- "*" Equipment : MENTIONS
    Tip "*" -- "*" Equipment : SUGGESTS
    Equipment "1" -- "*" Workorder : HAS_WORKORDER
    Equipment "*" -- "*" Equipment : CONNECTED_TO
    Equipment "*" -- "*" Equipment : HAS_PART
    Equipment "*" -- "*" Equipment : GOVERNS
    Equipment "*" -- "*" Equipment : LOCATED_IN
    Equipment "*" -- "*" Equipment : MONITORS
    Equipment "*" -- "*" Equipment : CAUSES
```

---

## 6. Security, Authentication & Role-Based Access Control (RBAC)

OmniPlant.AI enforces strict Role-Based Access Control across three operational tiers. Authentication is managed via JWT OAuth2 bearer tokens, persisted locally using HTTP-only/Browser cookies.

```mermaid
flowchart TD
    Start([User Access Request]) --> CheckAuth{Is Authenticated?}
    CheckAuth -- No --> AuthView[Render Authentication Tab Only]
    CheckAuth -- Yes --> ReadTier[Extract User Role Tier]
    
    ReadTier --> TierCheck{Check Role Tier}
    
    TierCheck -- Tier 1 (Operator) --> T1[Access Allowed:\n• Knowledge Graph & AI\n• Interactive P&ID Blueprint\n• Other Information\n• Employee Tip Submission]
    TierCheck -- Tier 2 (Engineer) --> T2[Access Allowed:\n• Tier 1 Capabilities\n• Tip Peer Approval Drawer\n• Tip Ingestion to Graph\n• Workorder Updates]
    TierCheck -- Tier 3 (Plant Manager / Admin) --> T3[Access Allowed:\n• Tier 1 & 2 Capabilities\n• Full Employee Management\n• Role Tier Assignment\n• System Ingestion Trigger]
```

---

## 7. Guidelines for Rendering Architectural Diagrams

- **Mermaid.js**: Copy any of the ```mermaid code blocks in this document into [Mermaid Live Editor](https://mermaid.live) or render directly in GitHub/VSCode.
- **Draw.io / Lucidchart**: Import the Mermaid syntax directly via *Insert > Advanced > Mermaid*.

---
*Document Version: 1.1.0 | System Name: OmniPlant.AI Production Engine*
