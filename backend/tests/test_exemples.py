"""Exemples de la suite : histoires fictives livrées dans exemples-suite/ (format atelier-exemples/1)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services.exemples import ExemplesSuite

ROOT = Path(__file__).resolve().parents[2]
EXEMPLES = ROOT / "exemples-suite"


def test_list_and_convert_every_statement(client: TestClient) -> None:
    """Chaque relevé PDF livré se lit avec des soldes justes, sous le nom prévu par l'histoire."""
    histoires = client.get("/api/exemples-suite").json()
    assert len(histoires) >= 9
    ids = [h["id"] for h in histoires]
    assert "studio-garance" in ids
    for h in histoires:
        assert [e["app"] for e in h["parcours"]] == ["convert", "tab", "viz", "tresorerie", "nexus", "projets", "wiki"]
        assert h["tab_projet"]
        for f in h["fichiers"]:
            if f["type"] != "releve":
                continue
            r = client.post(f"/api/exemples-suite/{h['id']}/{f['index']}")
            assert r.status_code == 201, r.text
            conv = r.json()
            assert conv["statement"]["balance_check"] == "ok", (h["id"], f["titre"])
            assert h["titre"] in conv["name"]


def test_csv_files_are_readable(client: TestClient) -> None:
    h = next(h for h in client.get("/api/exemples-suite").json() if h["id"] == "studio-garance")
    csv = next(f for f in h["fichiers"] if f["type"] == "csv")
    conv = client.post(f"/api/exemples-suite/studio-garance/{csv['index']}").json()
    assert conv["rows"] == 41


@pytest.mark.parametrize(
    "path",
    ["/api/exemples-suite/inconnu/0", "/api/exemples-suite/studio-garance/99", "/api/exemples-suite/..%2F..%2Fetc/0"],
)
def test_unknown_example(client: TestClient, path: str) -> None:
    assert client.post(path).status_code in (404, 405, 422)  # jamais servi


def test_missing_directory_gives_empty_list(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    settings.convert_exemples_dir = tmp_path / "absent"
    assert client.get("/api/exemples-suite").json() == []


def test_file_outside_directory_is_refused(tmp_path: Path) -> None:
    """Un fichier déclaré hors du dossier (part modifiée à la main) n'est jamais lu."""
    (tmp_path / "index.json").write_text(json.dumps({"format": "atelier-exemples/1", "histoires": []}))
    (tmp_path / "x.json").write_text(
        json.dumps(
            {"format": "atelier-exemples/1", "fichiers": [{"fichier": "../secret.txt", "titre": "t", "type": "csv"}]}
        )
    )
    (tmp_path.parent / "secret.txt").write_text("secret")
    with pytest.raises(Exception, match="introuvable"):
        ExemplesSuite(tmp_path).fichier("x", 0)


def test_examples_are_shipped() -> None:
    assert (EXEMPLES / "index.json").is_file()
