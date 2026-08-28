# ruff: noqa: E501
"""Self-contained interactive SVG narrative map for Streamlit."""

from __future__ import annotations

import json
import re

import streamlit as st

from services.narrative_map_service import NarrativeMapGraph

_ACCENT_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def _payload(graph: NarrativeMapGraph) -> str:
    data = {
        "project": graph.project_name,
        "nodes": [
            {
                "id": node.key,
                "type": node.node_type.value,
                "label": node.label,
                "subtitle": node.subtitle,
                "description": node.description,
                "href": node.href,
                "metrics": [
                    {"label": metric.label, "value": metric.value} for metric in node.metrics
                ],
                "itemsTitle": node.items_title,
                "items": list(node.items),
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
            }
            for edge in graph.edges
        ],
    }
    return (
        json.dumps(data, ensure_ascii=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


_DOCUMENT = r"""
<!doctype html>
<html lang="pt-BR" data-theme="__THEME__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root {
    color-scheme: dark;
    --accent: __ACCENT__;
    --bg: #11131a;
    --surface: rgba(31, 34, 45, .78);
    --surface-soft: rgba(35, 38, 50, .56);
    --border: rgba(255, 255, 255, .12);
    --text: #f4f5fb;
    --muted: #a9adbd;
    --edge: rgba(190, 195, 212, .34);
    --shadow: 0 18px 50px rgba(0, 0, 0, .24);
  }
  html[data-theme="light"] {
    color-scheme: light;
    --bg: #eef0f6;
    --surface: rgba(255, 255, 255, .82);
    --surface-soft: rgba(255, 255, 255, .58);
    --border: rgba(40, 43, 58, .13);
    --text: #181a22;
    --muted: #686c7b;
    --edge: rgba(76, 80, 98, .32);
    --shadow: 0 18px 45px rgba(52, 56, 74, .12);
  }
  * { box-sizing: border-box; }
  body {
    background: transparent;
    color: var(--text);
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    margin: 0;
    overflow: hidden;
  }
  button, a { font: inherit; }
  .map-shell {
    background:
      radial-gradient(circle at 18% 8%, color-mix(in srgb, var(--accent) 10%, transparent), transparent 32%),
      var(--bg);
    border: 1px solid var(--border);
    border-radius: 22px;
    box-shadow: var(--shadow), inset 0 1px 0 rgba(255, 255, 255, .06);
    height: 880px;
    overflow: hidden;
  }
  .map-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 310px;
    height: 100%;
    min-width: 0;
  }
  .map-stage {
    min-width: 0;
    overflow: hidden;
    position: relative;
  }
  #graph {
    cursor: grab;
    display: block;
    height: 100%;
    min-width: 0;
    touch-action: none;
    width: 100%;
  }
  #graph.is-panning { cursor: grabbing; }
  .map-controls {
    display: flex;
    gap: 6px;
    left: 14px;
    position: absolute;
    top: 14px;
    z-index: 4;
  }
  .map-controls button {
    align-items: center;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    cursor: pointer;
    display: inline-flex;
    font-size: 18px;
    height: 38px;
    justify-content: center;
    min-width: 38px;
    padding: 0 10px;
  }
  .map-controls button:last-child { font-size: 12px; font-weight: 750; }
  .map-controls button:hover { border-color: color-mix(in srgb, var(--accent) 48%, var(--border)); }
  .map-legend {
    align-items: center;
    backdrop-filter: blur(12px);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    bottom: 14px;
    display: flex;
    flex-wrap: wrap;
    gap: 9px 12px;
    left: 14px;
    padding: 8px 10px;
    position: absolute;
    z-index: 4;
  }
  .map-legend span { align-items: center; color: var(--muted); display: flex; font-size: 11px; gap: 5px; }
  .map-legend i { border-radius: 50%; display: inline-block; height: 8px; width: 8px; }
  .legend-project { background: var(--accent); }
  .legend-chapter { background: #7697f8; }
  .legend-scene { background: #55b99a; }
  .legend-character { background: #b181ef; }
  .legend-section { background: #ed9f56; }
  .edge {
    stroke: var(--edge);
    stroke-linecap: round;
    stroke-width: 1.7;
    transition: opacity .18s ease, stroke .18s ease, stroke-width .18s ease;
  }
  .edge-appearance { stroke: color-mix(in srgb, #55b99a 58%, var(--edge)); stroke-dasharray: 5 6; }
  .edge-relationship { stroke: color-mix(in srgb, #b181ef 70%, var(--edge)); stroke-width: 2; }
  .edge-mention { stroke: color-mix(in srgb, #ed9f56 76%, var(--edge)); stroke-dasharray: 3 5; stroke-width: 2.2; }
  .edge.is-active { stroke: var(--accent); stroke-width: 3; opacity: 1; }
  .edge.is-dimmed, .edge-label.is-dimmed { opacity: .08; }
  .edge-label {
    fill: var(--muted);
    font-size: 10px;
    font-weight: 700;
    paint-order: stroke;
    pointer-events: none;
    stroke: var(--bg);
    stroke-width: 4px;
    text-anchor: middle;
    transition: opacity .18s ease;
  }
  .node { cursor: pointer; outline: none; transition: opacity .18s ease; }
  .node.is-dimmed { opacity: .15; }
  .node rect {
    fill: var(--surface);
    stroke: var(--border);
    stroke-width: 1.5;
    transition: filter .18s ease, stroke .18s ease, stroke-width .18s ease;
  }
  .node:hover rect, .node:focus rect { filter: brightness(1.1); stroke: var(--accent); }
  .node.is-selected rect { filter: drop-shadow(0 8px 16px color-mix(in srgb, var(--accent) 26%, transparent)); stroke: var(--accent); stroke-width: 3; }
  .node-project rect { fill: color-mix(in srgb, var(--accent) 24%, var(--surface)); }
  .node-chapter rect { fill: color-mix(in srgb, #7697f8 18%, var(--surface)); }
  .node-scene rect { fill: color-mix(in srgb, #55b99a 17%, var(--surface)); }
  .node-character rect { fill: color-mix(in srgb, #b181ef 17%, var(--surface)); }
  .node-section rect { fill: color-mix(in srgb, #ed9f56 18%, var(--surface)); }
  .node-type-label { fill: var(--muted); font-size: 9px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; }
  .node-label { fill: var(--text); font-size: 13px; font-weight: 750; }
  .node-subtitle { fill: var(--muted); font-size: 10px; }
  .node-panel {
    background: color-mix(in srgb, var(--surface) 90%, transparent);
    border-left: 1px solid var(--border);
    min-width: 0;
    overflow: auto;
    padding: 24px 20px;
  }
  .panel-eyebrow { color: var(--accent); font-size: 10px; font-weight: 800; letter-spacing: 1.2px; margin: 0; text-transform: uppercase; }
  .node-panel h2 { font-size: 24px; letter-spacing: -.035em; line-height: 1.08; margin: 8px 0 0; overflow-wrap: anywhere; }
  .panel-subtitle { color: var(--muted); font-size: 13px; line-height: 1.5; margin: 8px 0 0; overflow-wrap: anywhere; }
  .panel-description { font-size: 13px; line-height: 1.6; margin: 18px 0 0; overflow-wrap: anywhere; white-space: pre-wrap; }
  .panel-metrics { display: grid; gap: 8px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 18px; }
  .panel-metric { background: var(--surface-soft); border: 1px solid var(--border); border-radius: 12px; min-width: 0; padding: 10px; }
  .panel-metric span { color: var(--muted); display: block; font-size: 9px; font-weight: 800; letter-spacing: .7px; text-transform: uppercase; }
  .panel-metric strong { display: block; font-size: 16px; margin-top: 4px; overflow-wrap: anywhere; }
  .panel-items { margin-top: 20px; }
  .panel-items h3 { font-size: 12px; margin: 0 0 8px; }
  .panel-items ul { display: grid; gap: 6px; list-style: none; margin: 0; padding: 0; }
  .panel-items li { background: var(--surface-soft); border: 1px solid var(--border); border-radius: 9px; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; padding: 8px 9px; }
  .panel-open {
    align-items: center;
    background: var(--accent);
    border-radius: 11px;
    color: white;
    display: flex;
    font-size: 13px;
    font-weight: 760;
    justify-content: center;
    margin-top: 22px;
    min-height: 42px;
    padding: 10px 12px;
    text-decoration: none;
  }
  .panel-empty { color: var(--muted); line-height: 1.6; margin-top: 12px; }
  @media (max-width: 700px) {
    body { overflow: auto; }
    .map-shell { height: 880px; }
    .map-layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: 530px 350px; }
    .node-panel { border-left: 0; border-top: 1px solid var(--border); padding: 18px 16px; }
    .map-legend { bottom: 10px; left: 10px; right: 10px; }
    .map-controls { left: 10px; top: 10px; }
    .panel-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { transition-duration: .01ms !important; }
  }
</style>
</head>
<body>
<main class="map-shell">
  <div class="map-layout">
    <section class="map-stage" aria-label="Mapa narrativo interativo">
      <div class="map-controls" aria-label="Controles do mapa">
        <button id="zoomIn" type="button" title="Aproximar" aria-label="Aproximar">+</button>
        <button id="zoomOut" type="button" title="Afastar" aria-label="Afastar">−</button>
        <button id="fit" type="button" title="Enquadrar mapa">Enquadrar</button>
      </div>
      <svg id="graph" role="application" aria-label="Nós e conexões narrativas">
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
        <span><i class="legend-section"></i>Seção GDD / @menção</span>
      </div>
    </section>
    <aside id="panel" class="node-panel" aria-live="polite"></aside>
  </div>
</main>
<script>
(() => {
  "use strict";
  const data = __GRAPH_DATA__;
  const svg = document.getElementById("graph");
  const edgeLayer = document.getElementById("edgeLayer");
  const edgeLabelLayer = document.getElementById("edgeLabelLayer");
  const nodeLayer = document.getElementById("nodeLayer");
  const panel = document.getElementById("panel");
  const NS = "http://www.w3.org/2000/svg";
  const NODE_WIDTH = 170;
  const NODE_HEIGHT = 66;
  const typeLabels = {project: "Projeto", chapter: "Capítulo", scene: "Cena", character: "Personagem", section: "Seção GDD"};
  const nodes = data.nodes.map(node => ({...node, x: 0, y: 0, element: null}));
  const edges = data.edges.map(edge => ({...edge, element: null, labelElement: null}));
  const nodeById = new Map(nodes.map(node => [node.id, node]));
  const typeCounts = nodes.reduce((counts, node) => {
    counts[node.type] = (counts[node.type] || 0) + 1;
    return counts;
  }, {});
  const largestLayer = Math.max(1, ...Object.values(typeCounts));
  const WORLD_WIDTH = Math.max(760, Math.min(1500, largestLayer * 210 + 240));

  function distribute(items, startY) {
    if (!items.length) return startY;
    const perRow = Math.max(1, Math.min(7, Math.floor((WORLD_WIDTH - 120) / 190)));
    const rows = Math.ceil(items.length / perRow);
    items.forEach((node, index) => {
      const row = Math.floor(index / perRow);
      const rowStart = row * perRow;
      const rowCount = Math.min(perRow, items.length - rowStart);
      const slot = index - rowStart;
      const spacing = WORLD_WIDTH / (rowCount + 1);
      node.x = spacing * (slot + 1);
      node.y = startY + row * 112;
    });
    return startY + rows * 112;
  }

  const projectNodes = nodes.filter(node => node.type === "project");
  const chapterNodes = nodes.filter(node => node.type === "chapter");
  const sceneNodes = nodes.filter(node => node.type === "scene");
  const characterNodes = nodes.filter(node => node.type === "character");
  const sectionNodes = nodes.filter(node => node.type === "section");
  projectNodes.forEach(node => { node.x = WORLD_WIDTH / 2; node.y = 88; });
  let nextY = distribute(chapterNodes, 230) + 85;
  nextY = distribute(sceneNodes, nextY) + 85;
  nextY = distribute(characterNodes, nextY) + 90;
  nextY = distribute(sectionNodes, nextY) + 90;
  const WORLD_HEIGHT = Math.max(720, nextY);
  let view = {x: 0, y: 0, w: WORLD_WIDTH, h: WORLD_HEIGHT};

  function applyView() {
    svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.w} ${view.h}`);
  }

  function svgElement(name, attributes = {}) {
    const element = document.createElementNS(NS, name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  }

  function truncate(value, maximum) {
    if (!value) return "";
    return value.length > maximum ? `${value.slice(0, maximum - 1)}…` : value;
  }

  function updateEdge(edge) {
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    if (!source || !target || !edge.element) return;
    edge.element.setAttribute("x1", source.x);
    edge.element.setAttribute("y1", source.y);
    edge.element.setAttribute("x2", target.x);
    edge.element.setAttribute("y2", target.y);
    if (edge.labelElement) {
      edge.labelElement.setAttribute("x", (source.x + target.x) / 2);
      edge.labelElement.setAttribute("y", (source.y + target.y) / 2 - 7);
    }
  }

  function updateNode(node) {
    if (!node.element) return;
    node.element.setAttribute(
      "transform",
      `translate(${node.x - NODE_WIDTH / 2} ${node.y - NODE_HEIGHT / 2})`
    );
    edges.filter(edge => edge.source === node.id || edge.target === node.id).forEach(updateEdge);
  }

  edges.forEach(edge => {
    if (!nodeById.has(edge.source) || !nodeById.has(edge.target)) return;
    const line = svgElement("line", {class: `edge edge-${edge.type}`, "data-edge-id": edge.id});
    if (edge.directed) line.setAttribute("marker-end", "url(#arrow)");
    edge.element = line;
    edgeLayer.appendChild(line);
    if ((edge.type === "relationship" || edge.type === "mention") && edge.label) {
      const label = svgElement("text", {class: "edge-label", "data-edge-id": edge.id});
      label.textContent = truncate(edge.label, 22);
      edge.labelElement = label;
      edgeLabelLayer.appendChild(label);
    }
    updateEdge(edge);
  });

  let dragNode = null;
  let dragOffset = {x: 0, y: 0};
  let nodeMoved = false;

  nodes.forEach(node => {
    const group = svgElement("g", {
      class: `node node-${node.type}`,
      tabindex: "0",
      role: "button",
      "aria-label": `${typeLabels[node.type]}: ${node.label}`,
      "data-node-id": node.id,
    });
    group.appendChild(svgElement("rect", {width: NODE_WIDTH, height: NODE_HEIGHT, rx: 16}));
    const type = svgElement("text", {class: "node-type-label", x: 14, y: 17});
    type.textContent = typeLabels[node.type];
    group.appendChild(type);
    const label = svgElement("text", {class: "node-label", x: 14, y: 38});
    label.textContent = truncate(node.label, 23);
    group.appendChild(label);
    const subtitle = svgElement("text", {class: "node-subtitle", x: 14, y: 55});
    subtitle.textContent = truncate(node.subtitle || "", 27);
    group.appendChild(subtitle);
    const title = svgElement("title");
    title.textContent = `${typeLabels[node.type]}: ${node.label}`;
    group.appendChild(title);
    node.element = group;
    nodeLayer.appendChild(group);
    updateNode(node);
    group.addEventListener("click", event => {
      event.stopPropagation();
      if (nodeMoved) { nodeMoved = false; return; }
      selectNode(node);
    });
    group.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectNode(node);
      }
    });
    group.addEventListener("pointerdown", event => {
      event.stopPropagation();
      const point = clientToSvg(event.clientX, event.clientY);
      dragNode = node;
      dragOffset = {x: point.x - node.x, y: point.y - node.y};
      nodeMoved = false;
      group.setPointerCapture(event.pointerId);
    });
  });

  function htmlElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = text;
    return element;
  }

  function renderEmptyPanel() {
    panel.replaceChildren();
    panel.appendChild(htmlElement("p", "panel-eyebrow", "Mapa narrativo"));
    panel.appendChild(htmlElement("h2", "", data.project));
    panel.appendChild(
      htmlElement(
        "p",
        "panel-empty",
        "Selecione um nó para ver suas informações e conexões. Arraste o mapa, use o zoom ou reposicione os nós."
      )
    );
  }

  function renderPanel(node) {
    panel.replaceChildren();
    panel.appendChild(htmlElement("p", "panel-eyebrow", typeLabels[node.type]));
    panel.appendChild(htmlElement("h2", "", node.label));
    if (node.subtitle) panel.appendChild(htmlElement("p", "panel-subtitle", node.subtitle));
    if (node.description) panel.appendChild(htmlElement("p", "panel-description", node.description));
    if (node.metrics && node.metrics.length) {
      const metrics = htmlElement("div", "panel-metrics");
      node.metrics.forEach(metric => {
        const card = htmlElement("div", "panel-metric");
        card.appendChild(htmlElement("span", "", metric.label));
        card.appendChild(htmlElement("strong", "", metric.value));
        metrics.appendChild(card);
      });
      panel.appendChild(metrics);
    }
    if (node.items && node.items.length) {
      const section = htmlElement("section", "panel-items");
      section.appendChild(htmlElement("h3", "", node.itemsTitle || "Conexões"));
      const list = htmlElement("ul");
      node.items.slice(0, 20).forEach(item => list.appendChild(htmlElement("li", "", item)));
      if (node.items.length > 20) {
        list.appendChild(htmlElement("li", "", `+ ${node.items.length - 20} itens`));
      }
      section.appendChild(list);
      panel.appendChild(section);
    }
    const open = htmlElement("a", "panel-open", `Abrir ${typeLabels[node.type].toLowerCase()}`);
    open.href = node.href;
    open.target = "_top";
    panel.appendChild(open);
  }

  function clearSelection() {
    nodes.forEach(node => node.element?.classList.remove("is-selected", "is-dimmed"));
    edges.forEach(edge => {
      edge.element?.classList.remove("is-active", "is-dimmed");
      edge.labelElement?.classList.remove("is-dimmed");
    });
    renderEmptyPanel();
  }

  function selectNode(selected) {
    const connectedEdges = edges.filter(edge => edge.source === selected.id || edge.target === selected.id);
    const connectedNodes = new Set([selected.id]);
    connectedEdges.forEach(edge => {
      connectedNodes.add(edge.source);
      connectedNodes.add(edge.target);
    });
    nodes.forEach(node => {
      node.element?.classList.toggle("is-selected", node.id === selected.id);
      node.element?.classList.toggle("is-dimmed", !connectedNodes.has(node.id));
    });
    edges.forEach(edge => {
      const active = connectedEdges.includes(edge);
      edge.element?.classList.toggle("is-active", active);
      edge.element?.classList.toggle("is-dimmed", !active);
      edge.labelElement?.classList.toggle("is-dimmed", !active);
    });
    renderPanel(selected);
  }

  function clientToSvg(clientX, clientY) {
    const point = svg.createSVGPoint();
    point.x = clientX;
    point.y = clientY;
    return point.matrixTransform(svg.getScreenCTM().inverse());
  }

  svg.addEventListener("pointermove", event => {
    if (dragNode) {
      const point = clientToSvg(event.clientX, event.clientY);
      const nextX = point.x - dragOffset.x;
      const nextY = point.y - dragOffset.y;
      if (Math.abs(nextX - dragNode.x) > 1 || Math.abs(nextY - dragNode.y) > 1) nodeMoved = true;
      dragNode.x = Math.max(NODE_WIDTH / 2, Math.min(WORLD_WIDTH - NODE_WIDTH / 2, nextX));
      dragNode.y = Math.max(NODE_HEIGHT / 2, Math.min(WORLD_HEIGHT - NODE_HEIGHT / 2, nextY));
      updateNode(dragNode);
      return;
    }
    if (!panStart) return;
    const rect = svg.getBoundingClientRect();
    view.x = panStart.viewX - ((event.clientX - panStart.clientX) / rect.width) * view.w;
    view.y = panStart.viewY - ((event.clientY - panStart.clientY) / rect.height) * view.h;
    applyView();
  });

  svg.addEventListener("pointerup", event => {
    if (dragNode?.element) dragNode.element.releasePointerCapture?.(event.pointerId);
    dragNode = null;
    panStart = null;
    svg.classList.remove("is-panning");
  });
  svg.addEventListener("pointercancel", () => {
    dragNode = null;
    panStart = null;
    svg.classList.remove("is-panning");
  });

  let panStart = null;
  svg.addEventListener("pointerdown", event => {
    if (event.target.closest?.(".node")) return;
    panStart = {clientX: event.clientX, clientY: event.clientY, viewX: view.x, viewY: view.y};
    svg.classList.add("is-panning");
  });
  svg.addEventListener("click", event => {
    if (!event.target.closest?.(".node")) clearSelection();
  });

  function zoom(factor, clientX, clientY) {
    const rect = svg.getBoundingClientRect();
    const ratioX = (clientX - rect.left) / rect.width;
    const ratioY = (clientY - rect.top) / rect.height;
    const nextW = Math.max(360, Math.min(WORLD_WIDTH * 2.2, view.w * factor));
    const nextH = nextW * (view.h / view.w);
    view.x += ratioX * (view.w - nextW);
    view.y += ratioY * (view.h - nextH);
    view.w = nextW;
    view.h = nextH;
    applyView();
  }

  svg.addEventListener("wheel", event => {
    event.preventDefault();
    zoom(event.deltaY > 0 ? 1.12 : .88, event.clientX, event.clientY);
  }, {passive: false});
  document.getElementById("zoomIn").addEventListener("click", () => {
    const rect = svg.getBoundingClientRect();
    zoom(.82, rect.left + rect.width / 2, rect.top + rect.height / 2);
  });
  document.getElementById("zoomOut").addEventListener("click", () => {
    const rect = svg.getBoundingClientRect();
    zoom(1.18, rect.left + rect.width / 2, rect.top + rect.height / 2);
  });
  document.getElementById("fit").addEventListener("click", () => {
    view = {x: 0, y: 0, w: WORLD_WIDTH, h: WORLD_HEIGHT};
    applyView();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") clearSelection();
  });

  applyView();
  renderEmptyPanel();
})();
</script>
</body>
</html>
"""


def narrative_map_document(
    graph: NarrativeMapGraph,
    theme: str | None = None,
) -> str:
    """Build a self-contained map document with safely encoded project data."""

    accent = graph.accent_color if _ACCENT_PATTERN.fullmatch(graph.accent_color) else "#7C5CFC"
    active_theme = "light" if theme == "light" else "dark"
    return (
        _DOCUMENT.replace("__GRAPH_DATA__", _payload(graph))
        .replace("__ACCENT__", accent)
        .replace("__THEME__", active_theme)
    )


def render_narrative_map(
    graph: NarrativeMapGraph,
    theme: str | None = None,
) -> None:
    st.iframe(
        narrative_map_document(graph, theme),
        width="stretch",
        height=900,
        tab_index=0,
    )
