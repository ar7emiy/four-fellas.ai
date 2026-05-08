"""Typer entry point for AI Influencer Studio.

Each command below is a thin stub that will be filled out in subsequent phases.
The shape of the CLI is the contract the rest of the project (and the SME UI,
and the verification steps in the plan) depends on.
"""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(
    name="studio",
    help="AI Influencer Studio — persona-driven Instagram content pipeline.",
    no_args_is_help=True,
)


@app.command("generate-faces")
def generate_faces(
    persona: str = typer.Argument(..., help="Persona slug (e.g. 'riley')."),
    count: int = typer.Option(0, help="Number of candidates. 0 = use persona default."),
) -> None:
    """Stage 1: generate candidate base faces via FLUX 2 Pro (fal.ai). No LoRA, no PuLID."""
    from ai_studio.generation.image_clients.fal import generate_faces as _gen
    from ai_studio.personas import Persona

    p = Persona.load(persona)
    n = count or p.face.candidate_count
    output_dir = Path("data/outputs") / persona / "stage1_candidates"

    typer.echo(f"Generating {n} candidate faces for '{persona}' → {output_dir}")
    saved = _gen(
        prompt=p.face.base_prompt,
        count=n,
        output_dir=output_dir,
        aspect_ratio=p.face.aspect_ratio,
        negative_prompt=p.face.negative_prompt,
    )
    typer.echo(f"✓ Saved {len(saved)} images to {output_dir}")


@app.command()
def init() -> None:
    """Run DB migrations and seed personas from data/personas/*.yaml."""
    typer.echo("[stub] studio init — Phase 1 will implement Alembic migrate + seed.")


@app.command("dataset-build")
def dataset_build(
    persona: str = typer.Option(..., help="Persona slug (e.g. 'golfer')."),
    count: int = typer.Option(80, help="Candidate images to generate."),
) -> None:
    """Phase 0: run consistent-character ComfyUI workflow on Modal to build a LoRA dataset."""
    typer.echo(f"[stub] studio dataset-build --persona {persona} --count {count}")


@app.command()
def train(
    persona: str = typer.Argument(..., help="Persona slug."),
    reference: str = typer.Option(..., help="Path to reference image dir."),
) -> None:
    """Phase 0: train a LoRA via ai-toolkit on Modal L4. Uploads .safetensors to GCS."""
    typer.echo(f"[stub] studio train {persona} --reference {reference}")


@app.command()
def generate(
    persona: str = typer.Option(..., help="Persona slug."),
    activity: str = typer.Option(..., help="Activity template slug."),
    count: int = typer.Option(8, help="Candidates to generate."),
) -> None:
    """Phase 1: generate candidate images via Modal ComfyUI w/ persona LoRA."""
    typer.echo(f"[stub] studio generate --persona {persona} --activity {activity} --count {count}")


@app.command()
def caption(post_id: int = typer.Option(..., help="Post ID.")) -> None:
    """Phase 1: generate caption + hashtags for a reviewed post via Claude."""
    typer.echo(f"[stub] studio caption --post-id {post_id}")


@app.command()
def post(post_id: int = typer.Option(..., help="Post ID.")) -> None:
    """Phase 1: publish post to Instagram via Graph API."""
    typer.echo(f"[stub] studio post --post-id {post_id}")


@app.command("run-once")
def run_once(
    persona: str = typer.Option(..., help="Persona slug."),
    activity: str = typer.Option(..., help="Activity template slug."),
) -> None:
    """Phase 1: end-to-end orchestration — generate, score, await SME pick, caption, post."""
    typer.echo(f"[stub] studio run-once --persona {persona} --activity {activity}")


@app.command("generate-week")
def generate_week(
    primary: str = typer.Option(..., help="Primary persona slug."),
) -> None:
    """Phase 2: produce 7 days of cross-coordinated content for the network."""
    typer.echo(f"[stub] studio generate-week --primary {primary}")


@app.command("post-today")
def post_today() -> None:
    """Phase 3: scheduled daily posting entry (Cloud Scheduler target)."""
    typer.echo("[stub] studio post-today")


if __name__ == "__main__":
    app()
