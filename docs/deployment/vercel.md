# Deploying Frontend Control Plane to Vercel

This guide covers deploying the Next.js 14 frontend control plane to Vercel.

---

## 1. Project Setup on Vercel

1. Log in to [Vercel Dashboard](https://vercel.com/) and click **Add New Project**.
2. Import your Git repository.
3. Configure the project root:
   - **Root Directory**: Select `frontend`.
   - **Framework Preset**: `Next.js`.
   - **Build Command**: `next build` (default).
   - **Output Directory**: `.next` (default).

---

## 2. Environment Variable Configuration

Under **Settings** $\to$ **Environment Variables**, set:

| Variable Name | Environment | Value | Description |
| :--- | :--- | :--- | :--- |
| `BACKEND_API_URL` | Production & Preview | `https://orchestrator-api.onrender.com` | Live URL of your Render backend service. |

> **IMPORTANT**: Do NOT set `GEMINI_API_KEY` or `DATABASE_URL` on Vercel.

---

## 3. How API Routing & Proxies Work

Next.js is configured via `frontend/next.config.mjs` to rewrite incoming frontend calls from `/api/:path*` to the Render backend:
```javascript
async rewrites() {
  return [
    {
      source: "/api/:path*",
      destination: `${process.env.BACKEND_API_URL}/api/:path*`,
    },
  ];
}
```
Benefits:
- **Same-Origin Browsing**: Browser network requests are sent to `/api/...` on the same domain as the web page, eliminating CORS complexity for users.
- **Header Forwarding**: Security headers (`X-Correlation-ID`) are forwarded seamlessly between Vercel Edge and Render.
