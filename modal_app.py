"""Modal deployment entrypoint.

Usage:
    modal deploy modal_app.py
    modal serve modal_app.py     # for local preview

The free Modal tier handles this fine because runs are short-lived (≤60s) and
state lives in a small SQLite file on a persistent Volume.
"""

from __future__ import annotations

from pathlib import Path

import modal

PROJECT_ROOT = Path(__file__).parent

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_pyproject(str(PROJECT_ROOT / "pyproject.toml"))
    .add_local_python_source("backend")
    # add_local_python_source follows Python import semantics and only
    # ships .py/.pyi files. The prompt registry reads sibling .md files at
    # runtime, so they have to be added explicitly.
    .add_local_dir(
        str(PROJECT_ROOT / "backend" / "app" / "agent" / "prompts"),
        "/root/backend/app/agent/prompts",
    )
)

app = modal.App("ops-agent")
volume = modal.Volume.from_name("ops-agent-data", create_if_missing=True)

# Secrets, create with `modal secret create ops-agent-secrets ANTHROPIC_API_KEY=... TAVILY_API_KEY=...`
secrets = [modal.Secret.from_name("ops-agent-secrets", required_keys=["ANTHROPIC_API_KEY", "TAVILY_API_KEY"])]


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/data": volume},
    timeout=600,
    min_containers=0,
)
@modal.asgi_app()
def fastapi_app():  # type: ignore[no-untyped-def]
    # Local imports, the Modal worker imports the app inside the container.
    import os  # noqa: PLC0415

    os.environ.setdefault("SQLITE_PATH", "/data/ops_agent.db")
    os.environ.setdefault("APP_ENV", "modal")
    # Starlette's CORSMiddleware compares ``allow_origins`` exactly; a glob like
    # ``https://*.vercel.app`` is a literal string and matches no browser.
    # Use ``CORS_ORIGIN_REGEX`` for preview deploys instead.
    os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
    os.environ.setdefault(
        "CORS_ORIGIN_REGEX",
        r"https://[a-z0-9-]+\.vercel\.app",
    )
    # SQLite WAL on a Modal Volume can lose ``-wal`` files between cold starts.
    # Use the rollback-journal mode for durability on network-backed volumes.
    os.environ.setdefault("SQLITE_JOURNAL_MODE", "DELETE")
    from backend.app.main import app as fastapi  # noqa: PLC0415

    return fastapi
