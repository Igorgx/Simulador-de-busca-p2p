from __future__ import annotations

import random
import uuid
from collections import deque
from dataclasses import dataclass

from .models import P2PNetwork, SearchEvent, SearchResult, ValidationError


ALGORITHMS = {
    "flooding",
    "informed_flooding",
    "random_walk",
    "informed_random_walk",
}


@dataclass
class _RunState:
    search_id: str
    algorithm: str
    origin: str
    resource_id: str
    ttl: int
    informed: bool
    direct_get: bool
    messages: int = 0
    cache_hits: int = 0
    events: list[SearchEvent] | None = None
    visited: set[str] | None = None
    response_path: list[str] | None = None
    holder: str | None = None

    def __post_init__(self) -> None:
        self.events = []
        self.visited = set()
        self.response_path = []

    def event(
        self,
        event_type: str,
        node_id: str,
        message: str,
        *,
        from_node: str | None = None,
        to_node: str | None = None,
        ttl: int | None = None,
        path: list[str] | tuple[str, ...] = (),
    ) -> None:
        assert self.events is not None
        self.events.append(
            SearchEvent(
                step=len(self.events) + 1,
                event_type=event_type,
                node_id=node_id,
                message=message,
                from_node=from_node,
                to_node=to_node,
                ttl=ttl,
                path=tuple(path),
            )
        )


def run_search(
    network: P2PNetwork,
    origin: str,
    resource_id: str,
    ttl: int,
    algorithm: str,
    *,
    search_id: str | None = None,
    seed: int | None = None,
    direct_get: bool = True,
) -> SearchResult:
    if algorithm not in ALGORITHMS:
        raise ValidationError(
            f"Algoritmo invalido: {algorithm}. Use um destes: {', '.join(sorted(ALGORITHMS))}."
        )
    if origin not in network.nodes:
        raise ValidationError(f"No de origem inexistente: {origin}.")
    if ttl < 0:
        raise ValidationError("ttl nao pode ser negativo.")

    state = _RunState(
        search_id=search_id or uuid.uuid4().hex[:8],
        algorithm=algorithm,
        origin=origin,
        resource_id=resource_id,
        ttl=ttl,
        informed=algorithm.startswith("informed_"),
        direct_get=direct_get,
    )
    rng = random.Random(seed)

    state.event(
        "start",
        origin,
        f"Busca {state.search_id} iniciada em {origin} procurando {resource_id} com TTL={ttl}.",
        ttl=ttl,
        path=[origin],
    )

    if algorithm.endswith("flooding"):
        _run_flooding(network, state)
    else:
        _run_random_walk_with_backtracking(network, state, rng)

    direct_messages = 0
    if direct_get and state.holder and state.holder != origin:
        direct_messages = 2
        state.event(
            "direct_request",
            origin,
            f"{origin} solicita {resource_id} diretamente a {state.holder}, sem depender dos vizinhos.",
            from_node=origin,
            to_node=state.holder,
            path=[origin, state.holder],
        )
        state.event(
            "direct_response",
            state.holder,
            f"{state.holder} envia {resource_id} diretamente para {origin}.",
            from_node=state.holder,
            to_node=origin,
            path=[state.holder, origin],
        )

    return SearchResult(
        search_id=state.search_id,
        algorithm=algorithm,
        origin=origin,
        resource_id=resource_id,
        ttl=ttl,
        found=state.holder is not None,
        holder=state.holder,
        messages=state.messages,
        visited_nodes=state.visited or set(),
        events=state.events or [],
        response_path=state.response_path or [],
        cache_hits=state.cache_hits,
        direct_request_messages=direct_messages,
    )


def _check_current_node(
    network: P2PNetwork,
    state: _RunState,
    current: str,
    path: list[str],
    ttl: int,
) -> bool:
    node = network.get(current)
    assert state.visited is not None
    state.visited.add(current)

    state.event(
        "visit",
        current,
        f"{current} recebeu a busca; TTL restante={ttl}; caminho={' -> '.join(path)}.",
        ttl=ttl,
        path=path,
    )

    if node.has_resource(state.resource_id):
        if state.holder is None:
            _mark_found(network, state, current, path, "resource")
        else:
            state.event(
                "found_again",
                current,
                f"{current} tambem recebeu a busca e confirmou {state.resource_id} localmente, mas a origem ja tinha sido avisada.",
                ttl=ttl,
                path=path,
            )
        return True

    if state.informed and state.resource_id in node.cache:
        state.cache_hits += 1
        holder = node.cache[state.resource_id]
        if state.holder is None:
            _mark_found(network, state, holder, path, "cache", cache_node=current)
        else:
            state.event(
                "cache_hit",
                current,
                f"{current} tambem encontrou no cache que {state.resource_id} esta em {holder}; a busca paralela continua nos outros ramos.",
                ttl=ttl,
                path=path,
            )
        return True

    return False


def _mark_found(
    network: P2PNetwork,
    state: _RunState,
    holder: str,
    path: list[str],
    source: str,
    *,
    cache_node: str | None = None,
) -> None:
    state.holder = holder
    state.response_path = list(reversed(path))

    if source == "cache":
        assert cache_node is not None
        state.event(
            "cache_hit",
            cache_node,
            f"{cache_node} ja sabia pelo cache que {state.resource_id} esta em {holder}.",
            ttl=0,
            path=path,
        )
    else:
        state.event(
            "found",
            holder,
            f"{holder} possui localmente {state.resource_id}.",
            ttl=0,
            path=path,
        )

    response_path = list(reversed(path))
    if len(response_path) > 1:
        for left, right in zip(response_path, response_path[1:]):
            state.messages += 1
            state.event(
                "response",
                right,
                f"Aviso de recurso encontrado volta de {left} para {right}.",
                from_node=left,
                to_node=right,
                path=response_path,
            )

    network.add_cache_entry(path, state.resource_id, holder)
    state.event(
        "cache_update",
        holder,
        f"Nos no caminho agora cacheiam {state.resource_id} -> {holder}: {', '.join(path)}.",
        path=path,
    )


