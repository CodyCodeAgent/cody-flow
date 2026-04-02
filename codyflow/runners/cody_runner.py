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
            except ImportError as exc:
                raise ImportError(
                    "Cody SDK not installed. Run: pip install codyflow[cody]"
                ) from exc
            client_kwargs = {"workdir": self.workdir}
            if self.config.get("api_key"):
                client_kwargs["api_key"] = self.config["api_key"]
            if self.config.get("model"):
                client_kwargs["model"] = self.config["model"]
            if self.config.get("base_url"):
                client_kwargs["base_url"] = self.config["base_url"]
            self._client = await AsyncCodyClient(**client_kwargs).__aenter__()
        return self._client

    async def run(self, prompt: str, session_id: str | None = None) -> RunnerResult:
        client = await self._get_client()
        kwargs = {}
        if session_id:
            kwargs["session_id"] = session_id

        full_output = ""
        result_session_id = session_id

        async for chunk in client.stream(prompt, **kwargs):
            if chunk.type == "text_delta":
                full_output += chunk.content
                if self.on_chunk:
                    self.on_chunk(chunk.content, "text_delta")
            elif chunk.type == "thinking":
                if self.on_chunk:
                    self.on_chunk(chunk.content, "thinking")
            elif chunk.type == "tool_call":
                if self.on_chunk:
                    self.on_chunk(chunk.tool_name, "tool_call", {
                        "args": chunk.args,
                        "tool_call_id": chunk.tool_call_id,
                    })
            elif chunk.type == "tool_result":
                if self.on_chunk:
                    self.on_chunk(chunk.content or "", "tool_result", {
                        "tool_name": chunk.tool_name,
                    })
            elif chunk.type == "done":
                result_session_id = getattr(chunk, "session_id", None) or session_id

        return RunnerResult(
            output=full_output,
            session_id=result_session_id,
            metadata={"runner": "cody"},
        )

    async def close(self):
        if self._client is not None:
            import contextlib
            with contextlib.suppress(Exception):
                await self._client.__aexit__(None, None, None)
            self._client = None


register_runner("cody", CodyRunner)
