"""Domain constants kept outside views and persistence services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StatusOption:
    value: str
    label: str


PROJECT_STATUSES: tuple[StatusOption, ...] = (
    StatusOption("idea", "Ideia"),
    StatusOption("concept", "Conceito"),
    StatusOption("pre_production", "Pré-produção"),
    StatusOption("prototype", "Protótipo"),
    StatusOption("production", "Produção"),
    StatusOption("alpha", "Alpha"),
    StatusOption("beta", "Beta"),
    StatusOption("polish", "Polimento"),
    StatusOption("finished", "Finalizado"),
    StatusOption("paused", "Pausado"),
    StatusOption("cancelled", "Cancelado"),
)

SECTION_STATUSES: tuple[StatusOption, ...] = (
    StatusOption("not_started", "Não iniciado"),
    StatusOption("draft", "Rascunho"),
    StatusOption("in_progress", "Em desenvolvimento"),
    StatusOption("review", "Revisão"),
    StatusOption("finished", "Finalizado"),
)

ROADMAP_STATUSES: tuple[StatusOption, ...] = (
    StatusOption("ideas", "Ideias"),
    StatusOption("planned", "Planejado"),
    StatusOption("in_progress", "Em andamento"),
    StatusOption("done", "Concluído"),
)

CHARACTER_ROLES: tuple[str, ...] = (
    "Protagonista",
    "Antagonista",
    "Coadjuvante",
    "Aliado",
    "Vilão",
    "NPC",
    "Criatura",
    "Mentor",
    "Personagem secundário",
)

DEFAULT_ACCENT_COLOR = "#7C5CFC"
INITIAL_SCHEMA_REVISION = "0001_initial_schema"
