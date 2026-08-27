# 🚀 DeepTutor — Production Cloud Deployment Guide

This document provides a comprehensive, step-by-step guide for deploying **DeepTutor** (FastAPI backend + React Vite frontend + Pinecone vector database + Google Gemini VLM) to production cloud environments.

---

## 📑 Table of Contents
1. [Architecture Overview & Cloud Topology](#-architecture-overview--cloud-topology)
2. [Prerequisites & External Cloud Services](#-prerequisites--external-cloud-services)
3. [Environment Variables Reference](#-environment-variables-reference)
4. [Deployment Option 1: Platform-as-a-Service (Render / Railway + Vercel)](#-deployment-option-1-platform-as-a-service-render--railway--vercel-recommended)
5. [Deployment Option 2: Docker Compose on Cloud VM (AWS EC2 / DigitalOcean / GCP)](#-deployment-option-2-docker-compose-on-cloud-vm-aws-ec2--digitalocean--gcp)
6. [Pinecone Cloud Vector Database Setup](#-pinecone-cloud-vector-database-setup)
7. [Running the VLM Textbook Ingestion in Cloud](#-running-the-vlm-textbook-ingestion-in-cloud)
8. [CORS, Domain & SSL Configuration](#-cors-domain--ssl-configuration)
9. [Health Checks & Verification](#-health-checks--verification)
10. [Troubleshooting & FAQs](#-troubleshooting--faqs)

---

## 🏗️ Architecture Overview & Cloud Topology

```mermaid
flowchart TD
    Client[User Browser / Mobile] -->|HTTPS| CloudFront[CDN / SSL / Reverse Proxy]
    
    subgraph Frontend Hosting [Vercel / Netlify / Nginx]
        FE[React 19 + TypeScript SPA]
    end
    
    subgraph Backend Cloud [Render / Railway / AWS EC2]
        API[FastAPI Backend - Gunicorn/Uvicorn]
        DB[(SQLite / PostgreSQL RDS)]
        DiskStore[(Local Disk / EBS Volume: uploads & cache)]
    end
    
    subgraph External Cloud Services
        Gemini[Google Gemini 2.0/2.5 Flash LLM & VLM]
        Pinecone[(Pinecone Cloud Vector DB: 3072-dim)]
        S3[(AWS S3 / Cloudflare R2 Document Store)]
    end

    CloudFront --> FE
    FE -->|REST API & SSE Streams| API
    API <--> DB
    API <--> DiskStore
    API <--> Gemini
    API <--> Pinecone
    API <--> S3
```

---

## 🔑 Prerequisites & External Cloud Services

Before deploying, ensure you have credentials for the following cloud services:

1. **Google AI Studio (Gemini API)**:
   - Create an API key at [Google AI Studio](https://aistudio.google.com/).
   - Models used: `gemini-2.0-flash` (Chat/Reasoning), `gemini-2.5-flash` (Vision VLM), and `models/text-embedding-004` (3072-dim embeddings).
2. **Pinecone Vector Database**:
   - Create a free or standard account at [Pinecone Console](https://app.pinecone.io/).
   - Create two serverless indexes with dimension `3072` and metric `cosine`:
     - Index 1: `textbook` (for indexed textbooks)
     - Index 2: `deeptutor` (for user-uploaded chat documents)
3. **AWS S3 or Cloudflare R2 (Optional for File Uploads)**:
   - S3 Bucket for persistent storage of uploaded PDF documents.
4. **Serper.dev API (Optional for AI Image Search)**:
   - API key from [serper.dev](https://serper.dev) for real-world visual verification.

---

## ⚙️ Environment Variables Reference

### 1. Backend (`.env` or Cloud Dashboard Environment)

```ini
# ── Server & Security ────────────────────────────────────────────────────────
PORT=8000
DEBUG=False
SECRET_KEY=generate-a-strong-random-64-character-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# ── Database ─────────────────────────────────────────────────────────────────
# SQLite (default for single-instance VM):
DATABASE_URL=sqlite+aiosqlite:///./deep_tutor.db
# PostgreSQL (recommended for multi-instance scaling):
# DATABASE_URL=postgresql+asyncpg://user:password@host:5432/deeptutor

# ── LLM Provider (Google Gemini) ─────────────────────────────────────────────
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...your-gemini-api-key
GEMINI_CHAT_MODEL=gemini-2.0-flash
GEMINI_TIMEOUT=30

# ── Embeddings (Google Gemini 3072-dim) ──────────────────────────────────────
EMBEDDING_PROVIDER=gemini
GEMINI_EMBED_MODEL=models/text-embedding-004

# ── Cloud Vector Store (Pinecone) ───────────────────────────────────────────
VECTOR_STORE_BACKEND=pinecone
PINECONE_API_KEY=pcsk_...your-pinecone-api-key
PINECONE_INDEX_NAME=textbook
PINECONE_TEXTBOOK_INDEX=textbook
PINECONE_CHAT_INDEX=deeptutor
PINECONE_ENVIRONMENT=us-east-1

# ── Graph Store ─────────────────────────────────────────────────────────────
GRAPH_STORE_BACKEND=json_kv
LIGHTRAG_DATA_DIR=./lightrag_data

# ── VLM (Vision-Language Model) Document Extraction ─────────────────────────
ENABLE_VLM_PARSER=True
GEMINI_VLM_MODEL=gemini-2.5-flash
VLM_CACHE_DIR=./vlm_cache
VLM_MAX_CONCURRENT_PAGES=4
VLM_MAX_PAGES_PER_DOC=50

# ── AWS S3 Document Storage (Optional) ──────────────────────────────────────
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET_NAME=deeptutor-uploads

# ── Serper Web Image Search (Optional) ──────────────────────────────────────
SERPER_API_KEY=
```

### 2. Frontend (`frontend/.env.production` or Vercel Environment)

```ini
# Backend API Base URL (Do not include trailing slash)
VITE_API_URL=https://api.yourdomain.com
```

---

## 🚢 Deployment Option 1: Platform-as-a-Service (Render / Railway + Vercel) [Recommended]

This is the fastest, zero-devops production setup.

### Step 1: Deploy Backend to Render or Railway

#### Via Render:
1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New > Web Service**.
2. Connect your Git repository.
3. Set the following settings:
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3` (or `Docker`)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT --timeout 120`
4. Add the backend Environment Variables from the list above.
5. *(Optional)* Add a Persistent Disk mounted to `/app/uploads` and `/app/vlm_cache` so uploads persist across restarts.
6. Click **Create Web Service**. Note your backend URL (e.g. `https://deeptutor-backend.onrender.com`).

#### Via Railway:
1. Go to [Railway.app](https://railway.app/) and click **New Project > Deploy from GitHub repo**.
2. Select your repository.
3. In service settings, set **Root Directory** to `/backend`.
4. Add all backend Environment Variables under the **Variables** tab.
5. Under **Networking**, generate a public domain (e.g. `https://deeptutor-api.up.railway.app`).

---

### Step 2: Deploy Frontend to Vercel or Netlify

#### Via Vercel:
1. Go to [Vercel Dashboard](https://vercel.com/dashboard) and click **Add New > Project**.
2. Import your GitHub repository.
3. Configure the build settings:
   - **Framework Preset**: `Vite`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. In **Environment Variables**, add:
   - `VITE_API_URL`: `https://your-backend-url.onrender.com` (your backend URL from Step 1).
5. Click **Deploy**.

---

## 🐳 Deployment Option 2: Docker Compose on Cloud VM (AWS EC2 / DigitalOcean / GCP)

Deploy the entire stack with a single command on any Linux VM (Ubuntu 22.04 LTS / 24.04 LTS).

### Step 1: Provision Cloud VM
- Recommended specs: **2 vCPU, 4 GB RAM, 30 GB SSD** (AWS `t3.medium`, DigitalOcean `$24/mo Droplet`, or GCP `e2-medium`).
- Open ports: `80` (HTTP), `443` (HTTPS), `22` (SSH).

### Step 2: Install Docker & Docker Compose on the VM
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg git

# Install Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Step 3: Clone Repository & Configure Environment
```bash
# Clone the repository
git clone https://github.com/your-org/DeepTutor.git /opt/deeptutor
cd /opt/deeptutor

# Create .env file with your production credentials
cp backend/.env.example .env
nano .env
```

### Step 4: Build & Launch Containers
```bash
# Build and start all services in detached mode
docker compose up --build -d

# Check status
docker compose ps

# View live backend logs
docker compose logs -f backend
```

---

## 🌲 Pinecone Cloud Vector Database Setup

DeepTutor uses **Pinecone Serverless** for high-speed sub-millisecond semantic retrieval.

### Creating the Indexes in Pinecone Console:

1. Log in to [Pinecone Console](https://app.pinecone.io/).
2. Click **Create Index**:
   - **Index Name**: `textbook`
   - **Dimensions**: `3072` *(matches Gemini `models/text-embedding-004`)*
   - **Metric**: `cosine`
   - **Cloud Provider**: `AWS` / `GCP` (Region: `us-east-1`)
3. Create a second index for user uploaded chats:
   - **Index Name**: `deeptutor`
   - **Dimensions**: `3072`
   - **Metric**: `cosine`
4. Copy your **API Key** from the API Keys tab and set it as `PINECONE_API_KEY` in your `.env`.

---

## 📚 Running the VLM Textbook Ingestion in Cloud

Once your backend is deployed and connected to Pinecone, populate the textbook knowledge base using Google Gemini Flash VLM:

```bash
# SSH into your VM or open Render/Railway shell:
cd /opt/deeptutor/backend  # or cd backend

# Optional: Clear any old textbook namespaces from Pinecone
python scripts/clear_pinecone_textbook.py

# Run VLM Multimodal Ingestion for all 3 SSLC textbooks (Physics, Chemistry, Maths):
python scripts/ingest_textbooks_vlm.py --subject all --concurrency 5 --dpi 180
```

> **Note on VLM Ingestion:**
> The script renders each page image at 180 DPI, feeds it to `gemini-2.5-flash` to extract structured Markdown, tables, diagrams, and LaTeX formulas, and computes 3072-dimensional embeddings directly upserted into the Pinecone `textbook` index.

---

## 🔒 CORS, Domain & SSL Configuration

### Backend CORS Configuration
DeepTutor allows all cross-origin requests by default in `backend/app/main.py`. For strict production locking, you can specify your frontend domain:

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",
        "https://www.yourdomain.com",
        "https://deeptutor.vercel.app",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Free SSL with Let's Encrypt (Nginx on VM)
If deploying via VM, install Certbot to secure your domain with free automated SSL certificates:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d api.yourdomain.com
```

---

## 🩺 Health Checks & Verification

After deployment, test that all endpoints and cloud integrations are functioning:

| Test Target | URL / Command | Expected Response |
|---|---|---|
| **Backend Health** | `GET https://api.yourdomain.com/api/health` | `{"status": "ok", "app": "Deep Tutor API"}` |
| **OpenAPI Docs** | `GET https://api.yourdomain.com/docs` | Swagger UI Interface |
| **Pinecone Connection** | `GET https://api.yourdomain.com/api/documents/topic/general/graph` | `{"topic_id": "general", "graph": {...}}` |
| **Frontend UI** | `GET https://yourdomain.com/` | Landing & Login Page |

---

## ❓ Troubleshooting & FAQs

### 1. `401 Unauthorized` on Chat Stream
- **Cause**: JWT access token missing or expired.
- **Fix**: Ensure the frontend sends `Authorization: Bearer <token>` header in requests. Logging in generates a fresh 7-day token.

### 2. `Pinecone ApiException: (404) Index not found`
- **Cause**: Index name mismatch or incorrect API key.
- **Fix**: Ensure index names `textbook` and `deeptutor` exist in your Pinecone dashboard and dimension is set to `3072`.

### 3. File Uploads Disappear on Container Restart
- **Cause**: Running containers without persistent volume mounts.
- **Fix**: Use Docker volumes (as defined in `docker-compose.yml`) or configure AWS S3 via `S3_BUCKET_NAME`.

### 4. VLM Ingestion Rate Limit (429)
- **Cause**: Exceeding Gemini API RPM (Requests Per Minute).
- **Fix**: Adjust concurrency down in the script: `python scripts/ingest_textbooks_vlm.py --concurrency 3`.
