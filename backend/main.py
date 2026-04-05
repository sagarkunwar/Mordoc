"""
MortgageDoc AI — FastAPI backend.

Local:      uvicorn main:app --reload --port 8000
Production: set env vars in Railway dashboard, deploy from GitHub
"""
import sys, os, json, tempfile

# Allow importing processors/ (root) and database/routes (backend/) from either CWD
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, '.env'))

# ── Railway / cloud: accept credentials as JSON string env var ────────────────
# Set GOOGLE_CREDENTIALS_JSON in Railway dashboard (paste the full key file content)
_creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
if _creds_json and not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
    _tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w')
    _tmp.write(_creds_json)
    _tmp.close()
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = _tmp.name

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import init_db
from routes.documents import router as doc_router
from routes.users import router as user_router
from routes.cases import router as case_router

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MortgageDoc AI",
    description="Australian mortgage document processing API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(doc_router,  prefix="/api/documents", tags=["Documents"])
app.include_router(user_router, prefix="/api/users",     tags=["Users"])
app.include_router(case_router, prefix="/api/cases",     tags=["Cases"])


@app.get("/api/health", tags=["Health"])
def health():
    from config import config
    return {"status": "ok", "google_cloud_configured": config.is_configured}


# ── Serve frontend (catches everything not matched by /api) ───────────────────
_frontend = os.path.join(_root, 'frontend')

@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(os.path.join(_frontend, 'index.html'))

# Serve any other static asset the frontend might reference
app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    print("\nMortgageDoc AI backend running")
    print("  Open: http://localhost:8000")
    print("  Docs: http://localhost:8000/docs\n")
