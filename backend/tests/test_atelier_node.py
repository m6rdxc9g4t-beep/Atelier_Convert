"""Nœud Atelier (docs/SUITE.md §7) : manifeste, table d'échange, conversion par workflow, envoi vers Tab,
idempotence, événements et erreurs `{detail, code}`."""

import base64
import json
import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.core.config import Settings
from app.schemas.atelier import EVENT_TYPES, AtelierTable
from app.services.atelier.journal import EventJournal
from main import create_app
from tests.test_conversions_routes import make_tab, upload

ROOT = Path(__file__).resolve().parents[2]
ACTION_ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")


def events(client: TestClient, **params: Any) -> dict[str, Any]:
    r = client.get("/api/atelier/events", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_manifest_shape(client: TestClient) -> None:
    m = client.get("/api/atelier/manifest").json()
    assert m["contract"] == "atelier-node/1" and m["app"] == "convert" and m["name"] == "Atelier Convert"
    ids = [a["id"] for a in m["actions"]]
    assert len(ids) == len(set(ids)) and all(ACTION_ID.match(i) for i in ids)
    for action in m["actions"]:
        assert (action.get("http") is None) != (action.get("mcp_tool") is None)
        Draft202012Validator.check_schema(action["input_schema"])
        Draft202012Validator.check_schema(action["output"]["schema"])
        assert all(SNAKE.match(p) for p in action["input_schema"]["properties"])
        if action["kind"] == "write":
            assert action["idempotency"] in {"header", "field"}
        # Chaque chemin existe vraiment dans l'API.
        path = re.sub(r"\{[^}]+\}", "0123456789ab", action["http"]["path"])
        assert client.request(action["http"]["method"], path).status_code != 405
    assert {e["type"] for e in m["events"]} == set(EVENT_TYPES)
    text = json.dumps(m)
    assert "Atelier_Tab" not in text and "/home" not in text  # ni chemin ni donnée


def test_convert_file_table_and_events(client: TestClient) -> None:
    content = base64.b64encode((ROOT / "samples" / "export-banque.csv").read_bytes()).decode()
    r = client.post("/api/atelier/conversions", json={"filename": "dossier/export.csv", "content_base64": content})
    assert r.status_code == 201, r.text
    result = r.json()
    assert result["rows"] == 18 and result["name"] == "export"
    cid = result["conversion_id"]

    page = client.get(f"/api/atelier/conversions/{cid}/table", params={"limit": 5}).json()
    table = AtelierTable.model_validate(page)
    assert table.total == 18 and table.truncated is True and len(table.rows) == 5
    assert table.rows[0]["date"] == "2026-03-02" and table.rows[0]["debit"] == 84.2

    created = [e for e in events(client)["events"] if e["type"] == "convert.conversion.created"]
    assert created[-1]["subject"] == {"kind": "conversion", "id": cid, "label": "export"}
    assert created[-1]["data"] == {
        "name": "export",
        "format": "csv",
        "rows": 18,
        "columns": 6,
        "statement": True,
        "origin": "workflow",
    }


def test_convert_file_errors(client: TestClient) -> None:
    r = client.post("/api/atelier/conversions", json={"filename": "x.csv", "content_base64": "%%%"})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION"
    r = client.post(
        "/api/atelier/conversions", json={"filename": "x.png", "content_base64": base64.b64encode(b"\x89PNG").decode()}
    )
    assert r.status_code == 415 and r.json()["code"] == "VALIDATION"
    r = client.get("/api/atelier/conversions/0123456789ab/table")
    assert r.status_code == 404 and r.json() == {"detail": "Conversion introuvable (supprimée ?).", "code": "NOT_FOUND"}
    r = client.post("/api/atelier/conversions", json={})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION"


def test_idempotency(client: TestClient, settings: Settings) -> None:
    content = base64.b64encode(b"Date;Libelle;Montant\n01/03/2026;Cafe;-2,50\n02/03/2026;Pain;-1,20\n").decode()
    body = {"filename": "mini.csv", "content_base64": content}
    first = client.post("/api/atelier/conversions", json=body, headers={"Idempotency-Key": "nexus:run1:step1"})
    again = client.post("/api/atelier/conversions", json=body, headers={"Idempotency-Key": "nexus:run1:step1"})
    assert first.status_code == again.status_code == 201
    assert again.headers["Idempotency-Replayed"] == "true" and again.json() == first.json()
    assert len(client.get("/api/conversions").json()) == 1
    other = client.post(
        "/api/atelier/conversions",
        json={**body, "filename": "autre.csv"},
        headers={"Idempotency-Key": "nexus:run1:step1"},
    )
    assert other.status_code == 409 and other.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    root = make_tab(settings)
    cid = first.json()["conversion_id"]
    send = {"project_id": "proj_0", "table_name": "Mini"}
    a = client.post(f"/api/atelier/conversions/{cid}/send-to-tab", json=send, headers={"Idempotency-Key": "k2"})
    b = client.post(f"/api/atelier/conversions/{cid}/send-to-tab", json=send, headers={"Idempotency-Key": "k2"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert len(list((root / "tables").glob("*.json"))) == 1
    sent = [e for e in events(client)["events"] if e["type"] == "convert.conversion.sent_to_tab"]
    assert len(sent) == 1 and sent[0]["data"]["rows"] == 2 and sent[0]["data"]["project_id"] == "proj_0"


def test_all_event_types_emitted(client: TestClient, settings: Settings) -> None:
    make_tab(settings)
    conv = upload(client)
    client.put(f"/api/conversions/{conv['id']}/name", json={"name": "Mars"})
    client.post(f"/api/conversions/{conv['id']}/send-to-tab", json={"project_id": "proj_0"})
    client.delete(f"/api/conversions/{conv['id']}")
    page = events(client, limit=500)
    assert {e["type"] for e in page["events"]} == set(EVENT_TYPES)
    for e in page["events"]:
        model = EVENT_TYPES[e["type"]][2]
        model.model_validate(e["data"])
        assert "rows" not in e["data"] or isinstance(e["data"]["rows"], int)
    only = events(client, types="convert.conversion.deleted")["events"]
    assert [e["type"] for e in only] == ["convert.conversion.deleted"]


def test_seq_survives_restart(settings: Settings) -> None:
    with TestClient(create_app(settings)) as c:
        upload(c)
        last = events(c)["next"]
    with TestClient(create_app(settings)) as c:
        upload(c)
        page = events(c, since=last)
        assert page["events"][0]["seq"] == last + 1 and page["gap"] is False
    journal = EventJournal(settings.data_dir / "atelier_events.jsonl")
    assert journal.last_seq == last + 1
    assert journal.page(since=last + 50, limit=10).gap is True
