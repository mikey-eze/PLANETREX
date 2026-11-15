## Launch a public browser preview

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/mikey-eze/PLANETREX)

The repository includes `render.yaml`, which deploys a Python FastAPI service from `backend/` and serves the experimental explorer at `/explorer`. Review and approve the service in Render. When deployment completes, open `https://<your-render-service>.onrender.com/explorer`.

This is a browser preview of the **incomplete research pilot**. It is not a verified scientific analog discovery engine. The free service's filesystem is ephemeral, so local SQLite measurements are not reliable permanent cloud storage. No NASA batch collection runs on startup.

---

# PLANETREX — Moon-first planetary explorer (navigation fix)

**New canonical interface:** open `http://127.0.0.1:8000/explorer` after starting FastAPI. It starts on the Moon; Mars is selectable. Click labeled points or arbitrary mapped planetary coordinates to transition to an interactive Earth with mapped regions and stored evidence (if any). No scientific similarities are fabricated.

**Critical distinction:** mission landing locations are **navigation sites**, not automatically scientifically measured planetary reference profiles. When no compatible reference has been imported, the Earth screen shows processed profiles or **unassessed** cells, not "similar" results. See `docs/MOON_FIRST_WORKFLOW.md` and `docs/SCIENTIFIC_PIPELINE.md`.

**Windows PowerShell, from the extracted `planetrex` folder:**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
cd backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

---

# PLANETREX — scientific planetary analog discovery (terrain research pilot)

PLANETREX is intended to find potentially overlooked regions on Earth that are scientifically comparable to regions on the Moon or Mars. The project preserves earlier work and now adds a **manual scientific terrain batch pipeline and stored read-only screening results**. It does **not** yet validate or claim new planetary analog discoveries.

## Run it on Windows (PowerShell)

Extract to a folder of your choice. Open PowerShell **in the extracted `planetrex` folder**:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
cd backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

**Open `http://127.0.0.1:8000/explorer` for the dependency-free Earth explorer immediately.** This requires only the Python backend, not Node/npm. You can also open `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8000/health`.

For the optional React-based UI, start a **separate terminal**, navigate to the project's `frontend` folder, and run:

```powershell
npm install
npm run dev
```

Visit `http://127.0.0.1:5173/`. The UI includes the existing Earth globe, geographic cell explorer, and a read-only scientific candidate panel. If no sourced Moon/Mars references exist, it correctly displays **no reference available**.

## Run a controlled real DEM batch

From `planetrex\backend`:

```powershell
..\.venv\Scripts\python.exe -m app.pipeline.cli scan --south 10 --north 12 --west 76 --east 78 --step 1 --limit 4 --spacing-m 1000
```

This command requires internet access to Open-Meteo. It stores local 3x3-stencil terrain features (slope and residual roughness), **not whole-grid-cell planetary matches**. No data is downloaded just by opening the web application. To import a verified planetary terrain reference and compare stored candidates, follow `docs/SCIENTIFIC_PIPELINE.md`.

## Read-only science APIs

- `GET /health`
- `GET /discovery/grid?step=30`
- `GET /discovery/observations` — existing point observation store
- `GET /scientific/earth-events` — EONET event metadata
- `GET /scientific/planetary-products?target=moon` — PDS catalog metadata
- `GET /science/profiles?body=earth|moon|mars` — stored feature profiles
- `GET /science/profiles/{id}` — sourced measurement profile
- `GET /science/candidates?reference_id=...` — unvalidated normalized terrain distance, **not a similarity percentage**

The research pilot still uses SQLite for simplicity. DuckDB/Parquet and all eight scientific comparison domains are not claimed as implemented. See `docs/SCIENTIFIC_PIPELINE.md` and `docs/SYSTEM_BLUEPRINT.md` for the exact capabilities, limitations and next phases.

**Important:** This ZIP is a preserved, updated copy of the earlier PLANETREX archive. It was **not** merged into the original Windows folder at `C:\Users\pixel\OneDrive\Documents\PLANTREX`, which is inaccessible from this environment. Keep that folder untouched until you review differences.
