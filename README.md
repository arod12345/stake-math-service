## Stake Math SDK Service (hosted Python runner)

This service wraps `@packages/math-sdk` behind an HTTP API so XFORGE users can:

- **Create a new game workspace** from `packages/math-sdk/games/template/`
- **Edit game files** (read/write/list)
- **Run simulations/config generation** on the server (no local Python required)
- **Download produced artifacts** (books, lookup tables, configs, manifests)

### Why this exists

`math-sdk` is Python/Rust heavy and not compatible with the JS runtime. Hosting it as a service keeps the JS runtime small while still letting users build custom logic by editing the template game files.

### Run locally (dev)

- Install Python 3.12+
- From repo root:

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -r packages/stake-math-service/requirements.txt
pip install -e packages/math-sdk
uvicorn stake_math_service.main:app --reload --port 8787
```

### Environment variables

- `STAKE_MATH_WORKSPACES_DIR`: where user workspaces live (default: `.stake-math-workspaces` in repo root)
- `STAKE_MATH_MAX_RUN_SECONDS`: max seconds per run (default: `120`)
- `STAKE_MATH_CORS_ORIGINS`: comma-separated origins for browser access (default: `*`)

### Deploy to Render (Docker)

In Render:

- **New → Web Service**
- **Source**: connect this GitHub repo
- **Runtime**: Docker
- **Dockerfile path**: `packages/stake-math-service/Dockerfile`
- **Health check path**: `/health`
- **Environment**
  - `STAKE_MATH_WORKSPACES_DIR=/data/workspaces`
  - `STAKE_MATH_CORS_ORIGINS=*` (or set it to your editor origin like `https://your-editor-domain`)

Recommended:

- **Add a Persistent Disk** mounted at `/data/workspaces` (otherwise user workspaces reset on deploy/restart)

After deploy, copy the Render public URL (example: `https://your-service.onrender.com`) and use it as `serviceUrl` in the Stake Math nodes.


