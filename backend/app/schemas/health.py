"""Schéma de l'endpoint de santé."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """État du service. `app` permet à l'app de bureau de reconnaître un serveur Atelier Convert."""

    status: Literal["ok"]
    app: Literal["atelier-convert"] = "atelier-convert"
    version: str
    environment: str
