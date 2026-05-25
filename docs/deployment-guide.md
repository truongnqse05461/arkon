# Deployment & Run Guide

This document details how to run Arkon in production using Docker Compose or configure a local development environment.

---

## 💻 System Requirements

Recommended configurations based on user team size:

| Parameter | **Starter** (1-20 users) | **Team** (20-100 users) | **Enterprise** (100+ users) |
|---|:---:|:---:|:---:|
| **vCPU** | 2 cores | 4 cores | 8+ cores |
| **RAM** | 4 GB | 8 GB | 16+ GB |
| **Storage** | 40 GB SSD | 100 GB SSD | 250+ GB NVMe SSD |
| **OS** | Ubuntu 22.04+ | Ubuntu 22.04+ | Ubuntu 22.04+ |

> **Note:** RAM is the primary bottleneck because workers load large context windows during LLM operations. All AI inference is run externally, so **no GPU is required**.

---

## 🐋 Option A: Production Deployment (Docker Compose)

### 📋 Prerequisites
1. **Software:** Docker Engine 24+ and Docker Compose v2+ installed.
2. **DNS & HTTPS:** A public domain pointing to your server IP. **HTTPS is required for OAuth 2.1 authentication in Claude.**
3. **SSL Certificate:** A valid TLS certificate (e.g. Let's Encrypt).
4. **Reverse Proxy:** Nginx configured to route traffic to the containers.

### 🚀 Step 1: Clone and Configure
1. Clone the repository:
   ```bash
   git clone https://github.com/nduckmink/arkon.git
   cd arkon
   ```
2. Copy the Docker env template:
   ```bash
   cp .env.docker.example .env.docker
   ```
3. Edit [.env.docker.example](file:///d:/workspace/src/truongnqse05461/arkon/.env.docker.example) to fill in:
   * `SECRET_KEY`: Generate using `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
   * `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD`.
   * `DATABASE_URL` and PostgreSQL passwords.
   * `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY`.
   * `NEXT_PUBLIC_API_URL`: Set to `https://arkon.yourcompany.com`.
   * `MINIO_PUBLIC_ENDPOINT`: Set to `minio.yourcompany.com`.

### ⚡ Step 2: Start Containers
Start the multi-container stack, defined in [docker-compose.yml](file:///d:/workspace/src/truongnqse05461/arkon/docker-compose.yml):
```bash
docker compose --env-file .env.docker up -d --build
```
This boots up:
* `arkon_postgres` (PostgreSQL 16 + pgvector)
* `arkon_redis` (Arq queue)
* `arkon_minio` (S3 storage)
* `arkon_api` (FastAPI backend + MCP)
* `arkon_worker` (Wiki ingestion worker)
* `arkon_worker_skills` (Skills compiler)
* `arkon_frontend` (Next.js portal)

Run migrations:
```bash
docker exec arkon_api alembic upgrade head
```

### 🔒 Step 3: Nginx Reverse Proxy Setup
Add this Nginx configuration at `/etc/nginx/sites-available/arkon`:

```nginx
# API + MCP server SSL
server {
    listen 443 ssl http2;
    server_name arkon.yourcompany.com;

    ssl_certificate     /etc/letsencrypt/live/arkon.yourcompany.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/arkon.yourcompany.com/privkey.pem;

    client_max_body_size 100M;

    # MCP endpoint (Streamable HTTP — disable buffering)
    location /mcp {
        proxy_pass http://127.0.0.1:5055;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;   # critical for OAuth https:// URLs
        proxy_set_header Connection        "";
        proxy_read_timeout 300s;
    }

    # Portal UI & API
    location / {
        proxy_pass http://127.0.0.1:5055;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
```

---

## 💻 Option B: Local Development Environment

### 📋 Prerequisites
* Python 3.11 – 3.14
* Node.js 20+
* Local running instances of PostgreSQL (with pgvector), Redis, and MinIO.

### ⚙️ Step 1: Start Infrastructure
You can boot these via local Docker containers:
```bash
docker run -d --name arkon-pg -p 5432:5432 -e POSTGRES_USER=arkon -e POSTGRES_PASSWORD=arkon_secret -e POSTGRES_DB=arkon pgvector/pgvector:pg16
docker run -d --name arkon-redis -p 6379:6379 redis:7-alpine
docker run -d --name arkon-minio -p 9000:9000 -p 9001:9001 -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin123 minio/minio server /data --console-address ":9001"
```

### 🐍 Step 2: Python Backend setup
1. Copy the local env template:
   ```bash
   cp .env.local.example .env.local
   ```
2. Build environment and install dependencies:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate

   pip install -e ".[dev]"
   alembic upgrade head
   ```
3. Run services in separate terminals:
   * **Terminal 1 (API Server):**
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port 5055 --reload
     ```
   * **Terminal 2 (Wiki Worker):**
     ```bash
     python -m arq app.worker.WorkerSettings
     ```
   * **Terminal 3 (Skills Worker):**
     ```bash
     python -m arq app.worker.SkillWorkerSettings
     ```

### ⚛️ Step 3: Frontend setup
1. Open a new terminal:
   ```bash
   cd frontend
   npm install
   ```
2. Create `frontend/.env.local`:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:5055
   ```
3. Start frontend:
   ```bash
   npm run dev
   ```
   Open **http://localhost:3000** in your browser.

---

## 🛠️ Common Troubleshooting

| Issue | Root Cause | Solution |
|---|---|---|
| Ingestion is stuck on `pending` | Background worker is not running | Run `python -m arq app.worker.WorkerSettings` in dev or ensure `arkon_worker` container is healthy. |
| DB Error: `pgvector extension not found` | PostgreSQL is missing pgvector | Ensure you are running the `pgvector/pgvector:pg16` image instead of standard `postgres`. |
| Claude Desktop: "Couldn't connect" | OAuth URL generated as `http://` | Ensure Nginx passes `proxy_set_header X-Forwarded-Proto $scheme;` in the proxy config. |
| Presigned URLs return `ERR_NAME_NOT_RESOLVED` | `MINIO_PUBLIC_ENDPOINT` is configured with internal hostnames | Set `MINIO_PUBLIC_ENDPOINT` to your browser-accessible domain or server IP. |
| Changed `NEXT_PUBLIC_API_URL` but UI calls localhost | Next.js environment variables are baked at build time | Rebuild the frontend container: `docker compose build --no-cache frontend` and restart. |
