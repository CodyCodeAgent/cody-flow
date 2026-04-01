"""Runner registry - maps runner names to their classes."""

from __future__ import annotations

from typing import Type

from codyflow.runners.base import Runner

_registry: dict[str, Type[Runner]] = {}


def register_runner(name: str, cls: Type[Runner]):
    """Register a runner class under a given name."""
    _registry[name] = cls


def get_runner(name: str, workdir: str, **kwargs) -> Runner:
    """Instantiate a runner by name.

    Raises:
        ValueError: If the runner name is not registered.
    """
    if name not in _registry:
        available = ", ".join(_registry.keys()) or "(none)"
        raise ValueError(
            f"Unknown runner '{name}'. Available runners: {available}"
        )
    return _registry[name](workdir=workdir, **kwargs)


def list_runners() -> list[str]:
    """Return all registered runner names."""
    return list(_registry.keys())
