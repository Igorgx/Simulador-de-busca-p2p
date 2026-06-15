from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from .config import load_config
from .demo_server import run_demo_server
from .models import SearchResult, ValidationError
from .search import ALGORITHMS, run_search
from .visualize import animate_search, draw_comparison_chart, draw_network


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="p2p-sim",
        description="Simulador de buscas em redes P2P não estruturadas.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Valida um arquivo de configuração.")
    validate.add_argument("config")

    show = subparsers.add_parser("show", help="Desenha a topologia da rede.")
    show.add_argument("config")
    show.add_argument("--output", default="output/rede.png")
    show.add_argument("--open", action="store_true", help="Abre uma janela com a imagem.")

    search = subparsers.add_parser("search", help="Executa uma busca.")
    search.add_argument("config")
    search.add_argument("--origin", required=True)
    search.add_argument("--resource", required=True)
    search.add_argument("--ttl", type=int, required=True)
    search.add_argument("--algo", choices=sorted(ALGORITHMS), required=True)
    search.add_argument("--search-id")
    search.add_argument("--seed", type=int)
    search.add_argument("--no-direct-get", action="store_true")
    search.add_argument("--trace", action="store_true", help="Mostra o rastro escrito completo.")
    search.add_argument("--plot", help="Salva imagem final da busca.")
    search.add_argument("--animate", help="Salva animação GIF da busca.")
    search.add_argument("--show-plot", action="store_true", help="Abre uma janela com a imagem final.")

    compare = subparsers.add_parser("compare", help="Compara algoritmos em várias buscas.")
    compare.add_argument("config")
    compare.add_argument("--runs", type=int, default=30)
    compare.add_argument("--ttl", type=int, default=4)
    compare.add_argument("--seed", type=int, default=42)
    compare.add_argument("--csv", default="output/comparacao.csv")
    compare.add_argument("--chart", default="output/comparacao.png")
    compare.add_argument(
        "--cold-cache",
        action="store_true",
        help="Recarrega a rede a cada busca, impedindo aquecimento do cache.",
    )

    demo = subparsers.add_parser("demo", help="Abre a interface visual passo a passo.")
    demo.add_argument("config")
    demo.add_argument("--host", default="127.0.0.1")
    demo.add_argument("--port", type=int, default=8000)
    demo.add_argument("--no-open", action="store_true", help="Não abre o navegador automaticamente.")

    args = parser.parse_args()

    try:
        if args.command == "validate":
            _validate(args.config)
        elif args.command == "show":
            _show(args)
        elif args.command == "search":
            _search(args)
        elif args.command == "compare":
            _compare(args)
        elif args.command == "demo":
            run_demo_server(
                args.config,
                host=args.host,
                port=args.port,
                open_browser=not args.no_open,
            )
    except ValidationError as exc:
        raise SystemExit(f"Erro de validação: {exc}") from exc


def _validate(config: str) -> None:
    network = load_config(config)
    min_degree, max_degree, avg_degree = network.degree_stats()
    print("Configuração válida.")
    print(f"Nós: {len(network.nodes)}")
    print(f"Recursos distintos: {len(network.all_resources())}")
    print(f"Grau mínimo/máximo/médio: {min_degree}/{max_degree}/{avg_degree:.2f}")


def _show(args: argparse.Namespace) -> None:
    network = load_config(args.config)
    output = draw_network(network, output_path=args.output, show=args.open)
    print(f"Imagem da rede salva em: {output}")


def _search(args: argparse.Namespace) -> None:
    network = load_config(args.config)
    result = run_search(
        network,
        args.origin,
        args.resource,
        args.ttl,
        args.algo,
        search_id=args.search_id,
        seed=args.seed,
        direct_get=not args.no_direct_get,
    )
    _print_summary(result)

    if args.trace:
        print("\nRastro da busca:")
        for event in result.events:
            print(f"{event.step:02d}. [{event.event_type}] {event.message}")

    if args.plot:
        output = draw_network(network, result, output_path=args.plot, show=args.show_plot)
        print(f"\nImagem final salva em: {output}")
    elif args.show_plot:
        draw_network(network, result, show=True)

    if args.animate:
        output = animate_search(network, result, output_path=args.animate)
        print(f"Animação salva em: {output}")


def _compare(args: argparse.Namespace) -> None:
    rng = random.Random(args.seed)
    base_network = load_config(args.config)
    node_ids = base_network.node_ids()
    resources = sorted(base_network.all_resources())
    cases = [(rng.choice(node_ids), rng.choice(resources)) for _ in range(args.runs)]

    rows: list[dict[str, str | int | float]] = []
    algorithm_networks = {
        algorithm: load_config(args.config) for algorithm in sorted(ALGORITHMS)
    }

    for run_number, (origin, resource_id) in enumerate(cases, start=1):
        for algorithm in sorted(ALGORITHMS):
            network = load_config(args.config) if args.cold_cache else algorithm_networks[algorithm]
            result = run_search(
                network,
                origin,
                resource_id,
                args.ttl,
                algorithm,
                seed=args.seed + run_number,
                direct_get=False,
            )
            rows.append(
                {
                    "run": run_number,
                    "search_id": result.search_id,
                    "algorithm": algorithm,
                    "origin": origin,
                    "resource": resource_id,
                    "ttl": args.ttl,
                    "found": int(result.found),
                    "holder": result.holder or "",
                    "messages": result.messages,
                    "visited_nodes": result.visited_count,
                    "cache_hits": result.cache_hits,
                }
            )

    csv_path = Path(args.csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    chart = draw_comparison_chart(rows, output_path=args.chart)
    print(f"CSV salvo em: {csv_path}")
    print(f"Gráfico salvo em: {chart}")
    print("\nResumo por algoritmo:")
    for algorithm in sorted(ALGORITHMS):
        subset = [row for row in rows if row["algorithm"] == algorithm]
        messages = [int(row["messages"]) for row in subset]
        visited = [int(row["visited_nodes"]) for row in subset]
        found_rate = sum(int(row["found"]) for row in subset) / len(subset)
        cache_hits = sum(int(row["cache_hits"]) for row in subset)
        print(
            f"- {algorithm}: mensagens min/máx/média = "
            f"{min(messages)}/{max(messages)}/{sum(messages) / len(messages):.2f}; "
            f"nós min/máx/média = {min(visited)}/{max(visited)}/{sum(visited) / len(visited):.2f}; "
            f"sucesso = {found_rate:.0%}; cache hits = {cache_hits}"
        )


def _print_summary(result: SearchResult) -> None:
    status = f"ENCONTRADO em {result.holder}" if result.found else "NÃO ENCONTRADO"
    print(f"Busca: {result.search_id}")
    print(f"Algoritmo: {result.algorithm}")
    print(f"Origem: {result.origin}")
    print(f"Recurso: {result.resource_id}")
    print(f"TTL: {result.ttl}")
    print(f"Status: {status}")
    print(f"Mensagens da busca/resposta: {result.messages}")
    print(f"Nós envolvidos: {result.visited_count} ({', '.join(sorted(result.visited_nodes))})")
    print(f"Cache hits: {result.cache_hits}")
    if result.response_path:
        print(f"Caminho de aviso: {' -> '.join(result.response_path)}")
    if result.direct_request_messages:
        print(
            "Transferência direta após descoberta: "
            f"{result.direct_request_messages} mensagens adicionais"
        )


if __name__ == "__main__":
    main()
