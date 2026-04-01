"""Claude Agent SDK runner implementation."""

from __future__ import annotations

from codyflow.runners.base import Runner, RunnerResult
from codyflow.runners.registry import register_runner


class ClaudeRunner(Runner):
    """Runner backed by the Claude Agent SDK."""

    async def run(self, prompt: str, session_id: str | None = None) -> RunnerResult:
        try:
            from claude_agent_sdk import query, ClaudeAgentOptions
        except ImportError:
            raise ImportError(
                "Claude Agent SDK not installed. Run: pip install codyflow[claude]"
            )

        output_parts: list[str] = []
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
                permission_mode="acceptEdits",
                cwd=self.workdir,
                max_turns=self.config.get("max_turns", 30),
            ),
        ):
            if hasattr(message, "message") and message.message:
                for block in message.message.content:
                    if hasattr(block, "text"):
                        output_parts.append(block.text)
            if hasattr(message, "result"):
                output_parts.append(str(message.result))

        return RunnerResult(
            output="\n".join(output_parts),
            metadata={"runner": "claude"},
        )


register_runner("claude", ClaudeRunner)
