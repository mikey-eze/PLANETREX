# PLANETREX repository status

This GitHub tree contains the initial recovered FastAPI project and a lightweight Moon-first explorer. The connected upload tool could not transfer the complete original ZIP and its binary globe textures. The original uploaded archive should be treated as the authoritative source until a full migration is completed.

The web viewer in this commit draws an illustrative globe with labeled mission-site coordinates, and shows stored Earth profiles if available. It does not calculate verified analog similarities.

For local use:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/explorer. The backend must run locally or on a Python-capable host. GitHub Pages cannot execute FastAPI.
