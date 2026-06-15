import pytest

from p2p_simulator.config import load_config, network_from_dict
from p2p_simulator.demo_server import compare_algorithms_for_resource
from p2p_simulator.models import ValidationError
from p2p_simulator.search import run_search


def test_loads_valid_sample_config():
    network = load_config("configs/sample.yaml")
    assert len(network.nodes) == 12
    assert "r11" in network.all_resources()


def test_rejects_self_edge():
    with pytest.raises(ValidationError):
        network_from_dict(
            {
                "num_nodes": 1,
                "min_neighbors": 0,
                "max_neighbors": 1,
                "resources": {"n1": ["r1"]},
                "edges": [["n1", "n1"]],
            }
        )


def test_flooding_finds_resource_and_records_stats():
    network = load_config("configs/sample.yaml")
    result = run_search(network, "n1", "r11", 4, "flooding", direct_get=False)
    assert result.found
    assert result.holder == "n10"
    assert result.messages > 0
    assert result.visited_count > 1
    assert result.search_id


def test_informed_search_uses_cache_after_first_search():
    network = load_config("configs/sample.yaml")
    first = run_search(network, "n1", "r11", 4, "flooding", direct_get=False)
    second = run_search(network, "n1", "r11", 4, "informed_flooding", direct_get=False)
    assert first.found
    assert second.found
    assert second.cache_hits >= 1
    assert second.messages <= first.messages


def test_resource_comparison_returns_min_and_max_by_algorithm():
    rows = compare_algorithms_for_resource(
        "configs/sample.yaml",
        "r11",
        4,
        random_trials=2,
        seed=7,
    )
    assert {row["algorithm"] for row in rows} == {
        "flooding",
        "informed_flooding",
        "random_walk",
        "informed_random_walk",
    }
    assert all("min_messages" in row and "max_nodes" in row for row in rows)
