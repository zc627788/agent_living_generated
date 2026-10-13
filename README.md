# PRD Agent Studio — Knowledge-Grounded Requirements Workspace

**Collect a product brief, consult a knowledge base, and export a structured requirements document from one workspace.**

This full-stack project connects a conversational requirements interface with document management, retrieval, graph-based exploration and Word-document export. It is a portfolio implementation for internal product, operations and knowledge-work workflows.

## What the workspace does

| User task | Implementation |
| --- | --- |
| Capture a project request | Conversation flow, structured fields and PRD preview |
| Maintain reference material | Upload, versions, rebuild jobs and retrieval checks |
| Explore indexed knowledge | Graph index selection, entity/relationship views and community reports |
| Deliver a reusable document | Markdown-to-DOCX export |

## Technology and structure

- Frontend: Next.js, React, TypeScript, Ant Design and ahooks.
- Backend: FastAPI, LangChain/LangGraph integration and Python document export.
- Retrieval/storage: Qdrant, GraphRAG artifacts, MinIO, PostgreSQL or SQLite.
- Model integrations: Qwen chat and embedding services, configured by the operator.
- `frontend/`: application UI; `backend/app/`: API and services; `docs/`: project manual; `scripts/`: Windows startup helpers.

## Local setup

Provision the dependencies you need first: Python 3.10+, Node.js 20+, Qdrant, MinIO, a database and authorized model credentials. Graph-building functionality additionally requires its CLI and compatible index assets.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ../frontend
npm ci
```

Configure local environment variables using the names documented in `backend/app/core/config.py` and [the project manual](docs/PROJECT_MANUAL.md). Keep secrets outside version control. Model calls and storage services must be configured and tested before presenting an end-to-end deployment as operational.

To start components manually:

```powershell
# Terminal 1, from backend/
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Terminal 2, from frontend/
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
npm run dev
```

The Windows startup scripts are available for development, but inspect them before use: the backend helper can stop processes occupying its configured port. A reload-free backend is preferable for a stable local demonstration.

## Verification and project limits

The repository contains code for retrieval, graph querying, knowledge jobs and DOCX export. Presence of these integrations does not establish answer accuracy, model quality or production readiness. A real acceptance test requires configured services, approved source documents and a representative question set. The interface is currently primarily Chinese; the portfolio description is in English.

For a client project, define document sources, access controls, data retention, model/provider budget, expected PRD format and retrieval evaluation criteria first. This repository does not claim proprietary client results or guaranteed productivity improvements.

[Detailed manual](docs/PROJECT_MANUAL.md) · [Previous Chinese setup notes](docs/legacy-readme.zh-CN.md)
