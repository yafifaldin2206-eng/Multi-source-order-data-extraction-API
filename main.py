"""
Order Extraction API - Main Entry Point
Self-hosted ETL pipeline for unstructured order data
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Any
import uvicorn
import time

from src.router.source_router import SourceRouter
from src.models import ExtractionRequest, ExtractionResponse

app = FastAPI(
    title="Order Extraction API",
    description="Semantic normalization pipeline for messy business order data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = SourceRouter()


@app.get("/")
async def root():
    return {
        "service": "Order Extraction API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "extract_json": "POST /extract/orders",
            "extract_file": "POST /extract/orders/file",
            "health": "GET /health",
            "sources": "GET /sources"
        }
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": time.time()}


@app.get("/sources")
async def list_sources():
    """List all supported input sources"""
    return {
        "sources": [
            {
                "id": "whatsapp",
                "name": "WhatsApp Chat",
                "description": "Raw WhatsApp chat text with order messages",
                "input_type": "text"
            },
            {
                "id": "excel",
                "name": "Excel File",
                "description": "Spreadsheet with order data (messy headers supported)",
                "input_type": "file"
            },
            {
                "id": "csv",
                "name": "CSV File",
                "description": "Comma-separated order data",
                "input_type": "file"
            }
        ]
    }


@app.post("/extract/orders", response_model=ExtractionResponse)
async def extract_orders(request: ExtractionRequest):
    """
    Extract and normalize order data from text-based sources.
    
    Supports:
    - source: "whatsapp" → raw WhatsApp chat text
    - source: "csv_text" → inline CSV content
    """
    start_time = time.time()

    try:
        result = await router.route(
            source=request.source,
            data=request.data,
            options=request.options or {}
        )
        result["metadata"]["processing_time_ms"] = round((time.time() - start_time) * 1000, 2)
        return JSONResponse(content=result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.post("/extract/orders/file")
async def extract_orders_file(
    file: UploadFile = File(...),
    source: str = Form(default="excel")
):
    """
    Extract and normalize order data from uploaded files.
    
    Supports:
    - Excel files (.xlsx, .xls)
    - CSV files (.csv)
    """
    start_time = time.time()

    allowed_types = {
        "excel": [".xlsx", ".xls"],
        "csv": [".csv"]
    }

    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if source in allowed_types and ext not in allowed_types[source]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}' for source '{source}'. Expected: {allowed_types[source]}"
        )

    file_bytes = await file.read()

    try:
        result = await router.route(
            source=source,
            data=file_bytes,
            options={"filename": filename}
        )
        result["metadata"]["processing_time_ms"] = round((time.time() - start_time) * 1000, 2)
        result["metadata"]["filename"] = filename
        return JSONResponse(content=result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
