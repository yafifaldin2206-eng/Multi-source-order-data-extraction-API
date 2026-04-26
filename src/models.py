"""
Pydantic models for API request/response schema
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict


class ExtractionRequest(BaseModel):
    source: str = Field(..., description="Data source type: 'whatsapp', 'csv_text'")
    data: str = Field(..., description="Raw input data as string")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Optional parser hints")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source": "whatsapp",
                    "data": "Budi: pesan 2 es teh 1L besok ya\nSari: order nasi goreng 3 porsi buat hari ini",
                    "options": {}
                }
            ]
        }
    }


class OrderItem(BaseModel):
    customer: Optional[str] = None
    product: Optional[str] = None
    quantity: Optional[int] = None
    unit: Optional[str] = None
    date: Optional[str] = None
    notes: Optional[str] = None
    confidence: Optional[float] = None
    validation_flags: Optional[List[str]] = None


class ExtractionMetadata(BaseModel):
    source: str
    confidence: float
    total_orders: int
    valid_orders: int
    warnings: List[str] = []
    processing_time_ms: Optional[float] = None


class ExtractionResponse(BaseModel):
    orders: List[OrderItem]
    metadata: ExtractionMetadata
