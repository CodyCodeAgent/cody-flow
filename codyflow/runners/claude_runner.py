"""Claude Agent SDK runner implementation."""

from __future__ import annotations

from codyflow.runners.base import Runner, RunnerResult
from codyflow.runners.registry import register_runner


class ClaudeRunner(Runner):
    """Runner backed by the Claude Agent SDK.

    Supports session-based multi-turn conversations for interactive nodes.
    """

    def __init__(self, workdir: str, **kwargs):
        super().__init__(workdir, **kwargs)
        self._sessions: dict[str, list] = {}  # session_id → conversation history

    async def run(self, prompt: str, session_id: str | None = None) -> RunnerResult:
        try:
            from claude_agent_sdk import query, ClaudeAgentOptions
        except ImportError:
            raise ImportError(
                "Claude Agent SDK not installed. Run: pip install codyflow[claude]"
            )

        # Build options
        options_kwargs = {
            "allowed_tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
            "permission_mode": "acceptEdits",
            "cwd": self.workdir,
            "max_turns": self.config.get("max_turns", 30),
        }
        if self.config.get("model"):
            options_kwargs["model"] = self.config["model"]

        # For multi-turn sessions, include conversation history as system prompt
        if session_id and session_id in self._sessions:
            history = self._sessions[session_id]
            history_text = "\n\n---\n\n".join(
                f"[{msg['role']}]: {msg['content']}" for msg in history
            )
            options_kwargs["system_prompt"] = (
                f"以下是之前的对话历史，请基于此继续：\n\n{history_text}"
            )

        output_parts: list[str] = []
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(**options_kwargs),
        ):
            if hasattr(message, "message") and message.message:
                for block in message.message.content:
                    if hasattr(block, "text"):
                        output_parts.append(block.text)
            if hasattr(message, "result"):
                output_parts.append(str(message.result))

        output = "\n".join(output_parts)

        # Manage session for multi-turn
        new_session_id = session_id or f"claude-{id(self)}-{len(self._sessions)}"
        if new_session_id not in self._sessions:
            self._sessions[new_session_id] = []
        self._sessions[new_session_id].append({"role": "user", "content": prompt})
        self._sessions[new_session_id].append({"role": "assistant", "content": output})

        return RunnerResult(
            output=output,
            session_id=new_session_id,
            metadata={"runner": "claude"},
        )


register_runner("claude", ClaudeRunner)
