"""Built-in GDD templates kept independent from the interface."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from models import GddSection

COMPLETE_GDD_TEMPLATE: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "Visão Geral",
        "◉",
        (
            "High Concept",
            "Elevator Pitch",
            "Resumo",
            "Objetivo do jogo",
            "Público alvo",
            "Diferenciais",
            "Referências",
        ),
    ),
    (
        "Gameplay",
        "◆",
        (
            "Core Gameplay",
            "Gameplay Loop",
            "Mecânicas",
            "Controles",
            "Interações",
            "Regras",
            "Dificuldade",
            "Vitória",
            "Derrota",
        ),
    ),
    (
        "História",
        "✦",
        (
            "Premissa",
            "Sinopse",
            "História principal",
            "Estrutura narrativa",
            "Capítulos",
            "Missões",
            "Eventos",
            "Finais",
        ),
    ),
    ("Personagens", "♟", ("Protagonistas", "Aliados", "Antagonistas", "NPCs")),
    (
        "Mundo",
        "◎",
        (
            "Universo",
            "Ambientação",
            "Locais",
            "Regiões",
            "Biomas",
            "Cidades",
            "Construções",
            "História do mundo",
            "Lore",
        ),
    ),
    (
        "Gameplay Systems",
        "⚙",
        (
            "Combate",
            "Inventário",
            "Interação",
            "IA",
            "Crafting",
            "Economia",
            "Progressão",
            "Skills",
            "Quests",
        ),
    ),
    (
        "Inimigos",
        "♜",
        ("Categorias", "Comportamentos", "Ataques", "Fraquezas", "Drops", "Localizações"),
    ),
    ("Itens", "◇", ("Armas", "Consumíveis", "Equipamentos", "Quest Items", "Colecionáveis")),
    (
        "Progressão",
        "↗",
        (
            "Progressão do jogador",
            "Progressão narrativa",
            "Progressão do mundo",
            "Unlocks",
            "Curva de dificuldade",
        ),
    ),
    (
        "Level Design",
        "▦",
        (
            "Filosofia de level design",
            "Mapas",
            "Áreas",
            "Fluxo",
            "Pontos de interesse",
            "Segredos",
            "Checkpoints",
        ),
    ),
    (
        "Arte",
        "✎",
        (
            "Direção de arte",
            "Estilo",
            "Paleta",
            "Iluminação",
            "Personagens",
            "Ambiente",
            "VFX",
            "Animações",
        ),
    ),
    ("Áudio", "♫", ("Direção sonora", "Música", "Soundtrack", "Ambiência", "SFX", "Vozes")),
    (
        "UI / UX",
        "▤",
        ("HUD", "Menus", "Inventário", "Feedback visual", "Acessibilidade", "Fluxo de telas"),
    ),
    (
        "Tecnologia",
        "⌘",
        (
            "Engine",
            "Linguagem",
            "Render pipeline",
            "Física",
            "IA",
            "Save System",
            "Networking",
            "Procedural Generation",
            "Plataformas alvo",
        ),
    ),
    (
        "Performance",
        "◴",
        (
            "FPS alvo",
            "Resolução",
            "Polygon Budget",
            "Texture Budget",
            "RAM",
            "VRAM",
            "LODs",
            "Draw Calls",
            "Mobile limitations",
        ),
    ),
    ("Produção", "✓", ("Milestones", "Protótipo", "Vertical Slice", "Alpha", "Beta", "Release")),
)


def add_complete_template(session: Session, project_id: UUID) -> None:
    for category_index, (title, icon, pages) in enumerate(COMPLETE_GDD_TEMPLATE, start=1):
        category = GddSection(
            project_id=project_id,
            title=title,
            icon=icon,
            section_type="category",
            position=category_index * 1000,
        )
        session.add(category)
        session.flush()
        session.add_all(
            GddSection(
                project_id=project_id,
                parent_id=category.id,
                title=page_title,
                section_type="page",
                position=page_index * 1000,
            )
            for page_index, page_title in enumerate(pages, start=1)
        )
