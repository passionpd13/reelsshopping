"""CLI: `reels-search find <image>` and `reels-search keywords <image>`."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .pipeline import find_videos
from .vision import extract_query

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.command()
def keywords(
    image: Path = typer.Argument(..., exists=True, readable=True, help="Path to product image"),
    as_json: bool = typer.Option(False, "--json", help="Print raw JSON"),
) -> None:
    """Run only the Gemini keyword extraction step. Cheap dev sanity check."""
    query = extract_query(image)
    if as_json:
        console.print_json(query.model_dump_json())
        return
    table = Table(title="Extracted product query", show_lines=False)
    table.add_column("field", style="bold")
    table.add_column("value")
    for k, v in query.model_dump().items():
        table.add_row(k, ", ".join(v) if isinstance(v, list) else str(v))
    console.print(table)


@app.command()
def find(
    image: Path = typer.Argument(..., exists=True, readable=True, help="Path to product image"),
    as_json: bool = typer.Option(False, "--json", help="Print raw JSON results"),
) -> None:
    """Find and download product videos that match the input image."""
    query, results = asyncio.run(find_videos(image))

    if as_json:
        payload = {
            "query": query.model_dump(),
            "results": [r.model_dump(mode="json") for r in results],
        }
        console.print_json(json.dumps(payload))
        return

    console.print(f"[bold]Query:[/bold] {query.primary_query('zh')}")
    if not results:
        console.print("[red]No videos found.[/red] Try setting cookies or SERPAPI_KEY in .env.")
        raise typer.Exit(code=1)

    table = Table(title=f"Top {len(results)} videos")
    table.add_column("#", justify="right")
    table.add_column("platform")
    table.add_column("similarity", justify="right")
    table.add_column("title", overflow="fold")
    table.add_column("file")
    for i, r in enumerate(results, 1):
        table.add_row(
            str(i),
            r.candidate.platform,
            f"{r.similarity:.2f}",
            r.candidate.title[:80],
            str(r.local_path),
        )
    console.print(table)


if __name__ == "__main__":
    app()
