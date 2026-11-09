"""Exemples de la suite : histoires fictives qui traversent toutes les apps (format `atelier-exemples/1`)."""

from typing import Literal

from pydantic import BaseModel

SuiteApp = Literal["convert", "tab", "viz", "tresorerie", "nexus", "projets", "wiki"]


class ExempleEtape(BaseModel):
    """Une étape du parcours : ce que l'on fait dans une app avec cette histoire."""

    app: SuiteApp
    titre: str
    texte: str


class ExempleFichier(BaseModel):
    """Fichier à convertir (relevé PDF, export CSV) ; désigné par son rang, jamais par un chemin."""

    index: int
    titre: str
    description: str
    type: Literal["releve", "csv"]


class ExempleHistoire(BaseModel):
    id: str
    titre: str
    sous_titre: str
    secteur: str
    resume: str
    parcours: list[ExempleEtape]
    fichiers: list[ExempleFichier]
    tab_projet: str
