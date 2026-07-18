"""
FastAPI application for Instant SWOT Agent.
Provides REST API backend for React frontend.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

from src.api.routes.analysis import router as analysis_router
from src.api.routes.stocks import router as stocks_router, load_stock_listings
from src.services.workflow_store import WORKFLOWS

# Load environment variables from .env file (for local development)
# In HF Spaces, secrets are injected as environment variables automatically
load_dotenv()  # Safe to call even if .env doesn't exist

# Debug: Log which LLM providers are available (without exposing keys)
_llm_providers = []
if os.getenv("GROQ_API_KEY"):
    _llm_providers.append("Groq")
if os.getenv("GEMINI_API_KEY"):
    _llm_providers.append("Gemini")
if os.getenv("OPENROUTER_API_KEY"):
    _llm_providers.append("OpenRouter")
print(f"[Startup] LLM providers available: {_llm_providers or 'NONE - check HF Spaces secrets!'}")

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load stock listings on startup."""
    await load_stock_listings()
    yield


app = FastAPI(
    title="Instant SWOT Agent API",
    description="Multi-agent SWOT analysis with self-correcting quality control",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS configuration for React frontend.
# Note: literal wildcards like "https://*.hf.space" are NOT matched by
# allow_origins; subdomain patterns require allow_origin_regex.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://localhost:3000",
        "https://huggingface.co",
    ],
    allow_origin_regex=r"https://.*\.hf\.space",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cache_headers(request, call_next):
    """Immutable caching for hashed /assets bundles; no-cache for the shell."""
    response = await call_next(request)
    if request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache"
    return response

# Include routers
app.include_router(analysis_router)
app.include_router(stocks_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    llm_status = {
        "groq": bool(os.getenv("GROQ_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
    }
    return {
        "status": "ok",
        "active_workflows": len(WORKFLOWS),
        "llm_providers_configured": llm_status,
        "llm_available": any(llm_status.values())
    }


@app.get("/health/deep")
def health_check_deep():
    """
    Deep health check: sends a 1-token prompt to every configured LLM provider.
    Distinguishes 'key present' from 'model actually serves' — a plain key
    check masked the June 2026 Gemini/OpenRouter model retirements.
    Runs in the threadpool (sync def) since provider calls are blocking.
    """
    from src.llm_client import LLMClient

    results = {}
    try:
        client = LLMClient()
    except ValueError as e:
        return {"status": "error", "detail": str(e), "providers": {}}

    for provider in client.providers:
        try:
            content, error = client._call_provider(
                provider=provider, prompt="Reply with: OK",
                temperature=0, max_tokens=20
            )
            results[provider["name"]] = {
                "model": provider["model"],
                "ok": bool(content),
                "error": error,
            }
        except Exception as e:
            results[provider["name"]] = {
                "model": provider["model"], "ok": False, "error": str(e)
            }

    return {
        "status": "ok" if any(r["ok"] for r in results.values()) else "degraded",
        "providers": results,
    }


@app.get("/api")
async def api_info():
    """API info endpoint."""
    return {
        "name": "Instant SWOT Agent API",
        "version": "2.0.0",
        "endpoints": [
            "POST /analyze - Start SWOT analysis",
            "GET /workflow/{id}/status - Get workflow progress",
            "GET /workflow/{id}/result - Get final result",
            "GET /api/stocks/search - Search US stocks",
            "GET /health - Health check"
        ]
    }


# Serve React frontend static files (for Docker/HF Spaces deployment)
# Static dir is at project root level
STATIC_DIR = Path(__file__).parent.parent.parent / "static"
if STATIC_DIR.exists():
    from fastapi.responses import FileResponse

    # Mount static assets FIRST (before catch-all routes)
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(STATIC_DIR / "index.html")

    # Serve vite.svg and other root static files
    @app.get("/vite.svg")
    async def serve_vite_svg():
        return FileResponse(STATIC_DIR / "vite.svg")

    # Fallback for SPA routing - exclude API and asset paths
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept API routes or assets
        if full_path.startswith(("api/", "assets/", "analyze", "workflow", "health")):
            return {"error": "Not found"}
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
