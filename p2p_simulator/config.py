from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import Node, P2PNetwork, ValidationError


def load_config(path: str | Path) -> P2PNetwork:
    config_path = Path(path)
    raw = config_path.read_text(encoding="utf-8")

    if config_path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        data = yaml.safe_load(raw)

    if not isinstance(data, dict):
        raise ValidationError("O arquivo de configuração deve conter um objeto JSON/YAML.")

    return network_from_dict(data)


def network_from_dict(data: dict[str, Any]) -> P2PNetwork:
    try:
        num_nodes = int(data["num_nodes"])
        min_neighbors = int(data["min_neighbors"])
        max_neighbors = int(data["max_neighbors"])
    except KeyError as exc:
        raise ValidationError(f"Campo obrigatório ausente: {exc.args[0]}") from exc

    if num_nodes <= 0:
        raise ValidationError("num_nodes deve ser maior que zero.")

    node_ids = [f"n{i}" for i in range(1, num_nodes + 1)]
    resources = _normalize_resources(data.get("resources", {}))
    edges = _normalize_edges(data.get("edges", []))

    extra_nodes = set(resources) - set(node_ids)
    if extra_nodes:
        raise ValidationError(
            "Recursos definidos para nós fora de num_nodes: " + ", ".join(sorted(extra_nodes))
        )

    nodes = {
        node_id: Node(node_id=node_id, resources=set(resources.get(node_id, [])))
        for node_id in node_ids
    }

    for left, right in edges:
        if left == right:
            raise ValidationError(f"Aresta inválida de {left} para ele mesmo.")
        if left not in nodes or right not in nodes:
            raise ValidationError(f"Aresta referencia nó inexistente: {left}, {right}.")
        nodes[left].neighbors.add(right)
        nodes[right].neighbors.add(left)

    network = P2PNetwork(nodes, min_neighbors, max_neighbors)
    network.validate()
    return network


def _normalize_resources(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise ValidationError("resources deve ser um mapa de nó para lista de recursos.")

    normalized: dict[str, list[str]] = {}
    for node_id, resources in value.items():
        if isinstance(resources, str):
            items = [item.strip() for item in resources.split(",") if item.strip()]
        elif isinstance(resources, list):
            items = [str(item).strip() for item in resources if str(item).strip()]
        else:
            raise ValidationError(f"Recursos de {node_id} devem ser lista ou string.")
        normalized[str(node_id)] = items
    return normalized


def _normalize_edges(value: Any) -> list[tuple[str, str]]:
    if not isinstance(value, list):
        raise ValidationError("edges deve ser uma lista de pares de nós.")

    edges: list[tuple[str, str]] = []
    for edge in value:
        if isinstance(edge, str):
            parts = [part.strip() for part in edge.split(",")]
        elif isinstance(edge, list) and len(edge) == 2:
            parts = [str(edge[0]).strip(), str(edge[1]).strip()]
        else:
            raise ValidationError(f"Aresta inválida: {edge!r}")

        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValidationError(f"Aresta inválida: {edge!r}")
        edges.append((parts[0], parts[1]))

    return edges
