"""srg — Shopping Reels Generator CLI entry point."""
from __future__ import annotations

import typer

from app.cli import spike

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Shopping Reels Generator")
app.command("spike", help="End-to-end Phase 0 spike: URL → analyzed reference → new reel mp4")(spike.run)


if __name__ == "__main__":
    app()
