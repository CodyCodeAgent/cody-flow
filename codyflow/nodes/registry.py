"""Node type registry - maps type names to node classes."""

from __future__ import annotations

from codyflow.nodes.base import Node

_registry: dict[str, type[Node]] = {}


def register_node_type(name: str, cls: type[Node]):
    """Register a node type class."""
    _registry[name] = cls


def get_node_type(name: str) -> type[Node]:
    """Get a node type class by name.

    Raises:
        ValueError: If the node type is not registered.
    """
    if name not in _registry:
        available = ", ".join(_registry.keys()) or "(none)"
        raise ValueError(
            f"Unknown node type '{name}'. Available types: {available}"
        )
    return _registry[name]


def list_node_types() -> list[str]:
    """Return all registered node type names."""
    return list(_registry.keys())
