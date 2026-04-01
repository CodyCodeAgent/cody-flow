"""CLI entry point for CodyFlow."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from codyflow.engine.flow import Flow, parse_flow

console = Console()


@click.group()
@click.version_option(package_name="codyflow")
def main():
    """CodyFlow - AI workflow orchestration framework."""


@main.command()
@click.argument("flow_file", type=click.Path(exists=True))
@click.option("--workdir", "-w", default=".", help="Working directory for the flow.")
@click.option("--input", "-i", "user_input", default="", help="User input / task description.")
@click.option("--runner", "-r", default=None, help="Override global runner.")
def run(flow_file: str, workdir: str, user_input: str, runner: str | None):
    """Run a flow from a YAML definition file."""
    workdir = str(Path(workdir).resolve())

    console.print(Panel(f"[bold]CodyFlow[/bold] — 加载 {flow_file}", style="blue"))

    definition = parse_flow(flow_file)
    if runner:
        definition.runner = runner

    flow = Flow(definition, workdir)

    # Progress callbacks
    flow.on_node_start = lambda nid, ntype: console.print(
        f"\n[yellow]▶ 执行节点:[/yellow] {nid} ({ntype})"
    )
    flow.on_node_complete = lambda nid, result: console.print(
        f"[green]✓ 完成:[/green] {nid}"
    )
    flow.on_flow_complete = lambda results: console.print(
        Panel(f"[bold green]Flow 执行完成[/bold green] — 共 {len(results)} 个节点", style="green")
    )

    asyncio.run(flow.run(user_input))


@main.command()
@click.argument("name")
@click.option("--workdir", "-w", default=".", help="Working directory.")
def init(name: str, workdir: str):
    """Initialize a new flow project with a template YAML."""
    workdir = Path(workdir).resolve()
    codyflow_dir = workdir / ".codyflow"
    codyflow_dir.mkdir(parents=True, exist_ok=True)
    (codyflow_dir / "context").mkdir(exist_ok=True)
    (codyflow_dir / "logs").mkdir(exist_ok=True)

    flow_file = workdir / f"{name}.flow.yaml"
    flow_file.write_text(f"""name: "{name}"
description: ""
runner: cody
max_iterations: 3

nodes:
  - id: discuss
    type: discuss
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
""", encoding="utf-8")

    console.print(f"[green]✓[/green] 已创建 {flow_file}")
    console.print(f"[green]✓[/green] 已创建 {codyflow_dir}/")
    console.print(f"\n运行: [bold]codyflow run {flow_file}[/bold]")


if __name__ == "__main__":
    main()
