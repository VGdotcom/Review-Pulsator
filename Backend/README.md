---
title: Review Pulsator Backend
emoji: ⚡
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# 🚀 Review Pulsator — Production AI Backend Engine

This repository hosts the backend REST API engine for **Review Pulsator**, deployed on **Hugging Face Spaces** using Docker containerization.

## 🏛️ Architecture & Deployment

* **Frontend Hosting**: Hosted on **Vercel** (`/dashboard` static UI bundle with Vercel proxy rewrites).
* **Backend API Hosting**: Hosted on **Hugging Face Spaces** (`PORT=7860`), executing the Groq Llama 3.3 70B inference pipeline and Google Workspace MCP delivery layer.

## 📡 REST API Endpoints

* `GET /api/status`: Check engine health, model parameters, and total archived reports.
* `GET /api/report`: Retrieve the latest validated weekly pulse summary (`≤250 words`).
* `GET /api/analytics`: Fetch 4-stage pipeline metrics, star rating distribution, and domain severity index.
* `GET /api/reports`: List all historical delivered pulse reports.
* `POST /api/trigger_pulse`: Trigger live LLM synthesis and publish directly to Google Docs & Gmail via MCP.

## 🔐 Environment Configuration

In your Hugging Face Space settings (**Settings $\rightarrow$ Variables and secrets**), configure:
* `GROQ_API_KEY`: Your Groq API key (`llama-3.3-70b-versatile`).
* `PULSATOR_TARGET_EMAIL`: Target recipient email alias for weekly drafts.
* `PULSATOR_GDOCS_DOC_ID`: Production Google Doc ID for chronological report appending.
* `MCP_SERVER_URL`: Remote Streamable HTTP endpoint (`https://vgdotcom-google-workspace-mcp.hf.space/sse`).

## 🛠️ Local Development

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run server locally on port 8080 (or custom $PORT)
PORT=8080 python3 dashboard_server.py
```
