# ruff: noqa: E501
"""Bidirectional full-page visual editor for the narrative graph."""

from __future__ import annotations

import json
import re
from typing import Any

import streamlit as st

from services.narrative_map_service import NarrativeMapGraph

_ACCENT_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
_IMPORT_MARKER_PATTERN = re.compile(r"<!--\s*import:[^>]+-->\s*", re.IGNORECASE)


def _display_content(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _IMPORT_MARKER_PATTERN.sub("", value).strip()
    cleaned = cleaned.split("\n## Conexões automáticas", 1)[0].rstrip()
    return cleaned or None


def _graph_data(
    graph: NarrativeMapGraph,
    theme: str | None = None,
    selected_node: str | None = None,
) -> dict[str, Any]:
    return {
        "project": graph.project_name,
        "projectId": str(graph.project_id),
        "accent": (
            graph.accent_color if _ACCENT_PATTERN.fullmatch(graph.accent_color) else "#7C5CFC"
        ),
        "theme": "light" if theme == "light" else "dark",
        "initialSelected": selected_node,
        "nodes": [
            {
                "id": node.key,
                "entityId": str(node.entity_id),
                "type": node.node_type.value,
                "label": node.label,
                "subtitle": node.subtitle,
                "description": node.description,
                "content": _display_content(node.content),
                "href": node.href,
                "metrics": [
                    {"label": metric.label, "value": metric.value} for metric in node.metrics
                ],
                "itemsTitle": node.items_title,
                "items": list(node.items),
                "connections": [
                    {
                        "edgeId": connection.edge_key,
                        "nodeId": connection.node_key,
                        "label": connection.label,
                        "subtitle": connection.subtitle,
                        "removable": connection.removable,
                    }
                    for connection in node.connections
                ],
            }
            for node in graph.nodes
        ],
        "edges": [
            {
                "id": edge.key,
                "source": edge.source,
                "target": edge.target,
                "type": edge.edge_type.value,
                "label": edge.label,
                "directed": edge.directed,
                "removable": edge.removable,
            }
            for edge in graph.edges
        ],
    }


def _payload(graph: NarrativeMapGraph) -> str:
    """Return script-safe JSON for regression tests and standalone previews."""

    return (
        json.dumps(_graph_data(graph), ensure_ascii=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


_HTML = """
<main class="map-shell">
  <div class="map-layout">
    <section class="map-stage" aria-label="Mapa narrativo interativo">
      <div class="map-controls" aria-label="Controles do mapa">
        <button id="zoomIn" type="button" title="Aproximar" aria-label="Aproximar">+</button>
        <button id="zoomOut" type="button" title="Afastar" aria-label="Afastar">−</button>
        <button id="fit" type="button" title="Enquadrar mapa">Enquadrar</button>
        <button id="clear" type="button" title="Limpar seleção">Limpar seleção</button>
        <button id="fullscreen" type="button" title="Usar a tela inteira">Tela cheia</button>
      </div>
      <svg id="graph" role="application" aria-label="Cards e conexões narrativas">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--accent)"></path>
          </marker>
        </defs>
        <g id="edgeLayer"></g>
        <g id="edgeLabelLayer"></g>
        <g id="nodeLayer"></g>
      </svg>
      <div class="map-legend" aria-label="Legenda">
        <span><i class="legend-project"></i>Projeto</span>
        <span><i class="legend-chapter"></i>Capítulo</span>
        <span><i class="legend-scene"></i>Cena</span>
        <span><i class="legend-character"></i>Personagem</span>
        <span><i class="legend-section"></i>Seção GDD</span>
        <span><i class="legend-manual"></i>Ligação criada</span>
      </div>
    </section>
    <aside id="panel" class="node-panel" aria-live="polite"></aside>
  </div>
</main>
"""


_CSS = """
:host {
  --accent: __ACCENT__;
  --bg: #11131a;
  --surface: rgba(31, 34, 45, .88);
  --surface-soft: rgba(35, 38, 50, .64);
  --border: rgba(255, 255, 255, .12);
  --text: #f4f5fb;
  --muted: #a9adbd;
  --edge: rgba(190, 195, 212, .34);
  --danger: #e85d68;
  color: var(--text);
  display: block;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
:host([data-theme="light"]), .map-shell[data-theme="light"] {
  --bg: #eef0f6;
  --surface: rgba(255, 255, 255, .92);
  --surface-soft: rgba(255, 255, 255, .7);
  --border: rgba(40, 43, 58, .13);
  --text: #181a22;
  --muted: #686c7b;
  --edge: rgba(76, 80, 98, .32);
  --danger: #c43b4a;
}
* { box-sizing: border-box; }
button, a { font: inherit; }
.map-shell {
  background: radial-gradient(circle at 18% 8%, color-mix(in srgb, var(--accent) 10%, transparent), transparent 32%), var(--bg);
  border: 1px solid var(--border);
  border-radius: 20px;
  box-shadow: 0 18px 48px rgba(30, 33, 48, .13), inset 0 1px 0 rgba(255, 255, 255, .06);
  color: var(--text);
  height: 1010px;
  min-height: 760px;
  overflow: hidden;
}
.map-shell:fullscreen { border: 0; border-radius: 0; height: 100vh; width: 100vw; }
.map-layout { display: grid; grid-template-columns: minmax(0, 1fr) 410px; height: 100%; min-width: 0; }
.map-stage { min-width: 0; overflow: hidden; position: relative; }
#graph { cursor: grab; display: block; height: 100%; min-width: 0; touch-action: none; width: 100%; }
#graph.is-panning { cursor: grabbing; }
.map-controls { display: flex; flex-wrap: wrap; gap: 6px; left: 14px; position: absolute; top: 14px; z-index: 4; }
.map-controls button, .panel-button {
  align-items: center; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; color: var(--text); cursor: pointer; display: inline-flex; font-size: 12px; font-weight: 750; justify-content: center; min-height: 38px; padding: 0 11px;
}
.map-controls button:first-child, .map-controls button:nth-child(2) { font-size: 18px; min-width: 38px; padding: 0; }
.map-controls button:hover, .panel-button:hover { border-color: color-mix(in srgb, var(--accent) 55%, var(--border)); }
.map-legend { align-items: center; backdrop-filter: blur(12px); background: var(--surface); border: 1px solid var(--border); border-radius: 12px; bottom: 14px; display: flex; flex-wrap: wrap; gap: 9px 12px; left: 14px; padding: 8px 10px; position: absolute; z-index: 4; }
.map-legend span { align-items: center; color: var(--muted); display: flex; font-size: 11px; gap: 5px; }
.map-legend i { border-radius: 50%; display: inline-block; height: 8px; width: 8px; }
.legend-project { background: var(--accent); } .legend-chapter { background: #7697f8; } .legend-scene { background: #55b99a; } .legend-character { background: #b181ef; } .legend-section { background: #ed9f56; } .legend-manual { background: #f4cb55; }
.edge { stroke: var(--edge); stroke-linecap: round; stroke-width: 1.6; transition: opacity .18s ease, stroke .18s ease, stroke-width .18s ease; }
.edge-appearance { stroke: color-mix(in srgb, #55b99a 58%, var(--edge)); stroke-dasharray: 5 6; }
.edge-relationship { stroke: color-mix(in srgb, #b181ef 70%, var(--edge)); stroke-width: 2; }
.edge-mention { stroke: color-mix(in srgb, #ed9f56 76%, var(--edge)); stroke-dasharray: 3 5; stroke-width: 2.1; }
.edge-manual { stroke: #e7b72d; stroke-dasharray: 9 4; stroke-width: 2.5; }
.edge.is-active { stroke: var(--accent); stroke-width: 3.2; opacity: 1; }
.edge.is-dimmed, .edge-label.is-dimmed { opacity: .055; }
.edge-label { fill: var(--muted); font-size: 10px; font-weight: 700; paint-order: stroke; pointer-events: none; stroke: var(--bg); stroke-width: 4px; text-anchor: middle; transition: opacity .18s ease; }
.node { cursor: pointer; outline: none; transition: opacity .18s ease; }
.node.is-dimmed { opacity: .12; }
.node rect { fill: var(--surface); stroke: var(--border); stroke-width: 1.5; transition: filter .18s ease, stroke .18s ease, stroke-width .18s ease; }
.node:hover rect, .node:focus rect { filter: brightness(1.08); stroke: var(--accent); }
.node.is-selected rect { filter: drop-shadow(0 9px 18px color-mix(in srgb, var(--accent) 32%, transparent)); stroke: var(--accent); stroke-width: 3.2; }
.node-project rect { fill: color-mix(in srgb, var(--accent) 24%, var(--surface)); } .node-chapter rect { fill: color-mix(in srgb, #7697f8 18%, var(--surface)); } .node-scene rect { fill: color-mix(in srgb, #55b99a 17%, var(--surface)); } .node-character rect { fill: color-mix(in srgb, #b181ef 17%, var(--surface)); } .node-section rect { fill: color-mix(in srgb, #ed9f56 18%, var(--surface)); }
.node-type-label { fill: var(--muted); font-size: 9px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; }
.node-label { fill: var(--text); font-size: 13px; font-weight: 750; } .node-subtitle { fill: var(--muted); font-size: 10px; }
.node-panel { background: color-mix(in srgb, var(--surface) 94%, transparent); border-left: 1px solid var(--border); min-width: 0; overflow: auto; padding: 24px 20px 36px; }
.panel-eyebrow { color: var(--accent); font-size: 10px; font-weight: 800; letter-spacing: 1.2px; margin: 0; text-transform: uppercase; }
.node-panel h2 { font-size: 25px; letter-spacing: -.035em; line-height: 1.08; margin: 8px 0 0; overflow-wrap: anywhere; }
.panel-subtitle { color: var(--muted); font-size: 13px; line-height: 1.5; margin: 8px 0 0; overflow-wrap: anywhere; }
.panel-description { font-size: 13px; line-height: 1.6; margin: 18px 0 0; overflow-wrap: anywhere; white-space: pre-wrap; }
.panel-content, .panel-items, .panel-connections { margin-top: 20px; }
.panel-content h3, .panel-items h3, .panel-connections h3 { font-size: 12px; margin: 0 0 8px; }
.panel-content-body { background: var(--surface-soft); border: 1px solid var(--border); border-radius: 12px; font-family: inherit; font-size: 13px; line-height: 1.65; margin: 0; max-height: 390px; overflow: auto; padding: 13px; white-space: pre-wrap; word-break: break-word; }
.panel-metrics { display: grid; gap: 8px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 18px; }
.panel-metric { background: var(--surface-soft); border: 1px solid var(--border); border-radius: 12px; min-width: 0; padding: 10px; }
.panel-metric span { color: var(--muted); display: block; font-size: 9px; font-weight: 800; letter-spacing: .7px; text-transform: uppercase; }
.panel-metric strong { display: block; font-size: 16px; margin-top: 4px; overflow-wrap: anywhere; }
.panel-items ul, .connection-list { display: grid; gap: 7px; list-style: none; margin: 0; padding: 0; }
.panel-items li { background: var(--surface-soft); border: 1px solid var(--border); border-radius: 9px; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; padding: 8px 9px; }
.connection-card { align-items: center; background: var(--surface-soft); border: 1px solid var(--border); border-radius: 11px; display: grid; gap: 8px; grid-template-columns: minmax(0, 1fr) auto; padding: 8px 9px; }
.connection-select { background: transparent; border: 0; color: var(--text); cursor: pointer; min-width: 0; padding: 0; text-align: left; }
.connection-select strong, .connection-select span { display: block; overflow-wrap: anywhere; } .connection-select strong { font-size: 12px; } .connection-select span { color: var(--muted); font-size: 10px; margin-top: 3px; }
.connection-delete { background: transparent; border: 1px solid color-mix(in srgb, var(--danger) 32%, var(--border)); border-radius: 8px; color: var(--danger); cursor: pointer; height: 30px; width: 30px; }
.panel-actions { display: grid; gap: 8px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 22px; }
.panel-button { min-height: 42px; text-decoration: none; }
.panel-button.primary { background: var(--accent); border-color: transparent; color: white; }
.panel-button.danger { color: var(--danger); }
.panel-button.wide { grid-column: 1 / -1; }
.panel-empty { color: var(--muted); line-height: 1.6; margin-top: 12px; }
@media (max-width: 850px) { .map-shell { height: 1180px; } .map-layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: 650px 530px; } .node-panel { border-left: 0; border-top: 1px solid var(--border); padding: 18px 16px; } .map-legend { bottom: 10px; left: 10px; right: 10px; } .map-controls { left: 10px; top: 10px; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: .01ms !important; } }
"""


_JS = r"""
export default function(component) {
  "use strict";
  const {data, parentElement, setTriggerValue} = component;
  const shell = parentElement.querySelector(".map-shell");
  const svg = parentElement.querySelector("#graph");
  const edgeLayer = parentElement.querySelector("#edgeLayer");
  const edgeLabelLayer = parentElement.querySelector("#edgeLabelLayer");
  const nodeLayer = parentElement.querySelector("#nodeLayer");
  const panel = parentElement.querySelector("#panel");
  const NS = "http://www.w3.org/2000/svg";
  const NODE_WIDTH = 184;
  const NODE_HEIGHT = 70;
  const typeLabels = {project: "Projeto", chapter: "Capítulo", scene: "Cena", character: "Personagem", section: "Seção GDD"};
  shell.dataset.theme = data.theme;
  shell.style.setProperty("--accent", data.accent);
  const nodes = data.nodes.map(node => ({...node, x: 0, y: 0, element: null}));
  const edges = data.edges.map(edge => ({...edge, element: null, labelElement: null}));
  const nodeById = new Map(nodes.map(node => [node.id, node]));
  const storageKey = `gdd-map-editor:${data.projectId}`;
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(storageKey) || "{}"); } catch (_) { saved = {}; }
  const typeCounts = nodes.reduce((counts, node) => { counts[node.type] = (counts[node.type] || 0) + 1; return counts; }, {});
  const largestLayer = Math.max(1, ...Object.values(typeCounts));
  const WORLD_WIDTH = Math.max(900, Math.min(1900, largestLayer * 214 + 280));

  function distribute(items, startY) {
    if (!items.length) return startY;
    const perRow = Math.max(1, Math.min(8, Math.floor((WORLD_WIDTH - 120) / 204)));
    const rows = Math.ceil(items.length / perRow);
    items.forEach((node, index) => {
      const row = Math.floor(index / perRow);
      const rowStart = row * perRow;
      const rowCount = Math.min(perRow, items.length - rowStart);
      const slot = index - rowStart;
      const spacing = WORLD_WIDTH / (rowCount + 1);
      node.x = spacing * (slot + 1);
      node.y = startY + row * 116;
    });
    return startY + rows * 116;
  }

  const byType = type => nodes.filter(node => node.type === type);
  byType("project").forEach(node => { node.x = WORLD_WIDTH / 2; node.y = 88; });
  let nextY = distribute(byType("chapter"), 230) + 82;
  nextY = distribute(byType("scene"), nextY) + 82;
  nextY = distribute(byType("character"), nextY) + 88;
  nextY = distribute(byType("section"), nextY) + 90;
  const WORLD_HEIGHT = Math.max(760, nextY);
  if (saved.positions) nodes.forEach(node => {
    const position = saved.positions[node.id];
    if (position && Number.isFinite(position.x) && Number.isFinite(position.y)) {
      node.x = Math.max(NODE_WIDTH / 2, Math.min(WORLD_WIDTH - NODE_WIDTH / 2, position.x));
      node.y = Math.max(NODE_HEIGHT / 2, Math.min(WORLD_HEIGHT - NODE_HEIGHT / 2, position.y));
    }
  });
  let view = saved.view && Number.isFinite(saved.view.w) ? saved.view : {x: 0, y: 0, w: WORLD_WIDTH, h: WORLD_HEIGHT};
  let selectedId = null;

  function saveState() {
    try {
      localStorage.setItem(storageKey, JSON.stringify({
        selectedId,
        view,
        positions: Object.fromEntries(nodes.map(node => [node.id, {x: node.x, y: node.y}])),
      }));
    } catch (_) {}
  }
  function applyView() { svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.w} ${view.h}`); }
  function svgElement(name, attributes = {}) { const element = document.createElementNS(NS, name); Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value))); return element; }
  function htmlElement(tag, className, text) { const element = document.createElement(tag); if (className) element.className = className; if (text !== undefined && text !== null) element.textContent = text; return element; }
  function truncate(value, maximum) { if (!value) return ""; return value.length > maximum ? `${value.slice(0, maximum - 1)}…` : value; }
  function action(kind, details = {}) { saveState(); setTriggerValue("action", {kind, ...details, nonce: Date.now()}); }
  function updateEdge(edge) {
    const source = nodeById.get(edge.source); const target = nodeById.get(edge.target);
    if (!source || !target || !edge.element) return;
    edge.element.setAttribute("x1", source.x); edge.element.setAttribute("y1", source.y); edge.element.setAttribute("x2", target.x); edge.element.setAttribute("y2", target.y);
    if (edge.labelElement) { edge.labelElement.setAttribute("x", (source.x + target.x) / 2); edge.labelElement.setAttribute("y", (source.y + target.y) / 2 - 7); }
  }
  function updateNode(node) { if (!node.element) return; node.element.setAttribute("transform", `translate(${node.x - NODE_WIDTH / 2} ${node.y - NODE_HEIGHT / 2})`); edges.filter(edge => edge.source === node.id || edge.target === node.id).forEach(updateEdge); }

  edges.forEach(edge => {
    if (!nodeById.has(edge.source) || !nodeById.has(edge.target)) return;
    const line = svgElement("line", {class: `edge edge-${edge.type}`, "data-edge-id": edge.id});
    if (edge.directed) line.setAttribute("marker-end", "url(#arrow)");
    edge.element = line; edgeLayer.appendChild(line);
    if ((edge.type === "relationship" || edge.type === "mention" || edge.type === "manual") && edge.label) {
      const label = svgElement("text", {class: "edge-label", "data-edge-id": edge.id}); label.textContent = truncate(edge.label, 24); edge.labelElement = label; edgeLabelLayer.appendChild(label);
    }
    updateEdge(edge);
  });

  let dragNode = null; let dragOffset = {x: 0, y: 0}; let nodeMoved = false; let panStart = null;
  nodes.forEach(node => {
    const group = svgElement("g", {class: `node node-${node.type}`, tabindex: "0", role: "button", "aria-label": `${typeLabels[node.type]}: ${node.label}`, "data-node-id": node.id});
    group.appendChild(svgElement("rect", {width: NODE_WIDTH, height: NODE_HEIGHT, rx: 16}));
    const type = svgElement("text", {class: "node-type-label", x: 14, y: 18}); type.textContent = typeLabels[node.type]; group.appendChild(type);
    const label = svgElement("text", {class: "node-label", x: 14, y: 40}); label.textContent = truncate(node.label, 25); group.appendChild(label);
    const subtitle = svgElement("text", {class: "node-subtitle", x: 14, y: 58}); subtitle.textContent = truncate(node.subtitle || "", 29); group.appendChild(subtitle);
    const title = svgElement("title"); title.textContent = `${typeLabels[node.type]}: ${node.label}`; group.appendChild(title);
    node.element = group; nodeLayer.appendChild(group); updateNode(node);
    group.addEventListener("click", event => { event.stopPropagation(); if (nodeMoved) { nodeMoved = false; return; } selectNode(node); });
    group.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectNode(node); } });
    group.addEventListener("pointerdown", event => { event.stopPropagation(); const point = clientToSvg(event.clientX, event.clientY); dragNode = node; dragOffset = {x: point.x - node.x, y: point.y - node.y}; nodeMoved = false; group.setPointerCapture(event.pointerId); });
  });

  function renderEmptyPanel() {
    panel.replaceChildren(); panel.appendChild(htmlElement("p", "panel-eyebrow", "Editor visual")); panel.appendChild(htmlElement("h2", "", data.project));
    panel.appendChild(htmlElement("p", "panel-empty", "Selecione um card para ler seu conteúdo completo, editar, excluir ou criar ligações. A seleção permanecerá ativa até você limpá-la."));
  }
  function panelButton(label, className, handler) { const button = htmlElement("button", `panel-button ${className || ""}`, label); button.type = "button"; button.addEventListener("click", handler); return button; }
  function renderPanel(node) {
    panel.replaceChildren(); panel.appendChild(htmlElement("p", "panel-eyebrow", typeLabels[node.type])); panel.appendChild(htmlElement("h2", "", node.label));
    if (node.subtitle) panel.appendChild(htmlElement("p", "panel-subtitle", node.subtitle));
    if (node.description) panel.appendChild(htmlElement("p", "panel-description", node.description));
    if (node.metrics?.length) { const metrics = htmlElement("div", "panel-metrics"); node.metrics.forEach(metric => { const card = htmlElement("div", "panel-metric"); card.appendChild(htmlElement("span", "", metric.label)); card.appendChild(htmlElement("strong", "", metric.value)); metrics.appendChild(card); }); panel.appendChild(metrics); }
    if (node.content && node.content !== node.description) { const section = htmlElement("section", "panel-content"); section.appendChild(htmlElement("h3", "", node.type === "scene" ? "Conteúdo completo da cena" : "Conteúdo completo")); section.appendChild(htmlElement("div", "panel-content-body", node.content)); panel.appendChild(section); }
    if (node.connections?.length) {
      const section = htmlElement("section", "panel-connections"); section.appendChild(htmlElement("h3", "", `Conexões (${node.connections.length})`)); const list = htmlElement("div", "connection-list");
      node.connections.forEach(connection => { const card = htmlElement("div", "connection-card"); const select = htmlElement("button", "connection-select"); select.type = "button"; select.appendChild(htmlElement("strong", "", connection.label)); select.appendChild(htmlElement("span", "", connection.subtitle)); select.addEventListener("click", () => { const target = nodeById.get(connection.nodeId); if (target) selectNode(target); }); card.appendChild(select);
        if (connection.removable) { const remove = htmlElement("button", "connection-delete", "×"); remove.type = "button"; remove.title = "Excluir ligação"; remove.setAttribute("aria-label", `Excluir ligação com ${connection.label}`); remove.addEventListener("click", event => { event.stopPropagation(); action("delete_edge", {nodeId: node.id, edgeId: connection.edgeId}); }); card.appendChild(remove); }
        list.appendChild(card); }); section.appendChild(list); panel.appendChild(section);
    }
    const actions = htmlElement("div", "panel-actions");
    if (node.type !== "project") { actions.appendChild(panelButton("Editar card", "primary", () => action("edit_node", {nodeId: node.id}))); actions.appendChild(panelButton("Criar ligação", "", () => action("create_edge", {nodeId: node.id}))); actions.appendChild(panelButton("Excluir card", "danger", () => action("delete_node", {nodeId: node.id}))); }
    const open = htmlElement("a", `panel-button ${node.type === "project" ? "primary wide" : ""}`, `Abrir ${typeLabels[node.type].toLowerCase()}`); open.href = node.href; actions.appendChild(open); panel.appendChild(actions);
  }
  function clearSelection() { selectedId = null; nodes.forEach(node => node.element?.classList.remove("is-selected", "is-dimmed")); edges.forEach(edge => { edge.element?.classList.remove("is-active", "is-dimmed"); edge.labelElement?.classList.remove("is-dimmed"); }); renderEmptyPanel(); saveState(); }
  function selectNode(selected) {
    selectedId = selected.id; const connectedEdges = edges.filter(edge => edge.source === selected.id || edge.target === selected.id); const connectedNodes = new Set([selected.id]); connectedEdges.forEach(edge => { connectedNodes.add(edge.source); connectedNodes.add(edge.target); });
    nodes.forEach(node => { node.element?.classList.toggle("is-selected", node.id === selected.id); node.element?.classList.toggle("is-dimmed", !connectedNodes.has(node.id)); });
    edges.forEach(edge => { const active = connectedEdges.includes(edge); edge.element?.classList.toggle("is-active", active); edge.element?.classList.toggle("is-dimmed", !active); edge.labelElement?.classList.toggle("is-dimmed", !active); });
    renderPanel(selected); saveState();
  }
  function clientToSvg(clientX, clientY) { const point = svg.createSVGPoint(); point.x = clientX; point.y = clientY; return point.matrixTransform(svg.getScreenCTM().inverse()); }
  svg.addEventListener("pointermove", event => { if (dragNode) { const point = clientToSvg(event.clientX, event.clientY); const nextX = point.x - dragOffset.x; const nextY = point.y - dragOffset.y; if (Math.abs(nextX - dragNode.x) > 1 || Math.abs(nextY - dragNode.y) > 1) nodeMoved = true; dragNode.x = Math.max(NODE_WIDTH / 2, Math.min(WORLD_WIDTH - NODE_WIDTH / 2, nextX)); dragNode.y = Math.max(NODE_HEIGHT / 2, Math.min(WORLD_HEIGHT - NODE_HEIGHT / 2, nextY)); updateNode(dragNode); return; } if (!panStart) return; const rect = svg.getBoundingClientRect(); view.x = panStart.viewX - ((event.clientX - panStart.clientX) / rect.width) * view.w; view.y = panStart.viewY - ((event.clientY - panStart.clientY) / rect.height) * view.h; applyView(); });
  svg.addEventListener("pointerup", event => { if (dragNode?.element) dragNode.element.releasePointerCapture?.(event.pointerId); dragNode = null; panStart = null; svg.classList.remove("is-panning"); saveState(); });
  svg.addEventListener("pointercancel", () => { dragNode = null; panStart = null; svg.classList.remove("is-panning"); });
  svg.addEventListener("pointerdown", event => { if (event.target.closest?.(".node")) return; panStart = {clientX: event.clientX, clientY: event.clientY, viewX: view.x, viewY: view.y}; svg.classList.add("is-panning"); });
  function zoom(factor, clientX, clientY) { const rect = svg.getBoundingClientRect(); const ratioX = (clientX - rect.left) / rect.width; const ratioY = (clientY - rect.top) / rect.height; const nextW = Math.max(380, Math.min(WORLD_WIDTH * 2.2, view.w * factor)); const nextH = nextW * (view.h / view.w); view.x += ratioX * (view.w - nextW); view.y += ratioY * (view.h - nextH); view.w = nextW; view.h = nextH; applyView(); saveState(); }
  svg.addEventListener("wheel", event => { event.preventDefault(); zoom(event.deltaY > 0 ? 1.12 : .88, event.clientX, event.clientY); }, {passive: false});
  parentElement.querySelector("#zoomIn").addEventListener("click", () => { const rect = svg.getBoundingClientRect(); zoom(.82, rect.left + rect.width / 2, rect.top + rect.height / 2); });
  parentElement.querySelector("#zoomOut").addEventListener("click", () => { const rect = svg.getBoundingClientRect(); zoom(1.18, rect.left + rect.width / 2, rect.top + rect.height / 2); });
  parentElement.querySelector("#fit").addEventListener("click", () => { view = {x: 0, y: 0, w: WORLD_WIDTH, h: WORLD_HEIGHT}; applyView(); saveState(); });
  parentElement.querySelector("#clear").addEventListener("click", clearSelection);
  parentElement.querySelector("#fullscreen").addEventListener("click", () => { if (document.fullscreenElement) document.exitFullscreen(); else shell.requestFullscreen?.(); });
  const keyboard = event => { if (event.key === "Escape" && !document.fullscreenElement) clearSelection(); };
  document.addEventListener("keydown", keyboard);
  applyView(); const restored = [data.initialSelected, saved.selectedId].find(key => key && nodeById.has(key)); if (restored) selectNode(nodeById.get(restored)); else renderEmptyPanel();
  return () => document.removeEventListener("keydown", keyboard);
}
"""


_MAP_COMPONENT = st.components.v2.component(
    "narrative_map_editor",
    html=_HTML,
    css=_CSS.replace("__ACCENT__", "#7C5CFC"),
    js=_JS,
)


def narrative_map_document(
    graph: NarrativeMapGraph,
    theme: str | None = None,
) -> str:
    """Build a script-safe standalone representation used by regression tests."""

    accent = graph.accent_color if _ACCENT_PATTERN.fullmatch(graph.accent_color) else "#7C5CFC"
    active_theme = "light" if theme == "light" else "dark"
    return (
        f'<!doctype html><html data-theme="{active_theme}"><head><style>'
        f"{_CSS.replace('__ACCENT__', accent)}</style></head><body>{_HTML}"
        f'<script type="application/json" id="graphData">{_payload(graph)}</script>'
        f"<script>{_JS}</script></body></html>"
    )


def render_narrative_map(
    graph: NarrativeMapGraph,
    theme: str | None = None,
    *,
    selected_node: str | None = None,
) -> Any:
    """Render the editor and return its latest state/trigger result."""

    return _MAP_COMPONENT(
        key=f"narrative-map-{graph.project_id}",
        data=_graph_data(graph, theme, selected_node),
        width="stretch",
        height=1030,
        on_action_change=lambda: None,
    )
