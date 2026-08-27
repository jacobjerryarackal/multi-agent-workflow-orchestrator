# Deploying Backend to Render (Free-Tier Guide)

This guide details the deployment of the FastAPI backend and managed PostgreSQL database to Render.

---

## 1. Automated Deployment via Blueprint (`render.yaml`)

The repository includes a `render.yaml` blueprint defining the complete free-tier backend infrastructure.

### Steps:
1. Push your repository to GitHub / GitLab.
2. Navigate to [Render Dashboard](https://dashboard.render.com/) $\to$ **Blueprints** $\to$ **New Blueprint Instance**.
3. Connect your repository and select the branch (e.g. `main`).
4. Render will automatically detect `render.yaml` and configure:
   - **`orchestrator-postgres`**: Free managed PostgreSQL database.
   - **`orchestrator-api`**: Docker Web Service running the backend container.
5. In the Render Dashboard, supply the sensitive secrets:
   - `GEMINI_API_KEY`: Your real Google Gemini API key.
   - `CORS_ORIGINS`: Comma-separated list including your Vercel frontend URL (e.g. `https://your-frontend.vercel.app`).
6. Click **Apply**. Render will provision the database, run the pre-deployment migration command, and start the web service.

---

## 2. Pre-Deployment Migration Strategy

To ensure zero database schema mismatches, Render executes the pre-deploy command defined in `render.yaml`:
```bash
alembic -c backend/alembic.ini upgrade head
```
- If migrations succeed, the new application container is promoted to live traffic.
- If migrations fail (e.g., database connectivity issues), Render aborts the deployment and maintains the previous running version, preventing broken releases.

---

## 3. Container Lifecycle & Single-Worker Process Model

- **Worker Sizing**: The backend is configured with `--workers 1` for Render Free Tier (512 MB RAM limit).
- **Background Engine**: A single Uvicorn process manages `BackgroundExecutionManager`, avoiding memory contention and keeping the in-process telemetry collector cohesive.
- **Graceful Shutdown**: When Render restarts a service during deployments, `SIGTERM` triggers the FastAPI lifespan shutdown handler, which stops the watchdog supervisor and cleanly drains in-flight workflows up to a 5-second timeout.
