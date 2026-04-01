"""CLI entry point for CodyFlow."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from codyflow.engine.flow import Flow, parse_flow, validate_flow

console = Console()
logger = logging.getLogger(__name__)


def _parse_vars(var_list: tuple[str, ...]) -> dict[str, str]:
    """Parse --var key=value pairs into a dict."""
    result = {}
    for v in var_list:
        if "=" not in v:
            raise click.BadParameter(f"Variable must be key=value format, got: {v}")
        key, value = v.split("=", 1)
        result[key.strip()] = value.strip()
    return result


async def _interactive_input(node_id: str, ai_output: str) -> str:
    """Ask user for input during interactive nodes."""
    console.print(f"\n[bold cyan]AI ({node_id}):[/bold cyan]")
    console.print(ai_output[:2000] + ("..." if len(ai_output) > 2000 else ""))
    console.print()
    return Prompt.ask(
        "[bold]你的回复[/bold] (输入 'done' 结束讨论)",
        default="done",
    )


def _setup_flow_callbacks(flow: Flow):
    """Attach progress reporting callbacks to a flow."""
    flow.on_node_start = lambda nid, ntype: console.print(
        f"\n[yellow]▶ 执行节点:[/yellow] {nid} ({ntype})"
    )
    flow.on_node_complete = lambda nid, result: console.print(
        f"[green]✓ 完成:[/green] {nid}"
    )
    flow.on_flow_complete = lambda state: console.print(
        Panel(
            f"[bold green]Flow 执行完成[/bold green] — "
            f"共 {len(state.get('completed_nodes', []))} 个节点, "
            f"迭代 {state.get('iteration', 0)} 轮",
            style="green",
        )
    )
    flow.on_interactive_input = _interactive_input


@click.group()
@click.version_option(package_name="codyflow")
@click.option("--debug", is_flag=True, help="启用调试日志")
def main(debug: bool):
    """CodyFlow - AI workflow orchestration framework."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@main.command()
@click.argument("flow_file", type=click.Path(exists=True))
@click.option("--workdir", "-w", default=".", help="项目工作目录")
@click.option("--input", "-i", "user_input", default="", help="任务描述 / 需求")
@click.option("--runner", "-r", default=None, help="覆盖全局 Runner")
@click.option("--var", "-v", "variables", multiple=True, help="变量替换 (key=value)")
def run(flow_file: str, workdir: str, user_input: str, runner: str | None, variables: tuple):
    """执行一个 Flow（从 YAML 文件）"""
    workdir = str(Path(workdir).resolve())
    var_dict = _parse_vars(variables)

    console.print(Panel(f"[bold]CodyFlow[/bold] — {flow_file}", style="blue"))

    definition = parse_flow(flow_file, variables=var_dict)
    if runner:
        definition.runner = runner

    # Validate and show warnings
    errors = validate_flow(definition)
    for err in errors:
        console.print(f"[yellow]⚠ {err}[/yellow]")

    flow = Flow(definition, workdir)
    _setup_flow_callbacks(flow)

    asyncio.run(flow.run(user_input))


@main.command()
@click.argument("name")
@click.option("--workdir", "-w", default=".", help="项目工作目录")
def init(name: str, workdir: str):
    """初始化一个新的 Flow 项目模板"""
    workdir = Path(workdir).resolve()
    codyflow_dir = workdir / ".codyflow"
    codyflow_dir.mkdir(parents=True, exist_ok=True)
    (codyflow_dir / "context").mkdir(exist_ok=True)
    (codyflow_dir / "logs").mkdir(exist_ok=True)

    flow_file = workdir / f"{name}.flow.yaml"
    flow_file.write_text("""\
name: "{name}"
description: "{{task_description}}"
runner: cody
max_iterations: 3

nodes:
  - id: discuss
    type: discuss
    interactive: true
    outputs:
      - discuss_output.md

  - id: learn
    type: learn
    outputs:
      - learn_output.md

  - id: code
    type: code
    outputs:
      - code_output.md

  - id: reflect
    type: reflect
    outputs:
      - reflect_output.md

  - id: judge
    type: judge
    outputs:
      - judge_output.md

edges:
  - from: discuss
    to: learn
  - from: learn
    to: code
  - from: code
    to: reflect
  - from: reflect
    to: judge
  - from: judge
    to: code
    condition: needs_fix
  - from: judge
    to: END
    condition: passed
""".replace("{name}", name), encoding="utf-8")

    console.print(f"[green]✓[/green] 已创建 {flow_file}")
    console.print(f"[green]✓[/green] 已创建 {codyflow_dir}/")
    console.print(f"\n运行示例:")
    console.print(
        f'  [bold]codyflow run {flow_file} -i "添加用户认证功能"'
        f' -v task_description="为项目添加 JWT 认证"[/bold]'
    )


@main.command()
@click.argument("flow_file", type=click.Path(exists=True))
@click.option("--workdir", "-w", default=".", help="项目工作目录")
@click.option("--input", "-i", "user_input", default="", help="补充任务描述")
def resume(flow_file: str, workdir: str, user_input: str):
    """从断点恢复执行 Flow"""
    workdir = str(Path(workdir).resolve())

    # Check state.db exists
    state_db = Path(workdir) / ".codyflow" / "state.db"
    if not state_db.exists():
        console.print(
            "[red]✗ 未找到执行状态文件 (.codyflow/state.db)[/red]\n"
            "  没有可恢复的 Flow，请使用 [bold]codyflow run[/bold] 开始新的执行。"
        )
        raise SystemExit(1)

    console.print(Panel(f"[bold]CodyFlow[/bold] — 恢复 {flow_file}", style="yellow"))

    definition = parse_flow(flow_file)
    flow = Flow(definition, workdir)
    _setup_flow_callbacks(flow)

    asyncio.run(flow.run(user_input))


if __name__ == "__main__":
    main()
