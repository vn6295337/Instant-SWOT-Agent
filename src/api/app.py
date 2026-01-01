"""
FastAPI application for Instant SWOT Agent.
Provides REST API backend for React frontend.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from src.api.routes.analysis import router as analysis_router
from src.api.routes.stocks import router as stocks_router, load_stock_listings
from src.services.workflow_store import WORKFLOWS

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Instant SWOT Agent API",
    description="Multi-agent SWOT analysis with self-correcting quality control",
    version="2.0.0"
)

# CORS configuration for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:3000",
        "https://huggingface.co",
        "https://*.hf.space",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis_router)
app.include_router(stocks_router)


@app.on_event("startup")
async def startup_event():
    """Load stock listings on startup."""
    await load_stock_listings()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "active_workflows": len(WORKFLOWS)
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
