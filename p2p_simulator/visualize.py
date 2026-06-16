from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import networkx as nx

from .models import P2PNetwork, SearchEvent, SearchResult


def build_graph(network: P2PNetwork) -> nx.Graph:
    graph = nx.Graph()
    for node_id, node in network.nodes.items():
        graph.add_node(node_id, resources=", ".join(sorted(node.resources)))
    for node_id, node in network.nodes.items():
        for neighbor in node.neighbors:
            if node_id < neighbor:
                graph.add_edge(node_id, neighbor)
    return graph


def draw_network(
    network: P2PNetwork,
    result: SearchResult | None = None,
    *,
    output_path: str | Path | None = None,
    show: bool = False,
) -> Path | None:
    graph = build_graph(network)
    pos = nx.spring_layout(graph, seed=42)
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_title(_title(result))
    ax.axis("off")

    visited = result.visited_nodes if result else set()
    holder = result.holder if result else None
    origin = result.origin if result else None

    node_colors = []
    for node_id in graph.nodes:
        if node_id == origin:
            node_colors.append("#3b82f6")
        elif node_id == holder:
            node_colors.append("#22c55e")
        elif node_id in visited:
            node_colors.append("#facc15")
        else:
            node_colors.append("#e5e7eb")

    nx.draw_networkx_edges(graph, pos, ax=ax, edge_color="#9ca3af", width=1.5)
    if result:
        _draw_event_edges(graph, pos, ax, result.events)

    labels = {
        node_id: f"{node_id}\n{graph.nodes[node_id]['resources']}" for node_id in graph.nodes
    }
    nx.draw_networkx_nodes(
        graph,
        pos,
        ax=ax,
        node_color=node_colors,
        node_size=1550,
        edgecolors="#111827",
        linewidths=1.0,
    )
    nx.draw_networkx_labels(graph, pos, labels=labels, ax=ax, font_size=8)

    legend_text = (
        "Azul: origem | Verde: recurso/cache encontrado | Amarelo: nós envolvidos\n"
        "Linhas vermelhas: consultas | Verdes: resposta | Roxa: pedido direto | Azul tracejada: backtracking"
    )
    ax.text(
        0.5,
        -0.06,
        legend_text,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=9,
    )

    saved: Path | None = None
    if output_path:
        saved = Path(output_path)
        saved.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(saved, dpi=160, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    return saved


def animate_search(
    network: P2PNetwork,
    result: SearchResult,
    *,
    output_path: str | Path,
    interval_ms: int = 900,
) -> Path:
    graph = build_graph(network)
    pos = nx.spring_layout(graph, seed=42)
    events = [event for event in result.events if event.event_type in _VISIBLE_EVENT_TYPES]
    if not events:
        events = result.events

    fig, ax = plt.subplots(figsize=(10, 7))

    def update(frame: int) -> None:
        ax.clear()
        ax.axis("off")
        event = events[frame]
        prefix = f"Passo {event.step}: {event.event_type}"
        ax.set_title(f"{_title(result)}\n{prefix} - {event.message}", fontsize=10)

        seen_nodes = {result.origin}
        active_edges: list[tuple[str, str, str]] = []
        for prior in events[: frame + 1]:
            seen_nodes.add(prior.node_id)
            if prior.from_node and prior.to_node:
                if prior.event_type in {"direct_request", "direct_response"}:
                    color = "#8b5cf6"
                elif prior.event_type == "backtrack":
                    color = "#0284c7"
                elif prior.event_type == "response":
                    color = "#22c55e"
                else:
                    color = "#ef4444"
                active_edges.append((prior.from_node, prior.to_node, color))

        node_colors = []
        for node_id in graph.nodes:
            if node_id == result.origin:
                node_colors.append("#3b82f6")
            elif node_id == result.holder and frame == len(events) - 1:
                node_colors.append("#22c55e")
            elif node_id == event.node_id:
                node_colors.append("#f97316")
            elif node_id in seen_nodes:
                node_colors.append("#facc15")
            else:
                node_colors.append("#e5e7eb")

        nx.draw_networkx_edges(graph, pos, ax=ax, edge_color="#d1d5db", width=1.2)
        for left, right, color in active_edges:
            nx.draw_networkx_edges(
                graph,
                pos,
                ax=ax,
                edgelist=[(left, right)],
                edge_color=color,
                width=3.0,
                style="dashed" if color in {"#8b5cf6", "#0284c7"} else "solid",
            )

        labels = {
            node_id: f"{node_id}\n{graph.nodes[node_id]['resources']}" for node_id in graph.nodes
        }
        nx.draw_networkx_nodes(
            graph,
            pos,
            ax=ax,
            node_color=node_colors,
            node_size=1550,
            edgecolors="#111827",
            linewidths=1.0,
        )
        nx.draw_networkx_labels(graph, pos, labels=labels, ax=ax, font_size=8)

    animation = FuncAnimation(fig, update, frames=len(events), interval=interval_ms, repeat=False)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    animation.save(output, writer=PillowWriter(fps=max(1, round(1000 / interval_ms))))
    plt.close(fig)
    return output


def draw_comparison_chart(
    rows: list[dict[str, str | int | float]],
    *,
    output_path: str | Path,
) -> Path:
    algorithms = sorted({str(row["algorithm"]) for row in rows})
    avg_messages = [
        sum(float(row["messages"]) for row in rows if row["algorithm"] == algo)
        / max(1, sum(1 for row in rows if row["algorithm"] == algo))
        for algo in algorithms
    ]
    avg_nodes = [
        sum(float(row["visited_nodes"]) for row in rows if row["algorithm"] == algo)
        / max(1, sum(1 for row in rows if row["algorithm"] == algo))
        for algo in algorithms
    ]

    x_positions = range(len(algorithms))
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar([x - 0.18 for x in x_positions], avg_messages, width=0.36, label="Mensagens")
    ax.bar([x + 0.18 for x in x_positions], avg_nodes, width=0.36, label="Nós envolvidos")
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(algorithms, rotation=15, ha="right")
    ax.set_ylabel("Média por busca")
    ax.set_title("Comparação dos algoritmos de busca P2P")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return output


def _draw_event_edges(graph: nx.Graph, pos: dict[str, tuple[float, float]], ax, events: list[SearchEvent]) -> None:
    query_edges = []
    response_edges = []
    direct_edges = []
    backtrack_edges = []
    for event in events:
        if not event.from_node or not event.to_node:
            continue
        edge = (event.from_node, event.to_node)
        if event.event_type == "query" and graph.has_edge(*edge):
            query_edges.append(edge)
        elif event.event_type == "response" and graph.has_edge(*edge):
            response_edges.append(edge)
        elif event.event_type in {"direct_request", "direct_response"}:
            direct_edges.append(edge)
        elif event.event_type == "backtrack" and graph.has_edge(*edge):
            backtrack_edges.append(edge)

    if query_edges:
        nx.draw_networkx_edges(graph, pos, ax=ax, edgelist=query_edges, edge_color="#ef4444", width=2.5)
    if response_edges:
        nx.draw_networkx_edges(graph, pos, ax=ax, edgelist=response_edges, edge_color="#22c55e", width=3.0)
    if direct_edges:
        nx.draw_networkx_edges(
            graph,
            pos,
            ax=ax,
            edgelist=direct_edges,
            edge_color="#8b5cf6",
            width=2.5,
            style="dashed",
            arrows=True,
        )
    if backtrack_edges:
        nx.draw_networkx_edges(
            graph,
            pos,
            ax=ax,
            edgelist=backtrack_edges,
            edge_color="#0284c7",
            width=2.5,
            style="dashed",
        )


def _title(result: SearchResult | None) -> str:
    if not result:
        return "Rede P2P"
    status = f"encontrado em {result.holder}" if result.found else "não encontrado"
    return (
        f"{result.algorithm} | busca={result.search_id} | {result.resource_id}: {status} | "
        f"mensagens={result.messages}, nós={result.visited_count}"
    )


_VISIBLE_EVENT_TYPES = {
    "start",
    "query",
    "visit",
    "found",
    "cache_hit",
    "parallel_continue",
    "found_again",
    "backtrack",
    "ttl_backtrack",
    "response",
    "direct_request",
    "direct_response",
    "not_found",
}
