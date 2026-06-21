from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from app.config import DEFAULT_MODEL


class TranslationRequest(BaseModel):
    text: str
    target_language: str
    model: str = Field(default=DEFAULT_MODEL, description="Modelo Ollama a usar")
    priority: int = Field(default=1, ge=1, le=3, description="1=alta 2=media 3=baja (se fuerza a 3 si el modelo no es el predeterminado)")


class ProductQARequest(BaseModel):
    context: str
    question: str
    model: str = Field(default=DEFAULT_MODEL, description="Modelo Ollama a usar")
    priority: int = Field(default=2, ge=1, le=3, description="1=alta 2=media 3=baja (se fuerza a 3 si el modelo no es el predeterminado)")


class CommercialTextRequest(BaseModel):
    text_type: Literal["email", "anuncio", "post"]
    product_description: str
    model: str = Field(default=DEFAULT_MODEL, description="Modelo Ollama a usar")
    priority: int = Field(default=3, ge=1, le=3, description="1=alta 2=media 3=baja (se fuerza a 3 si el modelo no es el predeterminado)")


class JobResponse(BaseModel):
    job_id: str
    status: str
    priority: int
    model: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    priority: int
    response: Optional[str] = None
    model: Optional[str] = None
    service: Optional[str] = None
    error: Optional[str] = None


class LogEntry(BaseModel):
    id: int
    job_id: str
    service: str
    model: str
    priority: int
    payload: dict
    status: str
    response: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LogsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[LogEntry]


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128, description="Nombre descriptivo de la aplicación")


class ApiKeyCreated(BaseModel):
    id: int
    name: str
    key: str = Field(description="Clave en texto plano — se muestra UNA sola vez")
    created_at: datetime


class ApiKeyInfo(BaseModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
