from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class Node:
    node_id: str
    resources: set[str] = field(default_factory=set)
    neighbors: set[str] = field(default_factory=set)
    cache: dict[str, str] = field(default_factory=dict)

    def has_resource(self, resource_id: str) -> bool:
        return resource_id in self.resources

    def knows_resource(self, resource_id: str) -> str | None:
        if self.has_resource(resource_id):
            return self.node_id
        return self.cache.get(resource_id)


@dataclass
class SearchEvent:
    step: int
    event_type: str
    node_id: str
    message: str
    from_node: str | None = None
    to_node: str | None = None
    ttl: int | None = None
    path: tuple[str, ...] = ()


@dataclass
class SearchResult:
    search_id: str
    algorithm: str
    origin: str
    resource_id: str
    ttl: int
    found: bool
    holder: str | None
    messages: int
    visited_nodes: set[str]
    events: list[SearchEvent]
    response_path: list[str] = field(default_factory=list)
    cache_hits: int = 0
    direct_request_messages: int = 0

    @property
    def visited_count(self) -> int:
        return len(self.visited_nodes)

    @property
    def total_messages(self) -> int:
        return self.messages + self.direct_request_messages


class ValidationError(ValueError):
    pass


class P2PNetwork:
    def __init__(
        self,
        nodes: dict[str, Node],
        min_neighbors: int,
        max_neighbors: int,
    ) -> None:
        self.nodes = nodes
        self.min_neighbors = min_neighbors
        self.max_neighbors = max_neighbors

    def get(self, node_id: str) -> Node:
        return self.nodes[node_id]

    def node_ids(self) -> list[str]:
        return sorted(self.nodes)

    def resource_locations(self, resource_id: str) -> list[str]:
        return sorted(
            node.node_id for node in self.nodes.values() if resource_id in node.resources
        )

    def all_resources(self) -> set[str]:
        resources: set[str] = set()
        for node in self.nodes.values():
            resources.update(node.resources)
        return resources

    def add_cache_entry(self, node_ids: Iterable[str], resource_id: str, holder: str) -> None:
        for node_id in node_ids:
            if node_id != holder:
                self.nodes[node_id].cache[resource_id] = holder

    def clear_cache(self) -> None:
        for node in self.nodes.values():
            node.cache.clear()

    def degree_stats(self) -> tuple[int, int, float]:
        degrees = [len(node.neighbors) for node in self.nodes.values()]
        return min(degrees), max(degrees), sum(degrees) / len(degrees)

    def validate(self) -> None:
        if not self.nodes:
            raise ValidationError("A rede precisa ter pelo menos um nó.")

        for node in self.nodes.values():
            if not node.resources:
                raise ValidationError(f"O nó {node.node_id} não possui recursos.")

            degree = len(node.neighbors)
            if degree < self.min_neighbors or degree > self.max_neighbors:
                raise ValidationError(
                    f"O nó {node.node_id} possui {degree} vizinhos; "
                    f"o permitido é entre {self.min_neighbors} e {self.max_neighbors}."
                )

            if node.node_id in node.neighbors:
                raise ValidationError(f"O nó {node.node_id} possui aresta para ele mesmo.")

            for neighbor_id in node.neighbors:
                if neighbor_id not in self.nodes:
                    raise ValidationError(
                        f"O nó {node.node_id} referencia vizinho inexistente {neighbor_id}."
                    )

        self._validate_connected()

    def _validate_connected(self) -> None:
        first = next(iter(self.nodes))
        seen = {first}
        stack = [first]
        while stack:
            current = stack.pop()
            for neighbor_id in self.nodes[current].neighbors:
                if neighbor_id not in seen:
                    seen.add(neighbor_id)
                    stack.append(neighbor_id)

        if len(seen) != len(self.nodes):
            missing = sorted(set(self.nodes) - seen)
            raise ValidationError(
                "A rede está particionada; nós inalcançáveis: " + ", ".join(missing)
            )
