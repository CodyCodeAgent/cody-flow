"""Base runner interface - all runners must implement this."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class RunnerResult:
    """Result returned by a runner after executing a prompt."""

    output: str
    session_id: str | None = None
    metadata: dict = field(default_factory=dict)


class Runner(abc.ABC):
    """Abstract base class for AI runners.

    A runner is the underlying AI engine that executes node prompts.
    Implementations include Cody SDK, Claude Agent SDK, etc.
    """

    def __init__(self, workdir: str, **kwargs):
        self.workdir = workdir
        self.config = kwargs

    @abc.abstractmethod
    async def run(self, prompt: str, session_id: str | None = None) -> RunnerResult:
        """Execute a prompt and return the result.

        Args:
            prompt: The prompt to execute.
            session_id: Optional session ID for multi-turn conversations.

        Returns:
            RunnerResult with the output text and metadata.
        """

    async def close(self):
        """Clean up resources. Override if needed."""
        return  # default no-op; subclasses may override

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
