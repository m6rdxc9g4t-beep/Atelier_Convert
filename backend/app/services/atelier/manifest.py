"""Manifeste du nœud Atelier Convert (docs/SUITE.md §7.1), `GET /api/atelier/manifest`.

Les `input_schema` et `output.schema` sont générés à partir des modèles Pydantic des routes
(JSON Schema draft 2020-12, propriétés en snake_case) : le manifeste ne peut pas diverger de l'API.
Ajouter une action : une entrée de `_actions()` (identifiant stable, jamais renommé) + un test.
Ajouter un événement : une entrée de `EVENT_TYPES` (`app/schemas/atelier.py`), émise par `EventJournal.emit`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, TypeAdapter

from app import __version__
from app.schemas.atelier import (
    EVENT_TYPES,
    AtelierManifest,
    AtelierTable,
    ConversionIdInput,
    ConvertFileInput,
    ConvertFileResult,
    ManifestAction,
    ManifestEvent,
    ManifestHttp,
    ManifestOutput,
    NoInput,
    SendToTabInput,
    TablePageInput,
)
from app.schemas.convert import ConversionSummary, SendToTabResult, TabStatus

Kind = Literal["read", "write", "destructive"]
Idem = Literal["header", "field", "natural", "none"]


def input_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Schéma d'entrée d'une action (objet, propriétés snake_case)."""
    schema = model.model_json_schema(mode="validation")
    schema.setdefault("properties", {})
    schema.setdefault("required", [])
    return schema


def output_schema(tp: Any) -> dict[str, Any]:
    return TypeAdapter(tp).json_schema(mode="serialization")


def _action(
    id_: str,
    label: str,
    description: str,
    kind: Kind,
    method: Literal["GET", "POST", "DELETE"],
    path: str,
    model: type[BaseModel],
    fmt: Literal["atelier-table/1", "json"],
    out: Any,
    idempotency: Idem,
) -> ManifestAction:
    return ManifestAction(
        id=id_,
        label=label,
        description=description,
        kind=kind,
        http=ManifestHttp(method=method, path=path),
        input_schema=input_schema(model),
        output=ManifestOutput(format=fmt, schema=output_schema(out)),
        idempotency=idempotency,
    )


def _actions() -> list[ManifestAction]:
    return [
        _action(
            "conversions.list",
            "Lister les conversions",
            "Historique des conversions : fichier, ce qui a été reconnu, nombre de lignes, envois vers Atelier Tab.",
            "read",
            "GET",
            "/api/conversions",
            NoInput,
            "json",
            list[ConversionSummary],
            "natural",
        ),
        _action(
            "conversions.table",
            "Lire la table d'une conversion",
            "Lignes d'une conversion (colonnes incluses) au format atelier-table/1, par pages.",
            "read",
            "GET",
            "/api/atelier/conversions/{conversion_id}/table",
            TablePageInput,
            "atelier-table/1",
            AtelierTable,
            "natural",
        ),
        _action(
            "conversions.convert_file",
            "Convertir un fichier",
            "Lit un fichier (PDF de relevé, CSV, TXT, XLSX, OFX, QIF, JSON) transmis en base64 et crée une conversion.",
            "write",
            "POST",
            "/api/atelier/conversions",
            ConvertFileInput,
            "json",
            ConvertFileResult,
            "header",
        ),
        _action(
            "tab.projects",
            "Lister les projets d'Atelier Tab",
            "Projets du dossier de données d'Atelier Tab où une conversion peut être envoyée.",
            "read",
            "GET",
            "/api/tab",
            NoInput,
            "json",
            TabStatus,
            "natural",
        ),
        _action(
            "conversions.send_to_tab",
            "Envoyer dans Atelier Tab",
            "Crée une nouvelle table dans un projet d'Atelier Tab avec les colonnes incluses de la conversion.",
            "write",
            "POST",
            "/api/atelier/conversions/{conversion_id}/send-to-tab",
            SendToTabInput,
            "json",
            SendToTabResult,
            "header",
        ),
        _action(
            "conversions.delete",
            "Supprimer une conversion",
            "Supprime la conversion et son fichier source de l'historique (les tables envoyées dans Tab restent).",
            "destructive",
            "DELETE",
            "/api/conversions/{conversion_id}",
            ConversionIdInput,
            "json",
            dict[str, bool],
            "natural",
        ),
    ]


def build_manifest() -> AtelierManifest:
    """Manifeste complet (actions + événements), sans secret ni donnée."""
    return AtelierManifest(
        name="Atelier Convert",
        version=__version__,
        transport="http",
        actions=_actions(),
        events=[
            ManifestEvent(type=t, label=label, data_schema=model.model_json_schema(mode="serialization"))
            for t, (label, _kind, model) in EVENT_TYPES.items()
        ],
    )
