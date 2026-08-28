"""Create and edit dialogs for game projects."""

from __future__ import annotations

import logging
from uuid import uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.feedback import set_flash
from services.project_service import (
    ProjectDetails,
    ProjectInput,
    ProjectServiceError,
    create_project,
    update_project,
)
from services.user_service import OwnerIdentity
from utils.constants import DEFAULT_ACCENT_COLOR, PROJECT_STATUSES
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)
_STATUS_VALUES = [option.value for option in PROJECT_STATUSES]
_STATUS_LABELS = {option.value: option.label for option in PROJECT_STATUSES}


def _project_fields(project: ProjectDetails | None, form_key: str) -> ProjectInput | None:
    status_value = project.status if project else "idea"
    with st.form(form_key, border=False):
        name = st.text_input(
            "Nome do jogo *",
            value=project.name if project else "",
            max_chars=160,
            placeholder="Ex.: Encouraçado",
        )
        first, second = st.columns(2)
        with first:
            codename = st.text_input(
                "Codinome",
                value=(project.codename or "") if project else "",
                max_chars=120,
                placeholder="Nome interno do projeto",
            )
            genre = st.text_input(
                "Gênero",
                value=(project.genre or "") if project else "",
                max_chars=80,
                placeholder="Horror, RPG, estratégia...",
            )
            platform = st.text_input(
                "Plataforma",
                value=(project.platform or "") if project else "",
                max_chars=120,
                placeholder="PC, PlayStation 5, mobile...",
            )
            status = st.selectbox(
                "Status",
                options=_STATUS_VALUES,
                index=_STATUS_VALUES.index(status_value),
                format_func=lambda value: _STATUS_LABELS[value],
            )
        with second:
            subgenre = st.text_input(
                "Subgênero",
                value=(project.subgenre or "") if project else "",
                max_chars=80,
                placeholder="Psicológico, roguelite...",
            )
            engine = st.text_input(
                "Engine",
                value=(project.engine or "") if project else "",
                max_chars=80,
                placeholder="Unity, Unreal, Godot...",
            )
            start_date = st.date_input(
                "Data de início",
                value=project.start_date if project else None,
                format="DD/MM/YYYY",
            )
            accent_color = st.color_picker(
                "Cor do projeto",
                value=project.accent_color if project else DEFAULT_ACCENT_COLOR,
            )
        description = st.text_area(
            "Descrição curta",
            value=(project.description or "") if project else "",
            max_chars=10_000,
            height=110,
            placeholder="Qual é a essência deste jogo?",
        )
        current_cover = project.cover_source if project else None
        if current_cover:
            st.image(current_cover, caption="Capa atual", width="stretch")
        cover_upload = st.file_uploader(
            "Imagem da capa",
            type=["png", "jpg", "jpeg", "webp"],
            max_upload_size=10,
            help="PNG, JPG ou WebP até 10 MB. A imagem será convertida para 480p.",
        )
        remove_cover = bool(current_cover) and st.checkbox("Remover capa atual")
        if cover_upload is not None:
            st.image(cover_upload, caption="Nova capa", width="stretch")
        if project is None:
            template_key = st.selectbox(
                "Estrutura inicial do GDD",
                options=["complete", None],
                format_func=lambda value: (
                    "GDD Completo — 16 categorias" if value == "complete" else "Começar vazio"
                ),
            )
        else:
            template_key = project.template_key
        submitted = st.form_submit_button(
            "Salvar projeto" if project else "Criar projeto",
            type="primary",
            icon=":material/check:",
            use_container_width=True,
        )
    if not submitted:
        return None
    if cover_upload is not None:
        cover_url = None
        cover_image = cover_upload.getvalue()
        cover_image_mime = cover_upload.type
    elif remove_cover:
        cover_url = None
        cover_image = None
        cover_image_mime = None
    elif project:
        cover_url = project.cover_url
        cover_image = project.cover_image
        cover_image_mime = project.cover_image_mime
    else:
        cover_url = None
        cover_image = None
        cover_image_mime = None

    return ProjectInput(
        name=name,
        codename=codename,
        description=description,
        genre=genre,
        subgenre=subgenre,
        platform=platform,
        engine=engine,
        status=status,
        start_date=start_date,
        cover_url=cover_url,
        cover_image=cover_image,
        cover_image_mime=cover_image_mime,
        accent_color=accent_color,
        template_key=template_key,
    )


def _render_action_error(exc: Exception) -> None:
    if isinstance(exc, ProjectServiceError):
        st.error(str(exc))
        return
    incident = uuid4().hex[:8]
    LOGGER.exception("Project write failed | incident=%s", incident)
    st.error(f"Não foi possível salvar o projeto agora. Código: {incident}")


@st.dialog("Novo projeto", width="large", icon=":material/add_circle:")
def show_create_project_dialog(owner: OwnerIdentity) -> None:
    st.caption("Comece pelo essencial. Tudo poderá ser refinado depois.")
    data = _project_fields(None, "create-project-form")
    if data is None:
        return
    try:
        project_id = create_project(owner, data)
    except (ProjectServiceError, SQLAlchemyError) as exc:
        _render_action_error(exc)
        return
    set_flash("Projeto criado e salvo no Neon.")
    go_to_page("project_detail", id=str(project_id))


@st.dialog("Editar projeto", width="large", icon=":material/edit:")
def show_edit_project_dialog(owner: OwnerIdentity, project: ProjectDetails) -> None:
    data = _project_fields(project, f"edit-project-form-{project.id}")
    if data is None:
        return
    try:
        update_project(owner, project.id, data)
    except (ProjectServiceError, SQLAlchemyError) as exc:
        _render_action_error(exc)
        return
    set_flash("Alterações salvas no Neon.")
    st.rerun()
