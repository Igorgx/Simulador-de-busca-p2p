from __future__ import annotations

import json
import threading
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import networkx as nx

from .config import load_config
from .models import P2PNetwork, SearchEvent, SearchResult, ValidationError
from .search import ALGORITHMS, run_search
from .visualize import build_graph


class DemoApp:
    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self.network = load_config(self.config_path)
        self.positions = _layout_positions(self.network)
        self.lock = threading.RLock()

    def reset_cache(self) -> dict[str, Any]:
        with self.lock:
            self.network.clear_cache()
        return {"ok": True, "message": "Cache limpo."}

    def network_payload(self) -> dict[str, Any]:
        with self.lock:
            network = self.network
            min_degree, max_degree, avg_degree = network.degree_stats()
            return {
                "config": str(self.config_path),
                "node_ids": network.node_ids(),
                "resources": sorted(network.all_resources()),
                "algorithms": sorted(ALGORITHMS),
                "min_neighbors": network.min_neighbors,
                "max_neighbors": network.max_neighbors,
                "degree_stats": {
                    "min": min_degree,
                    "max": max_degree,
                    "avg": round(avg_degree, 2),
                },
                "nodes": [
                    {
                        "id": node.node_id,
                        "resources": sorted(node.resources),
                        "neighbors": sorted(node.neighbors),
                        "cache": dict(sorted(node.cache.items())),
                        "x": self.positions[node.node_id][0],
                        "y": self.positions[node.node_id][1],
                    }
                    for node in network.nodes.values()
                ],
                "edges": _edges(network),
            }

    def run_search(self, data: dict[str, Any]) -> dict[str, Any]:
        origin = str(data.get("origin", ""))
        resource = str(data.get("resource", ""))
        algorithm = str(data.get("algorithm", ""))
        ttl = int(data.get("ttl", 0))
        seed = _optional_int(data.get("seed"))
        direct_get = bool(data.get("direct_get", True))

        with self.lock:
            result = run_search(
                self.network,
                origin,
                resource,
                ttl,
                algorithm,
                seed=seed,
                direct_get=direct_get,
            )
            network_payload = self.network_payload()

        return {
            "result": _result_payload(result),
            "network": network_payload,
        }

    def compare_resource(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resource = _first(query, "resource", "")
        ttl = int(_first(query, "ttl", "4"))
        trials = int(_first(query, "trials", "8"))
        seed = int(_first(query, "seed", "42"))

        rows = compare_algorithms_for_resource(
            self.config_path,
            resource,
            ttl,
            random_trials=max(1, trials),
            seed=seed,
        )
        return {"resource": resource, "ttl": ttl, "trials": trials, "rows": rows}


def run_demo_server(
    config_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    open_browser: bool = True,
) -> None:
    app = DemoApp(config_path)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    self._send_html(DEMO_HTML)
                elif parsed.path == "/api/network":
                    self._send_json(app.network_payload())
                elif parsed.path == "/api/compare":
                    self._send_json(app.compare_resource(parse_qs(parsed.query)))
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
            except Exception as exc:  # pragma: no cover - defensive for live demo
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/search":
                    self._send_json(app.run_search(self._read_json()))
                elif parsed.path == "/api/reset-cache":
                    self._send_json(app.reset_cache())
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
            except ValidationError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:  # pragma: no cover - defensive for live demo
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("JSON precisa ser um objeto.")
            return data

        def _send_html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"Interface de demonstração aberta em: {url}")
    print("Pressione Ctrl+C para encerrar.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()


def compare_algorithms_for_resource(
    config_path: str | Path,
    resource: str,
    ttl: int,
    *,
    random_trials: int = 8,
    seed: int = 42,
) -> list[dict[str, Any]]:
    node_ids = load_config(config_path).node_ids()
    rows: list[dict[str, Any]] = []

    for algorithm in sorted(ALGORITHMS):
        results: list[SearchResult] = []
        trials = random_trials if "random_walk" in algorithm else 1
        for origin in node_ids:
            for attempt in range(trials):
                network = load_config(config_path)
                result = run_search(
                    network,
                    origin,
                    resource,
                    ttl,
                    algorithm,
                    seed=seed + attempt + len(results),
                    direct_get=False,
                )
                results.append(result)

        found = [result for result in results if result.found]
        failures = len(results) - len(found)
        rows.append(
            {
                "algorithm": algorithm,
                "runs": len(results),
                "successes": len(found),
                "failures": failures,
                "min_messages": min((result.messages for result in found), default=None),
                "max_messages": max((result.messages for result in found), default=None),
                "avg_messages": _avg(result.messages for result in found),
                "min_nodes": min((result.visited_count for result in found), default=None),
                "max_nodes": max((result.visited_count for result in found), default=None),
                "avg_nodes": _avg(result.visited_count for result in found),
            }
        )

    return rows


def _layout_positions(network: P2PNetwork) -> dict[str, tuple[float, float]]:
    graph = build_graph(network)
    raw = nx.spring_layout(graph, seed=7)
    xs = [xy[0] for xy in raw.values()]
    ys = [xy[1] for xy in raw.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    positions: dict[str, tuple[float, float]] = {}
    for node_id, xy in raw.items():
        x = 80 + 840 * ((xy[0] - min_x) / (max_x - min_x or 1))
        y = 80 + 560 * ((xy[1] - min_y) / (max_y - min_y or 1))
        positions[str(node_id)] = (round(x, 2), round(y, 2))
    return positions


def _edges(network: P2PNetwork) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    for node_id, node in network.nodes.items():
        for neighbor in node.neighbors:
            if node_id < neighbor:
                edges.append({"source": node_id, "target": neighbor})
    return sorted(edges, key=lambda edge: (edge["source"], edge["target"]))


def _result_payload(result: SearchResult) -> dict[str, Any]:
    return {
        "search_id": result.search_id,
        "algorithm": result.algorithm,
        "origin": result.origin,
        "resource_id": result.resource_id,
        "ttl": result.ttl,
        "found": result.found,
        "holder": result.holder,
        "messages": result.messages,
        "total_messages": result.total_messages,
        "direct_request_messages": result.direct_request_messages,
        "visited_nodes": sorted(result.visited_nodes),
        "visited_count": result.visited_count,
        "response_path": result.response_path,
        "cache_hits": result.cache_hits,
        "events": [_event_payload(event) for event in result.events],
    }


def _event_payload(event: SearchEvent) -> dict[str, Any]:
    data = asdict(event)
    data["path"] = list(event.path)
    return data


def _avg(values: Any) -> float | None:
    items = list(values)
    if not items:
        return None
    return round(sum(items) / len(items), 2)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _first(query: dict[str, list[str]], key: str, default: str) -> str:
    values = query.get(key)
    if not values:
        return default
    return values[0]


DEMO_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Simulador P2P - Demonstração</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7fb;
      --panel: #ffffff;
      --text: #111827;
      --muted: #6b7280;
      --line: #d7dce5;
      --query: #ef4444;
      --response: #16a34a;
      --direct: #7c3aed;
      --origin: #93c5fd;
      --active: #fdba74;
      --visited: #facc15;
      --found: #86efac;
      --idle: #e5e7eb;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      padding: 18px 24px 14px;
      background: #111827;
      color: white;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
    }
    h1 { font-size: 22px; margin: 0; }
    header p { margin: 4px 0 0; color: #cbd5e1; font-size: 13px; }
    main {
      display: grid;
      grid-template-columns: 300px minmax(520px, 1fr) 330px;
      gap: 12px;
      padding: 16px;
      min-height: calc(100vh - 74px);
    }
    .panel {
      background: var(--panel);
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 14px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
    }
    .panel h2 {
      margin: 0 0 12px;
      font-size: 15px;
      letter-spacing: 0;
    }
    label {
      display: block;
      margin: 10px 0 4px;
      color: #374151;
      font-size: 12px;
      font-weight: 700;
    }
    select, input {
      width: 100%;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      padding: 9px 10px;
      font-size: 14px;
      background: white;
      color: var(--text);
    }
    input[type="checkbox"] { width: auto; }
    button {
      border: 0;
      border-radius: 6px;
      padding: 10px 12px;
      font-weight: 800;
      cursor: pointer;
      background: #2563eb;
      color: white;
    }
    button.secondary { background: #e5e7eb; color: #111827; }
    button.warning { background: #f97316; color: white; }
    button:disabled { opacity: 0.45; cursor: not-allowed; }
    .button-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
    .checkbox-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 10px;
      color: #374151;
      font-size: 13px;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 12px;
    }
    .stat {
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 10px;
      background: #f9fafb;
    }
    .stat small {
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-bottom: 4px;
    }
    .stat strong { font-size: 18px; }
    .graph-panel {
      display: grid;
      grid-template-rows: auto minmax(420px, 1fr) auto;
      gap: 12px;
    }
    .graph-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .step-text {
      color: #111827;
      font-weight: 800;
      line-height: 1.35;
    }
    .step-text span {
      display: block;
      color: var(--muted);
      font-weight: 500;
      font-size: 13px;
      margin-top: 3px;
    }
    svg {
      width: 100%;
      height: 100%;
      min-height: 560px;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      background: #ffffff;
    }
    .edge {
      stroke: var(--line);
      stroke-width: 2;
    }
    .edge.query { stroke: var(--query); stroke-width: 5; }
    .edge.response { stroke: var(--response); stroke-width: 5; }
    .edge.direct { stroke: var(--direct); stroke-width: 4; stroke-dasharray: 9 7; }
    .node circle {
      stroke: #111827;
      stroke-width: 2;
      fill: var(--idle);
    }
    .node.origin circle { fill: var(--origin); }
    .node.visited circle { fill: var(--visited); }
    .node.active circle { fill: var(--active); }
    .node.found circle { fill: var(--found); }
    .node text {
      text-anchor: middle;
      dominant-baseline: middle;
      fill: #000000 !important;
      stroke: #ffffff;
      stroke-opacity: 0.75;
      stroke-width: 2px;
      paint-order: stroke fill;
      font-size: 13px;
      font-weight: 900;
      pointer-events: none;
    }
    .node .resources {
      font-size: 11px;
      font-weight: 800;
      fill: #000000 !important;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 16px;
      color: #374151;
      font-size: 12px;
    }
    .legend i {
      display: inline-block;
      width: 14px;
      height: 10px;
      border-radius: 3px;
      margin-right: 5px;
      vertical-align: -1px;
    }
    .timeline {
      width: 100%;
      accent-color: #2563eb;
    }
    .event-list {
      max-height: 310px;
      overflow: auto;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
    }
    .event-item {
      padding: 9px 10px;
      border-bottom: 1px solid #eef2f7;
      font-size: 12px;
      color: #374151;
    }
    .event-item.current {
      color: #111827;
      background: #eff6ff;
      font-weight: 800;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    th, td {
      border-bottom: 1px solid #e5e7eb;
      padding: 7px 6px;
      text-align: left;
    }
    th { color: #374151; background: #f9fafb; }
    .muted { color: var(--muted); }
    .path {
      margin-top: 10px;
      padding: 10px;
      border-radius: 8px;
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      font-size: 13px;
      line-height: 1.4;
    }
    .status-ok { color: #15803d; font-weight: 900; }
    .status-fail { color: #b91c1c; font-weight: 900; }
    @media (max-width: 1250px) {
      main { grid-template-columns: 1fr; }
      svg { min-height: 520px; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Simulador visual de busca P2P</h1>
      <p>Escolha o recurso na hora da apresentação e avance mensagem por mensagem.</p>
    </div>
    <div id="networkSummary" class="muted"></div>
  </header>

  <main>
    <section class="panel">
      <h2>Controle da busca</h2>
      <label for="origin">Nó de origem</label>
      <select id="origin"></select>

      <label for="resource">Recurso procurado</label>
      <select id="resource"></select>

      <label for="algorithm">Algoritmo</label>
      <select id="algorithm"></select>

      <label for="ttl">TTL</label>
      <input id="ttl" type="number" min="0" value="4">

      <label for="seed">Seed do random walk</label>
      <input id="seed" type="number" value="42">

      <div class="checkbox-row">
        <input id="directGet" type="checkbox" checked>
        <span>Mostrar pedido direto do recurso após localizar o nó</span>
      </div>

      <div class="button-row">
        <button id="runSearch">Executar busca</button>
        <button id="resetCache" class="secondary">Limpar cache</button>
      </div>

      <div class="stats">
        <div class="stat"><small>ID da busca</small><strong id="searchId">-</strong></div>
        <div class="stat"><small>Status</small><strong id="status">-</strong></div>
        <div class="stat"><small>Mensagens</small><strong id="messages">0</strong></div>
        <div class="stat"><small>Nós buscados</small><strong id="visited">0</strong></div>
        <div class="stat"><small>TTL atual</small><strong id="ttlNow">-</strong></div>
        <div class="stat"><small>Cache hits</small><strong id="cacheHits">0</strong></div>
      </div>

      <div class="path">
        <strong>Caminho para receber o recurso:</strong>
        <div id="pathText" class="muted">Execute uma busca para ver o caminho.</div>
      </div>
    </section>

    <section class="panel graph-panel">
      <div class="graph-toolbar">
        <div class="step-text" id="stepTitle">Rede pronta para a demonstração<span>O professor pode escolher qualquer recurso da lista.</span></div>
        <div class="button-row">
          <button id="prevStep" class="secondary">Anterior</button>
          <button id="playPause" class="warning">Play</button>
          <button id="nextStep" class="secondary">Próximo</button>
        </div>
      </div>
      <svg id="graph" viewBox="0 0 1000 720" role="img" aria-label="Rede P2P"></svg>
      <div>
        <input id="timeline" class="timeline" type="range" min="0" max="0" value="0">
        <div class="legend">
          <span><i style="background:#93c5fd"></i>origem</span>
          <span><i style="background:#fdba74"></i>passo atual</span>
          <span><i style="background:#facc15"></i>já buscado</span>
          <span><i style="background:#86efac"></i>recurso encontrado</span>
          <span><i style="background:#ef4444"></i>consulta</span>
          <span><i style="background:#16a34a"></i>aviso de retorno</span>
          <span><i style="background:#7c3aed"></i>pedido direto</span>
        </div>
      </div>
    </section>

    <section class="panel">
      <h2>Rastro e min/máx</h2>
      <div class="button-row">
        <button id="compare" class="secondary">Calcular min/máx do recurso</button>
      </div>
      <p class="muted" style="font-size:12px;margin:8px 0 10px;">
        O min/máx roda cada algoritmo a partir de todos os nós. No random walk, usa várias tentativas por causa da aleatoriedade.
      </p>
      <table>
        <thead>
          <tr>
            <th>Algoritmo</th>
            <th>Msg min/máx</th>
            <th>Nós min/máx</th>
            <th>Sucesso</th>
          </tr>
        </thead>
        <tbody id="compareBody">
          <tr><td colspan="4" class="muted">Clique em calcular para o recurso selecionado.</td></tr>
        </tbody>
      </table>

      <h2 style="margin-top:16px;">Passos da busca</h2>
      <div id="eventList" class="event-list">
        <div class="event-item muted">Nenhuma busca executada ainda.</div>
      </div>
    </section>
  </main>

  <script>
    const state = {
      network: null,
      result: null,
      step: 0,
      timer: null,
      playbackMs: 950
    };

    const $ = (id) => document.getElementById(id);

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: {'Content-Type': 'application/json'},
        ...options
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || 'Erro na requisição.');
      return data;
    }

    function fillSelect(select, items) {
      select.innerHTML = '';
      for (const item of items) {
        const option = document.createElement('option');
        option.value = item;
        option.textContent = item;
        select.appendChild(option);
      }
    }

    async function loadNetwork() {
      state.network = await api('/api/network');
      fillSelect($('origin'), state.network.node_ids);
      fillSelect($('resource'), state.network.resources);
      fillSelect($('algorithm'), state.network.algorithms);
      $('networkSummary').textContent = `${state.network.node_ids.length} nós | grau ${state.network.degree_stats.min}/${state.network.degree_stats.max} | config ${state.network.config}`;
      drawGraph();
    }

    async function runSearch() {
      stopPlayback();
      const payload = {
        origin: $('origin').value,
        resource: $('resource').value,
        algorithm: $('algorithm').value,
        ttl: Number($('ttl').value),
        seed: Number($('seed').value),
        direct_get: $('directGet').checked
      };
      const data = await api('/api/search', {method: 'POST', body: JSON.stringify(payload)});
      state.result = data.result;
      state.network = data.network;
      state.step = 0;
      $('timeline').max = Math.max(0, state.result.events.length - 1);
      $('timeline').value = 0;
      updateAll();
    }

    async function resetCache() {
      await api('/api/reset-cache', {method: 'POST', body: '{}'});
      state.network = await api('/api/network');
      drawGraph();
      alert('Cache limpo. As próximas buscas informadas começam sem localizações aprendidas.');
    }

    async function compareSelectedResource() {
      const params = new URLSearchParams({
        resource: $('resource').value,
        ttl: $('ttl').value,
        trials: '10',
        seed: $('seed').value
      });
      const data = await api(`/api/compare?${params}`);
      const body = $('compareBody');
      body.innerHTML = '';
      for (const row of data.rows) {
        const tr = document.createElement('tr');
        const msg = row.min_messages === null ? '-' : `${row.min_messages}/${row.max_messages}`;
        const nodes = row.min_nodes === null ? '-' : `${row.min_nodes}/${row.max_nodes}`;
        const success = `${row.successes}/${row.runs}`;
        tr.innerHTML = `<td>${row.algorithm}</td><td>${msg}</td><td>${nodes}</td><td>${success}</td>`;
        body.appendChild(tr);
      }
    }

    function updateAll() {
      drawGraph();
      updateStats();
      updateEventList();
      $('timeline').value = state.step;
    }

    function currentEvent() {
      if (!state.result || !state.result.events.length) return null;
      return state.result.events[state.step];
    }

    function eventsUntilStep() {
      if (!state.result) return [];
      return state.result.events.slice(0, state.step + 1);
    }

    function updateStats() {
      if (!state.result) return;
      const event = currentEvent();
      const past = eventsUntilStep();
      const messageCount = past.filter(e => ['query', 'response', 'direct_request', 'direct_response'].includes(e.event_type)).length;
      const visited = new Set(past.filter(e => e.event_type === 'visit').map(e => e.node_id));

      $('searchId').textContent = state.result.search_id;
      $('status').innerHTML = state.result.found ? `<span class="status-ok">achou em ${state.result.holder}</span>` : '<span class="status-fail">não achou</span>';
      $('messages').textContent = `${messageCount}/${state.result.total_messages}`;
      $('visited').textContent = `${visited.size}/${state.result.visited_count}`;
      $('ttlNow').textContent = event && event.ttl !== null ? event.ttl : '-';
      $('cacheHits').textContent = state.result.cache_hits;
      $('pathText').textContent = state.result.response_path.length ? state.result.response_path.join(' → ') : 'Recurso não encontrado com este TTL.';

      const title = event ? `Passo ${event.step}: ${labelEvent(event.event_type)}` : 'Rede pronta';
      const detail = event ? event.message : 'Execute uma busca para iniciar.';
      $('stepTitle').innerHTML = `${title}<span>${detail}</span>`;
    }

    function updateEventList() {
      const list = $('eventList');
      list.innerHTML = '';
      if (!state.result) {
        list.innerHTML = '<div class="event-item muted">Nenhuma busca executada ainda.</div>';
        return;
      }
      state.result.events.forEach((event, index) => {
        const item = document.createElement('div');
        item.className = `event-item ${index === state.step ? 'current' : ''}`;
        item.textContent = `${String(event.step).padStart(2, '0')}. [${labelEvent(event.event_type)}] ${event.message}`;
        item.onclick = () => { state.step = index; updateAll(); };
        list.appendChild(item);
      });
      const current = list.querySelector('.current');
      if (current) current.scrollIntoView({block: 'nearest'});
    }

    function drawGraph() {
      if (!state.network) return;
      const svg = $('graph');
      svg.innerHTML = '';

      const active = currentEvent();
      const past = eventsUntilStep();
      const visited = new Set(past.filter(e => e.event_type === 'visit').map(e => e.node_id));
      const foundNow = state.result && state.result.found && past.some(e => ['found', 'cache_hit', 'direct_request', 'direct_response'].includes(e.event_type));

      const edgeLayer = svgEl('g');
      svg.appendChild(edgeLayer);
      for (const edge of state.network.edges) {
        edgeLayer.appendChild(drawEdge(edge.source, edge.target, 'edge'));
      }
      for (const event of past) {
        if (event.from_node && event.to_node) {
          let cls = 'edge query';
          if (event.event_type === 'response') cls = 'edge response';
          if (['direct_request', 'direct_response'].includes(event.event_type)) cls = 'edge direct';
          edgeLayer.appendChild(drawEdge(event.from_node, event.to_node, cls));
        }
      }

      const nodeLayer = svgEl('g');
      svg.appendChild(nodeLayer);
      for (const node of state.network.nodes) {
        let cls = 'node';
        if (state.result && node.id === state.result.origin) cls += ' origin';
        if (visited.has(node.id)) cls += ' visited';
        if (active && active.node_id === node.id) cls += ' active';
        if (foundNow && state.result && node.id === state.result.holder) cls += ' found';
        nodeLayer.appendChild(drawNode(node, cls));
      }
    }

    function drawEdge(sourceId, targetId, cls) {
      const source = findNode(sourceId);
      const target = findNode(targetId);
      const line = svgEl('line');
      line.setAttribute('x1', source.x);
      line.setAttribute('y1', source.y);
      line.setAttribute('x2', target.x);
      line.setAttribute('y2', target.y);
      line.setAttribute('class', cls);
      return line;
    }

    function drawNode(node, cls) {
      const group = svgEl('g');
      group.setAttribute('class', cls);
      group.setAttribute('transform', `translate(${node.x}, ${node.y})`);
      const circle = svgEl('circle');
      circle.setAttribute('r', '38');
      group.appendChild(circle);

      const idText = svgEl('text');
      idText.setAttribute('y', '-8');
      idText.setAttribute('fill', '#000000');
      idText.setAttribute('stroke', '#ffffff');
      idText.setAttribute('stroke-opacity', '0.75');
      idText.setAttribute('stroke-width', '2');
      idText.setAttribute('paint-order', 'stroke fill');
      idText.textContent = node.id;
      group.appendChild(idText);

      const resText = svgEl('text');
      resText.setAttribute('class', 'resources');
      resText.setAttribute('y', '12');
      resText.setAttribute('fill', '#000000');
      resText.setAttribute('stroke', '#ffffff');
      resText.setAttribute('stroke-opacity', '0.75');
      resText.setAttribute('stroke-width', '2');
      resText.setAttribute('paint-order', 'stroke fill');
      resText.textContent = compact(node.resources.join(', '), 18);
      group.appendChild(resText);

      const title = svgEl('title');
      const cache = Object.keys(node.cache).length ? `\nCache: ${Object.entries(node.cache).map(([k, v]) => `${k}->${v}`).join(', ')}` : '';
      title.textContent = `${node.id}\nRecursos: ${node.resources.join(', ')}\nVizinhos: ${node.neighbors.join(', ')}${cache}`;
      group.appendChild(title);
      return group;
    }

    function findNode(nodeId) {
      return state.network.nodes.find(n => n.id === nodeId);
    }

    function svgEl(tag) {
      return document.createElementNS('http://www.w3.org/2000/svg', tag);
    }

    function compact(text, max) {
      return text.length > max ? `${text.slice(0, max - 1)}…` : text;
    }

    function labelEvent(type) {
      const labels = {
        start: 'início',
        visit: 'nó buscado',
        query: 'mensagem de busca',
        response: 'aviso de retorno',
        found: 'recurso encontrado',
        cache_hit: 'cache encontrou',
        cache_update: 'cache atualizado',
        ttl_expired: 'TTL acabou',
        duplicate: 'duplicata ignorada',
        not_found: 'não encontrado',
        direct_request: 'pedido direto',
        direct_response: 'recurso recebido',
        dead_end: 'sem vizinho'
      };
      return labels[type] || type;
    }

    function step(delta) {
      if (!state.result) return;
      state.step = Math.max(0, Math.min(state.result.events.length - 1, state.step + delta));
      updateAll();
    }

    function togglePlayback() {
      if (state.timer) {
        stopPlayback();
        return;
      }
      if (!state.result) return;
      $('playPause').textContent = 'Pause';
      state.timer = setInterval(() => {
        if (!state.result || state.step >= state.result.events.length - 1) {
          stopPlayback();
          return;
        }
        step(1);
      }, state.playbackMs);
    }

    function stopPlayback() {
      if (state.timer) clearInterval(state.timer);
      state.timer = null;
      $('playPause').textContent = 'Play';
    }

    $('runSearch').onclick = () => runSearch().catch(err => alert(err.message));
    $('resetCache').onclick = () => resetCache().catch(err => alert(err.message));
    $('compare').onclick = () => compareSelectedResource().catch(err => alert(err.message));
    $('prevStep').onclick = () => step(-1);
    $('nextStep').onclick = () => step(1);
    $('playPause').onclick = togglePlayback;
    $('timeline').oninput = (event) => {
      state.step = Number(event.target.value);
      updateAll();
    };

    loadNetwork().catch(err => alert(err.message));
  </script>
</body>
</html>
"""
