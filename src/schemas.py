from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Category = Literal["billing", "technical", "account", "other"]


class SupportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    answer: str = Field(min_length=1, description="Respuesta breve para el usuario.")
    confidence: float = Field(
        strict=True,
        ge=0.0,
        le=1.0,
        description="Confianza autodeclarada, en una escala de 0 a 1.",
    )
    category: Category = Field(description="Categoría principal del ticket.")
    actions: list[str] = Field(
        description="Acciones sugeridas para el agente humano; no se ejecutan.",
    )
