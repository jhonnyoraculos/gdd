"""Import the professional ENCOURADO DOCX into one existing GDD Studio project.

The importer treats the document as source material, never as executable instructions.
It creates a pre-import snapshot, preserves non-imported user text, archives the complete
document in dedicated GDD sections, fills matching template sections, and integrates
characters plus the playable narrative.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from sqlalchemy import func, select
from sqlalchemy.orm import Session, undefer

from config.settings import get_settings
from models import Chapter, Character, GddSection, Project, ProjectVersion, Scene
from services.database import session_scope
from services.mention_service import (
    ContentSourceType,
    mention_key,
    sync_project_content_links,
)
from services.user_service import get_or_create_owner, owner_from_settings

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
IMPORT_MARKER = "<!-- import:roteiro-profissional-v0.1 -->"
ARCHIVE_TITLE = "Roteiro Profissional v0.1"


@dataclass(frozen=True, slots=True)
class Block:
    kind: str
    text: str = ""
    style: str = ""
    rows: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentSection:
    title: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class ImportedScene:
    act: str
    number: int
    kind: str
    title: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    preamble: tuple[Block, ...]
    sections: tuple[DocumentSection, ...]
    scenes: tuple[ImportedScene, ...]
    media_count: int


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if character.isalnum())


def _element_text(element: ET.Element) -> str:
    pieces: list[str] = []
    for node in element.iter():
        if node.tag == f"{W_NS}t":
            pieces.append(node.text or "")
        elif node.tag == f"{W_NS}tab":
            pieces.append("\t")
        elif node.tag in {f"{W_NS}br", f"{W_NS}cr"}:
            pieces.append("\n")
    return "".join(pieces).strip()


def _read_blocks(path: Path) -> tuple[tuple[Block, ...], int]:
    with ZipFile(path) as archive:
        styles_root = ET.fromstring(archive.read("word/styles.xml"))
        styles: dict[str, str] = {}
        for style in styles_root.findall(f".//{W_NS}style"):
            name = style.find(f"{W_NS}name")
            style_id = style.get(f"{W_NS}styleId")
            if style_id:
                styles[style_id] = name.get(f"{W_NS}val", "") if name is not None else ""

        document = ET.fromstring(archive.read("word/document.xml"))
        body = document.find(f"{W_NS}body")
        if body is None:
            raise ValueError("O DOCX não possui um corpo de documento válido.")

        blocks: list[Block] = []
        for child in body:
            if child.tag == f"{W_NS}p":
                text = _element_text(child)
                style_element = child.find(f"./{W_NS}pPr/{W_NS}pStyle")
                style_id = style_element.get(f"{W_NS}val") if style_element is not None else ""
                style_name = styles.get(style_id or "", "").casefold()
                numbered = child.find(f"./{W_NS}pPr/{W_NS}numPr") is not None
                if text:
                    blocks.append(
                        Block(
                            "paragraph",
                            text,
                            f"list:{style_name}" if numbered else style_name,
                        )
                    )
            elif child.tag == f"{W_NS}tbl":
                rows: list[tuple[str, ...]] = []
                for row in child.findall(f"./{W_NS}tr"):
                    cells = tuple(
                        "<br>".join(
                            text
                            for paragraph in cell.findall(f"./{W_NS}p")
                            if (text := _element_text(paragraph))
                        )
                        for cell in row.findall(f"./{W_NS}tc")
                    )
                    if any(cells):
                        rows.append(cells)
                if rows:
                    blocks.append(Block("table", rows=tuple(rows)))
        media_count = sum(name.startswith("word/media/") for name in archive.namelist())
        return tuple(blocks), media_count


def _table_markdown(rows: tuple[tuple[str, ...], ...]) -> str:
    if len(rows) == 1 and len(rows[0]) == 1:
        return f"> **{rows[0][0]}**"
    width = max(len(row) for row in rows)

    def cleaned(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", "<br>")

    output = [
        "| " + " | ".join("" for _ in range(width)) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    for row in rows:
        values = [cleaned(value) for value in row] + [""] * (width - len(row))
        output.append("| " + " | ".join(values) + " |")
    return "\n".join(output)


def _block_markdown(block: Block) -> str:
    if block.kind == "table":
        return _table_markdown(block.rows)
    text = block.text
    style = block.style.removeprefix("list:")
    if block.style.startswith("list:") or text.startswith("• "):
        return f"- {text.removeprefix('• ').strip()}"
    if style == "heading 1":
        return f"# {text}"
    if style == "heading 2":
        return f"## {text}"
    if style == "heading 3":
        return f"### {text}"
    if style.startswith("tag "):
        return f"> **ESTADO — {text}**"
    if style == "character":
        return f"**PERSONAGEM — {text}**"
    if style == "dialogue":
        return f"> {text}"
    if style == "action":
        return f"**AÇÃO:** {text}"
    if style == "objective":
        return f"**OBJETIVO:** {text}"
    if style == "note":
        return f"> **NOTA:** {text}"
    if style == "title":
        return f"# {text}"
    if style == "subtitle":
        return f"_{text}_"
    return text


def _markdown(blocks: tuple[Block, ...] | list[Block]) -> str:
    return "\n\n".join(_block_markdown(block) for block in blocks if block.text or block.rows)


def _plain_text(blocks: tuple[Block, ...] | list[Block]) -> str:
    parts: list[str] = []
    for block in blocks:
        if block.kind == "paragraph":
            parts.append(block.text)
        else:
            parts.extend(cell for row in block.rows for cell in row if cell)
    return "\n".join(parts)


def _split_document(blocks: tuple[Block, ...], media_count: int) -> ParsedDocument:
    preamble: list[Block] = []
    sections: list[DocumentSection] = []
    current_title: str | None = None
    current_blocks: list[Block] = []
    for block in blocks:
        if block.kind == "paragraph" and block.style == "heading 1":
            if current_title is None:
                preamble.extend(current_blocks)
            else:
                sections.append(DocumentSection(current_title, tuple(current_blocks)))
            current_title = block.text
            current_blocks = []
        else:
            current_blocks.append(block)
    if current_title is None:
        preamble.extend(current_blocks)
    else:
        sections.append(DocumentSection(current_title, tuple(current_blocks)))

    scene_pattern = re.compile(
        r"^ATO\s+([IVX]+)\s*/\s*(CENA|SEQU[ÊE]NCIA)\s*(\d+)\s*[—–-]\s*(.+)$",
        re.IGNORECASE,
    )
    scenes: list[ImportedScene] = []
    active: tuple[str, int, str, str] | None = None
    active_blocks: list[Block] = []

    def finish() -> None:
        nonlocal active, active_blocks
        if active is not None:
            act, number, kind, title = active
            scenes.append(ImportedScene(act, number, kind, title, tuple(active_blocks)))
        active = None
        active_blocks = []

    for block in blocks:
        marker = None
        if block.kind == "table" and len(block.rows) == 1 and len(block.rows[0]) == 1:
            marker = scene_pattern.match(block.rows[0][0].strip())
        if marker:
            finish()
            active = (
                marker.group(1).upper(),
                int(marker.group(3)),
                marker.group(2).upper(),
                marker.group(4).strip(),
            )
        elif active is not None:
            if block.kind == "paragraph" and block.style == "heading 1":
                finish()
            else:
                active_blocks.append(block)
    finish()
    return ParsedDocument(tuple(preamble), tuple(sections), tuple(scenes), media_count)


def parse_docx(path: Path) -> ParsedDocument:
    blocks, media_count = _read_blocks(path)
    return _split_document(blocks, media_count)


def _find_section(document: ParsedDocument, prefix: str) -> DocumentSection:
    for section in document.sections:
        if _fold(section.title).startswith(_fold(prefix)):
            return section
    raise ValueError(f"Seção {prefix!r} não encontrada no DOCX.")


def _subsections(section: DocumentSection, prefixes: tuple[str, ...]) -> tuple[Block, ...]:
    wanted = {_fold(prefix) for prefix in prefixes}
    output: list[Block] = []
    active = False
    for block in section.blocks:
        if block.kind == "paragraph" and block.style == "heading 2":
            active = any(_fold(block.text).startswith(prefix) for prefix in wanted)
        if active:
            output.append(block)
    return tuple(output)


def _import_content(source_title: str, blocks: tuple[Block, ...]) -> str:
    return (
        f"{IMPORT_MARKER}\n\n"
        f"> Importado do documento **Roteiro Profissional — versão 0.1**. "
        f"Fonte: **{source_title}**.\n\n{_markdown(blocks)}"
    ).strip()


def _merge_import(existing: str | None, imported: str) -> str:
    current = (existing or "").strip()
    if IMPORT_MARKER in current:
        preserved = current.split(IMPORT_MARKER, 1)[0].rstrip("\n- ")
        return f"{preserved}\n\n---\n\n{imported}" if preserved else imported
    if not current:
        return imported
    return f"{current}\n\n---\n\n{imported}"


def _snapshot(session: Session, project: Project) -> ProjectVersion:
    sections = session.scalars(
        select(GddSection)
        .options(undefer(GddSection.content))
        .where(GddSection.project_id == project.id)
        .order_by(GddSection.position, GddSection.id)
    ).all()
    characters = session.scalars(
        select(Character).where(Character.project_id == project.id).order_by(Character.name)
    ).all()
    chapters = session.scalars(
        select(Chapter).where(Chapter.project_id == project.id).order_by(Chapter.position)
    ).all()
    scenes = session.scalars(
        select(Scene).where(Scene.project_id == project.id).order_by(Scene.timeline_order)
    ).all()
    snapshot = {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
        },
        "sections": [
            {
                "id": str(item.id),
                "parent_id": str(item.parent_id) if item.parent_id else None,
                "title": item.title,
                "status": item.status,
                "content": item.content,
            }
            for item in sections
        ],
        "characters": [
            {
                "id": str(item.id),
                "name": item.name,
                "role": item.role,
                "summary": item.summary,
            }
            for item in characters
        ],
        "chapters": [
            {"id": str(item.id), "title": item.title, "summary": item.summary} for item in chapters
        ],
        "scenes": [
            {
                "id": str(item.id),
                "chapter_id": str(item.chapter_id),
                "title": item.title,
                "summary": item.summary,
                "content": item.content,
            }
            for item in scenes
        ],
    }
    version = ProjectVersion(
        project_id=project.id,
        name="Antes da importação do roteiro profissional v0.1",
        description="Snapshot automático criado antes da integração do DOCX.",
        snapshot=snapshot,
        schema_version=1,
    )
    session.add(version)
    return version


def _section_lookup(session: Session, project_id: UUID) -> dict[tuple[str, str], GddSection]:
    sections = session.scalars(
        select(GddSection)
        .options(undefer(GddSection.content))
        .where(GddSection.project_id == project_id)
    ).all()
    by_id = {item.id: item for item in sections}
    output: dict[tuple[str, str], GddSection] = {}
    for item in sections:
        parent_title = by_id[item.parent_id].title if item.parent_id in by_id else ""
        output[(_fold(parent_title), _fold(item.title))] = item
    return output


def _upsert_archive(
    session: Session,
    project: Project,
    document: ParsedDocument,
) -> tuple[GddSection, ...]:
    root = session.scalar(
        select(GddSection).where(
            GddSection.project_id == project.id,
            GddSection.parent_id.is_(None),
            GddSection.title == ARCHIVE_TITLE,
        )
    )
    if root is None:
        max_position = (
            session.scalar(
                select(func.max(GddSection.position)).where(
                    GddSection.project_id == project.id,
                    GddSection.parent_id.is_(None),
                )
            )
            or 0
        )
        root = GddSection(
            project_id=project.id,
            title=ARCHIVE_TITLE,
            icon="📘",
            section_type="category",
            status="review",
            position=max_position + 1000,
        )
        session.add(root)
        session.flush()
    else:
        root.status = "review"

    pages = [("Documento e créditos", document.preamble)] + [
        (section.title, section.blocks) for section in document.sections
    ]
    existing = {
        item.title: item
        for item in session.scalars(
            select(GddSection).where(
                GddSection.project_id == project.id,
                GddSection.parent_id == root.id,
            )
        ).all()
    }
    imported: list[GddSection] = []
    for index, (title, blocks) in enumerate(pages, start=1):
        page = existing.get(title)
        if page is None:
            page = GddSection(
                project_id=project.id,
                parent_id=root.id,
                title=title[:180],
                icon="§",
                section_type="page",
                status="review",
                position=index * 1000,
            )
            session.add(page)
        page.position = index * 1000
        page.status = "review"
        page.content = _import_content(title, blocks)
        imported.append(page)
    session.flush()
    return tuple(imported)


def _populate_template(
    session: Session,
    project: Project,
    document: ParsedDocument,
) -> tuple[GddSection, ...]:
    base = _find_section(document, "2.")
    characters = _find_section(document, "3.")
    structure = _find_section(document, "4.")
    act_one = _find_section(document, "5.")
    later_acts = _find_section(document, "6.")
    dialogue = _find_section(document, "7.")
    body_sheet = _find_section(document, "8.")
    priorities = _find_section(document, "10.")

    mappings: tuple[tuple[str, str, str, tuple[Block, ...]], ...] = (
        ("Visão Geral", "High Concept", "2.1 Logline atual", _subsections(base, ("2.1",))),
        (
            "Visão Geral",
            "Elevator Pitch",
            "2. Base narrativa consolidada",
            _subsections(base, ("2.1", "2.3")),
        ),
        ("Visão Geral", "Resumo", base.title, base.blocks),
        ("Visão Geral", "Objetivo do jogo", structure.title, structure.blocks),
        (
            "Visão Geral",
            "Diferenciais",
            "Mistério e regras de ritmo",
            _subsections(base, ("2.2", "2.4")) + _subsections(structure, ("4.1",)),
        ),
        ("História", "Premissa", base.title, _subsections(base, ("2.1", "2.2"))),
        ("História", "Sinopse", base.title, base.blocks),
        (
            "História",
            "História principal",
            "Estrutura e atos da campanha",
            structure.blocks + later_acts.blocks,
        ),
        ("História", "Estrutura narrativa", structure.title, structure.blocks),
        (
            "História",
            "Capítulos",
            "Roteiro jogável e atos seguintes",
            act_one.blocks + later_acts.blocks,
        ),
        ("Personagens", "Protagonistas", "3.1 Protagonista", _subsections(characters, ("3.1",))),
        (
            "Personagens",
            "Aliados",
            "Encouraçado e guia não nomeado",
            _subsections(characters, ("3.2", "3.3")),
        ),
        (
            "Personagens",
            "Antagonistas",
            "Corpo Seco, Cuca e Mula sem Cabeça",
            _subsections(characters, ("3.4", "3.5")),
        ),
        ("Personagens", "NPCs", dialogue.title, _subsections(dialogue, ("7.2",))),
        ("Mundo", "Universo", base.title, base.blocks),
        ("Mundo", "Ambientação", "Base e estrutura da campanha", base.blocks + structure.blocks),
        ("Mundo", "Locais", structure.title, structure.blocks),
        ("Mundo", "Lore", "Verdade de bastidor", _subsections(base, ("2.2", "2.4"))),
        ("Gameplay", "Core Gameplay", "Regras de ritmo", _subsections(structure, ("4.1",))),
        ("Gameplay", "Gameplay Loop", "Regras de ritmo", _subsections(structure, ("4.1",))),
        ("Gameplay", "Regras", "Regras de ritmo", _subsections(structure, ("4.1",))),
        (
            "Inimigos",
            "Categorias",
            "Corpo Seco e criaturas",
            _subsections(characters, ("3.4", "3.5")),
        ),
        (
            "Inimigos",
            "Comportamentos",
            "Corpo Seco",
            _subsections(characters, ("3.4",)) + body_sheet.blocks,
        ),
        (
            "Inimigos",
            "Fraquezas",
            "Ficha individual de Corpo Seco",
            body_sheet.blocks,
        ),
        ("Progressão", "Progressão narrativa", structure.title, structure.blocks),
        ("Level Design", "Áreas", structure.title, structure.blocks),
        ("Level Design", "Fluxo", structure.title, structure.blocks),
        ("Áudio", "Direção sonora", "Progressão da voz da rádio", _subsections(dialogue, ("7.2",))),
        ("Áudio", "Vozes", "Progressão da voz da rádio", _subsections(dialogue, ("7.2",))),
        ("Produção", "Milestones", priorities.title, priorities.blocks),
    )
    lookup = _section_lookup(session, project.id)
    updated: list[GddSection] = []
    for parent, title, source_title, blocks in mappings:
        section = lookup.get((_fold(parent), _fold(title)))
        if section is None:
            continue
        section.content = _merge_import(section.content, _import_content(source_title, blocks))
        if section.status == "not_started":
            section.status = "in_progress"
        updated.append(section)
    session.flush()
    return tuple(updated)


def _character_specs(document: ParsedDocument) -> tuple[dict[str, str | None], ...]:
    section = _find_section(document, "3.")
    dialogue = _find_section(document, "7.")

    def content(*prefixes: str) -> str:
        return _markdown(_subsections(section, tuple(prefixes)))

    return (
        {
            "name": "Protagonista",
            "role": "Protagonista",
            "occupation": "Policial",
            "short_description": (
                "Policial de uma cidade mineira nos anos 1990, ligado ao ciclo do portal."
            ),
            "summary": content("3.1"),
        },
        {
            "name": "Encouraçado",
            "role": "Guardião ambíguo do ciclo",
            "species": "Vampiro brasileiro",
            "short_description": (
                "Figura rara e ambígua que retorna a cada 33 anos para localizar e fechar o portal."
            ),
            "summary": content("3.2"),
        },
        {
            "name": "Guia não nomeado",
            "role": "Guia sobrenatural",
            "short_description": (
                "Presença inspirada respeitosamente em Exu Caveira, sem nome revelado em cena."
            ),
            "summary": content("3.3"),
        },
        {
            "name": "CORPO SECO",
            "role": "Antagonista principal",
            "short_description": (
                "Inimigo individualizado; cada Corpo Seco conserva história, hábitos e "
                "comportamento próprios."
            ),
            "summary": content("3.4"),
        },
        {
            "name": "Cuca",
            "role": "Presença folclórica",
            "species": "Cuca",
            "short_description": "Presença psicológica ligada a som, memória, medo e manipulação.",
            "summary": content("3.5"),
        },
        {
            "name": "Mula sem Cabeça",
            "role": "Ameaça folclórica",
            "species": "Mula sem Cabeça",
            "short_description": (
                "Ameaça das estradas e da roça percebida por som, velocidade, luz e fogo."
            ),
            "summary": content("3.5"),
        },
        {
            "name": "Locutor da Madrugada",
            "role": "Voz radiofônica",
            "short_description": (
                "Voz da emissora impossível, ligada a uma noite de um ciclo anterior."
            ),
            "summary": _markdown(_subsections(dialogue, ("7.2",))),
        },
    )


def _upsert_characters(
    session: Session,
    project: Project,
    document: ParsedDocument,
) -> tuple[Character, ...]:
    existing = {
        mention_key(item.name): item
        for item in session.scalars(
            select(Character).where(Character.project_id == project.id)
        ).all()
    }
    characters: list[Character] = []
    for spec in _character_specs(document):
        name = str(spec["name"])
        character = existing.get(mention_key(name))
        if character is None:
            character = Character(
                project_id=project.id,
                name=name,
                normalized_name=name.casefold(),
            )
            session.add(character)
            existing[mention_key(name)] = character
        for field in ("role", "occupation", "species", "short_description"):
            value = spec.get(field)
            if value and not getattr(character, field):
                setattr(character, field, value)
        imported_summary = (
            f"{IMPORT_MARKER}\n\n> Perfil importado do roteiro profissional v0.1.\n\n"
            f"{spec.get('summary') or ''}"
        ).strip()
        character.summary = _merge_import(character.summary, imported_summary)
        characters.append(character)
    session.flush()
    return tuple(characters)


def _scene_summary(scene: ImportedScene) -> str:
    metadata: dict[str, str] = {}
    for block in scene.blocks:
        if block.kind != "table":
            continue
        for row in block.rows:
            if len(row) >= 2:
                metadata[_fold(row[0])] = row[1]
    parts = [
        f"{label}: {metadata[key]}"
        for key, label in (("local", "Local"), ("horario", "Horário"), ("modo", "Modo"))
        if key in metadata
    ]
    if parts:
        return " · ".join(parts)[:20_000]
    for index, block in enumerate(scene.blocks):
        if block.kind == "paragraph" and _fold(block.text).startswith("funcao"):
            for following in scene.blocks[index + 1 :]:
                if following.kind == "paragraph" and following.style.startswith("heading"):
                    break
                text = _plain_text([following]).strip()
                if text and _fold(text) not in {"estrutural", "confirmado", "adefinir"}:
                    return text[:20_000]
    return f"{scene.kind.title()} estrutural do Ato {scene.act}."


def _character_mentions(text: str, *, protagonist: bool = False) -> list[str]:
    folded = _fold(text)
    aliases = (
        ("encouracado", "@encouracado"),
        ("guianomeado", "@guianaonomeado"),
        ("guia", "@guianaonomeado"),
        ("corposeco", "@corposeco"),
        ("cuca", "@cuca"),
        ("mulasemcabeca", "@mulasemcabeca"),
        ("locutordamadrugada", "@locutordamadrugada"),
    )
    tokens = [token for alias, token in aliases if alias in folded]
    if protagonist:
        tokens.insert(0, "@protagonista")
    return list(dict.fromkeys(tokens))


def _scene_content(scene: ImportedScene) -> str:
    title = f"Ato {scene.act} · {scene.kind.title()} {scene.number:02d} — {scene.title}"
    body = _markdown(scene.blocks)
    mentions = _character_mentions(_plain_text(scene.blocks), protagonist=True)
    connection_block = "\n\n## Conexões automáticas\n\n" + " ".join(mentions)
    return (
        f"{IMPORT_MARKER}\n\n> Importado do roteiro profissional v0.1.\n\n"
        f"# {title}\n\n{body}{connection_block}"
    ).strip()


def _upsert_narrative(
    session: Session,
    project: Project,
    document: ParsedDocument,
) -> tuple[tuple[Chapter, ...], tuple[Scene, ...]]:
    chapter_specs = {
        "I": (
            "Ato I — Ruptura",
            "Casa, rua, delegacia e garagem. O cotidiano se transforma em mistério.",
        ),
        "II": (
            "Ato II — Investigação",
            "Hospital, igreja e cidade alta ampliam o ciclo e a presença do Encouraçado.",
        ),
        "III": (
            "Ato III — Expansão",
            "Estrada, roça, distrito e baile mudam o ritmo e apresentam a Mula sem Cabeça.",
        ),
        "IV": (
            "Ato IV — Revelação",
            "Cuca e antiga estação de rádio rompem memória e tempo.",
        ),
        "V": (
            "Ato V — Convergência",
            "Portal, linhagem, criaturas, guia e decisão final convergem.",
        ),
        "EPILOGO": (
            "Epílogo — Consequência",
            "Cidade, rádio e casa mostram o preço da escolha e o destino do ciclo.",
        ),
    }
    imported_scenes = list(document.scenes)
    imported_scenes.append(
        ImportedScene(
            "EPILOGO",
            1,
            "SEQUÊNCIA",
            "CONSEQUÊNCIA DO CICLO",
            (
                Block("paragraph", "ESTRUTURAL", "tag structural"),
                Block("paragraph", "Áreas: cidade, rádio e casa."),
                Block(
                    "paragraph",
                    "Mostrar o preço da escolha e o destino do ciclo.",
                ),
            ),
        )
    )
    existing_chapters = session.scalars(
        select(Chapter)
        .where(Chapter.project_id == project.id)
        .order_by(Chapter.position, Chapter.id)
    ).all()
    chapters_by_key = {_fold(item.title): item for item in existing_chapters}
    chapters: dict[str, Chapter] = {}
    act_order = ("I", "II", "III", "IV", "V", "EPILOGO")
    for index, act in enumerate(act_order, start=1):
        title, summary = chapter_specs[act]
        chapter = chapters_by_key.get(_fold(title))
        if chapter is None and act == "I" and len(existing_chapters) == 1:
            chapter = existing_chapters[0]
        if chapter is None:
            chapter = Chapter(project_id=project.id, title=title, position=index * 1000)
            session.add(chapter)
        chapter.title = title
        chapter.summary = summary
        chapter.position = index * 1000
        chapters[act] = chapter
    session.flush()

    existing_scenes = session.scalars(
        select(Scene)
        .where(Scene.project_id == project.id)
        .order_by(Scene.timeline_order, Scene.position, Scene.id)
    ).all()
    scenes_by_key = {(_fold(item.title), item.chapter_id): item for item in existing_scenes}
    first_existing = existing_scenes[0] if len(existing_scenes) == 1 else None
    imported: list[Scene] = []
    by_act: defaultdict[str, list[ImportedScene]] = defaultdict(list)
    for source in imported_scenes:
        by_act[source.act].append(source)
    timeline = 0
    for act in act_order:
        chapter = chapters[act]
        for position, source in enumerate(
            sorted(by_act[act], key=lambda item: item.number), start=1
        ):
            scene = scenes_by_key.get((_fold(source.title), chapter.id))
            if scene is None and act == "I" and source.number == 1 and first_existing is not None:
                scene = first_existing
            if scene is None:
                scene = Scene(
                    project_id=project.id,
                    chapter_id=chapter.id,
                    title=source.title,
                    position=position * 1000,
                    timeline_order=0,
                )
                session.add(scene)
            timeline += 1000
            old_summary = (scene.summary or "").strip()
            summary = _scene_summary(source)
            if (
                old_summary
                and old_summary not in summary
                and IMPORT_MARKER not in (scene.content or "")
            ):
                summary = f"{summary} · Registro anterior: {old_summary}"
            scene.chapter_id = chapter.id
            scene.title = source.title
            scene.summary = summary[:20_000]
            scene.content = _scene_content(source)
            scene.position = position * 1000
            scene.timeline_order = timeline
            imported.append(scene)
    session.flush()
    return tuple(chapters[act] for act in act_order), tuple(imported)


def _append_section_mentions(
    session: Session,
    project: Project,
    sections: tuple[GddSection, ...],
    scenes: tuple[Scene, ...],
) -> None:
    sources: list[tuple[ContentSourceType, UUID, str]] = []
    for section in sections:
        base_content = section.content or ""
        plain = _fold(base_content)
        tokens = _character_mentions(base_content)
        for scene in scenes:
            if _fold(scene.title) in plain:
                tokens.append(f"@cena:{mention_key(scene.title)}")
        tokens = list(dict.fromkeys(tokens))
        if tokens and "## Conexões importadas" not in base_content:
            section.content = (
                f"{base_content.rstrip()}\n\n## Conexões importadas\n\n{' '.join(tokens)}"
            )
        sources.append((ContentSourceType.SECTION, section.id, section.content or ""))
    sources.extend(
        (
            ContentSourceType.SCENE,
            scene.id,
            "\n".join(filter(None, (scene.summary, scene.content))),
        )
        for scene in scenes
    )
    sync_project_content_links(session, project.id, tuple(sources))


def import_document(path: Path, project_id: UUID, *, apply: bool) -> dict[str, int]:
    document = parse_docx(path)
    result = {
        "document_sections": len(document.sections),
        "document_scenes": len(document.scenes),
        "document_media": document.media_count,
        "archive_pages": len(document.sections) + 1,
        "characters": 7,
        "chapters": 6,
        "scenes": len(document.scenes) + 1,
    }
    if not apply:
        return result

    settings = get_settings()
    owner = owner_from_settings(settings)
    with session_scope() as session:
        user = get_or_create_owner(session, owner)
        project = session.scalar(
            select(Project).where(Project.id == project_id, Project.user_id == user.id)
        )
        if project is None:
            raise ValueError("Projeto não encontrado ou fora do workspace configurado.")
        _snapshot(session, project)
        archive = _upsert_archive(session, project, document)
        template_sections = _populate_template(session, project, document)
        characters = _upsert_characters(session, project, document)
        chapters, scenes = _upsert_narrative(session, project, document)
        _append_section_mentions(
            session,
            project,
            tuple(dict.fromkeys((*archive, *template_sections))),
            scenes,
        )
        project.updated_at = datetime.now(UTC)
        session.flush()
        result.update(
            {
                "archive_pages": len(archive),
                "template_sections": len(template_sections),
                "characters": len(characters),
                "chapters": len(chapters),
                "scenes": len(scenes),
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--project", required=True, type=UUID)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist the import. Without this option the command only reports the plan.",
    )
    args = parser.parse_args()
    if not args.document.is_file():
        raise SystemExit(f"Documento não encontrado: {args.document}")
    result = import_document(args.document, args.project, apply=args.apply)
    mode = "IMPORTAÇÃO CONCLUÍDA" if args.apply else "PLANO DE IMPORTAÇÃO"
    print(mode)
    for key, value in result.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
