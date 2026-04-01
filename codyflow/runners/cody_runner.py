"""Cody SDK runner implementation."""

from __future__ import annotations

from codyflow.runners.base import Runner, RunnerResult
from codyflow.runners.registry import register_runner


class CodyRunner(Runner):
    """Runner backed by the Cody SDK (cody-ai package)."""

    def __init__(self, workdir: str, **kwargs):
        super().__init__(workdir, **kwargs)
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                from cody import AsyncCodyClient
            except ImportError:
                raise ImportError(
                    "Cody SDK not installed. Run: pip install codyflow[cody]"
                )
            self._client = await AsyncCodyClient(workdir=self.workdir).__aenter__()
        return self._client

    async def run(self, prompt: str, session_id: str | None = None) -> RunnerResult:
        client = await self._get_client()
        kwargs = {}
        if session_id:
            kwargs["session_id"] = session_id
        result = await client.run(prompt, **kwargs)
        return RunnerResult(
            output=result.output,
            session_id=getattr(result, "session_id", None),
            metadata={"runner": "cody"},
        )

    async def close(self):
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None


register_runner("cody", CodyRunner)