def _run_flooding(network: P2PNetwork, state: _RunState) -> None:
    processed: set[str] = set()
    assert state.visited is not None

    if _check_current_node(network, state, state.origin, [state.origin], state.ttl):
        return

    processed.add(state.origin)
    queue: deque[tuple[str, str, int, list[str]]] = deque()

    if state.ttl == 0:
        state.event("ttl_expired", state.origin, "TTL inicial e 0; a busca nao sai da origem.", ttl=0)
        return

    for neighbor in sorted(network.get(state.origin).neighbors):
        state.messages += 1
        state.event(
            "query",
            neighbor,
            f"{state.origin} envia a busca para {neighbor}; TTL enviado={state.ttl - 1}.",
            from_node=state.origin,
            to_node=neighbor,
            ttl=state.ttl - 1,
            path=[state.origin, neighbor],
        )
        queue.append((state.origin, neighbor, state.ttl - 1, [state.origin, neighbor]))

    while queue:
        previous, current, ttl, path = queue.popleft()
        if current in processed:
            state.event(
                "duplicate",
                current,
                f"{current} ignora duplicata da busca {state.search_id}.",
                from_node=previous,
                to_node=current,
                ttl=ttl,
                path=path,
            )
            continue

        processed.add(current)
        if _check_current_node(network, state, current, path, ttl):
            if queue:
                state.event(
                    "parallel_continue",
                    current,
                    "Este ramo encontrou o recurso, mas outras mensagens de inundacao ja estavam em paralelo e continuam sendo processadas.",
                    ttl=ttl,
                    path=path,
                )
            continue

        if ttl == 0:
            state.event(
                "ttl_expired",
                current,
                f"{current} nao retransmite porque o TTL chegou a 0.",
                ttl=ttl,
                path=path,
            )
            continue

        for neighbor in sorted(network.get(current).neighbors):
            if neighbor == previous or neighbor in processed:
                continue
            state.messages += 1
            next_path = [*path, neighbor]
            state.event(
                "query",
                neighbor,
                f"{current} inunda a busca para {neighbor}; TTL enviado={ttl - 1}.",
                from_node=current,
                to_node=neighbor,
                ttl=ttl - 1,
                path=next_path,
            )
            queue.append((current, neighbor, ttl - 1, next_path))

    if state.holder is None:
        state.event(
            "not_found",
            state.origin,
            f"{state.resource_id} nao foi encontrado antes da fila esvaziar.",
            ttl=0,
        )


def _run_random_walk_with_backtracking(
    network: P2PNetwork,
    state: _RunState,
    rng: random.Random,
) -> None:
    path = [state.origin]
    ttl_stack = [state.ttl]
    tried_edges: set[tuple[str, str]] = set()
    visited_for_choice = {state.origin}
    ttl_zero_backtrack_allowed: set[str] = set()

    if _check_current_node(network, state, state.origin, path, state.ttl):
        return

    while path and state.holder is None:
        current = path[-1]
        ttl = ttl_stack[-1]
        candidates = [
            neighbor
            for neighbor in sorted(network.get(current).neighbors)
            if (current, neighbor) not in tried_edges and neighbor not in visited_for_choice
        ]

        can_move = ttl > 0 or current in ttl_zero_backtrack_allowed
        if candidates and can_move:
            if ttl == 0:
                ttl_zero_backtrack_allowed.discard(current)
            next_node = rng.choice(candidates)
            tried_edges.add((current, next_node))
            tried_edges.add((next_node, current))
            visited_for_choice.add(next_node)
            next_ttl = max(ttl - 1, 0)
            next_path = [*path, next_node]
            state.messages += 1
            state.event(
                "query",
                next_node,
                f"{current} escolhe aleatoriamente {next_node}; TTL enviado={next_ttl}.",
                from_node=current,
                to_node=next_node,
                ttl=next_ttl,
                path=next_path,
            )
            path.append(next_node)
            ttl_stack.append(next_ttl)

            if _check_current_node(network, state, next_node, next_path, next_ttl):
                return
            continue

        if len(path) == 1:
            break

        backtracked_from = path.pop()
        ttl_stack.pop()
        previous = path[-1]
        previous_ttl = ttl_stack[-1]
        state.messages += 1
        state.event(
            "backtrack",
            previous,
            f"{backtracked_from} nao encontrou {state.resource_id} ou esgotou o TTL do ramo; volta para {previous} para tentar outro vizinho disponivel.",
            from_node=backtracked_from,
            to_node=previous,
            ttl=previous_ttl,
            path=path,
        )

        if previous_ttl == 0:
            ttl_zero_backtrack_allowed.add(previous)
            state.event(
                "ttl_backtrack",
                previous,
                f"Mesmo com TTL 0 em {previous}, o backtracking permite escolher outro vizinho ainda nao tentado.",
                ttl=previous_ttl,
                path=path,
            )

    if state.holder is None:
        state.event(
            "not_found",
            state.origin,
            f"{state.resource_id} nao foi encontrado depois de tentar os caminhos disponiveis com random walk e backtracking.",
            ttl=ttl_stack[-1] if ttl_stack else 0,
            path=path,
        )
