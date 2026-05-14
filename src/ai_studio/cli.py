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
    persona: str = typer.Argument(..., help="Persona slug (e.g. 'riley')."),
    workflow: Path = typer.Option(
        Path("workflows/consistent_character_dataset.json"),
        help="ComfyUI API-format workflow JSON.",
        exists=True,
    ),
    count: int = typer.Option(80, help="Number of candidate images to generate."),
    local: bool = typer.Option(False, help="Use local ComfyUI instead of Modal."),
) -> None:
    """Phase 0: run consistent-character ComfyUI workflow (Modal or local) to build LoRA dataset.

    Generates <count> candidate images via Flux.2 Klein + realism LoRA stack,
    saves to data/outputs/<persona>/dataset_candidates/.
    """
    import json as _json

    from ai_studio.generation.image_clients.comfyui_client import ComfyUIClient
    from ai_studio.personas import Persona

    p = Persona.load(persona)
    output_dir = Path("data/outputs") / persona / "dataset_candidates"

    if not p.reference_image:
        typer.echo(f"Error: persona '{persona}' has no reference_image in its YAML.", err=True)
        raise typer.Exit(1)

    ref_path = Path("data/personas") / p.reference_image
    if not ref_path.exists():
        typer.echo(f"Error: reference image not found: {ref_path}", err=True)
        raise typer.Exit(1)

    ref_filename = ref_path.name
    ref_bytes = ref_path.read_bytes()

    raw = _json.loads(workflow.read_text())
    wf = _inject_persona_prompt(raw, p.face.base_prompt, p.face.negative_prompt)
    wf = _inject_persona_runtime(wf, ref_filename)

    client = ComfyUIClient(local_url="http://localhost:8188" if local else None)

    typer.echo(
        f"Running dataset build for '{persona}' -> {output_dir}\n"
        f"  workflow: {workflow}\n"
        f"  reference: {ref_path}\n"
        f"  count: {count}\n"
        f"  backend: {'local' if local else 'Modal L4'}"
    )

    import random as _random

    all_saved: list[Path] = []
    for i in range(count):
        typer.echo(f"  [{i + 1}/{count}] generating...", nl=False)
        wf["257"]["inputs"]["noise_seed"] = _random.randint(0, 2**32 - 1)
        saved = client.run_workflow(
            workflow=wf,
            output_dir=output_dir,
            filename_prefix="candidate",
            input_images={ref_filename: ref_bytes},
        )
        all_saved.extend(saved)
        typer.echo(f" saved {[s.name for s in saved]}")

    typer.echo(f"\n✓ {len(all_saved)} candidates saved to {output_dir}")


def _inject_persona_prompt(
    workflow: dict,
    positive_prompt: str,
    negative_prompt: str,
) -> dict:
    """Replace placeholder prompts in the workflow with the persona's prompts.

    Looks for nodes with class_type 'CLIPTextEncode' whose text contains
    the marker strings '{{POSITIVE_PROMPT}}' or '{{NEGATIVE_PROMPT}}'.
    """
    import copy

    wf = copy.deepcopy(workflow)
    for node in wf.values():
        if node.get("class_type") != "CLIPTextEncode":
            continue
        text = node.get("inputs", {}).get("text", "")
        if "{{POSITIVE_PROMPT}}" in text:
            node["inputs"]["text"] = text.replace("{{POSITIVE_PROMPT}}", positive_prompt)
        if "{{NEGATIVE_PROMPT}}" in text:
            node["inputs"]["text"] = text.replace("{{NEGATIVE_PROMPT}}", negative_prompt)
    return wf


def _inject_persona_runtime(
    workflow: dict,
    reference_image_filename: str,
) -> dict:
    """Inject runtime values into CCDB workflow nodes.

    Node 166 (LoadImage): reference face filename.
    """
    import copy

    wf = copy.deepcopy(workflow)
    if "166" in wf:
        wf["166"]["inputs"]["image"] = reference_image_filename
    return wf


@app.command("upload-lora")
def upload_lora(
    lora_file: Path = typer.Argument(..., help="Path to .safetensors LoRA file.", exists=True),
    name: str = typer.Option("", help="Destination filename in volume. Defaults to source filename."),
) -> None:
    """Upload a LoRA .safetensors file to the Modal model volume."""
    from ai_studio.generation.image_clients.comfyui_client import ComfyUIClient

    client = ComfyUIClient()
    dest = name or lora_file.name
    typer.echo(f"Uploading {lora_file.name} → {dest} ({lora_file.stat().st_size / 1e6:.1f} MB)...")
    client.upload_lora(lora_file, dest_name=dest or None)
    typer.echo("✓ Done. LoRA available in Modal ComfyUI.")


@app.command()
def train(
    persona: str = typer.Argument(..., help="Persona slug."),
    reference: str = typer.Option(..., help="Path to reference image dir."),
) -> None:
    """Phase 0: train a LoRA via ai-toolkit on Modal L4. Uploads .safetensors to Modal volume."""
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
    """Phase 3: scheduled daily posting entry (Modal Cron target)."""
    typer.echo("[stub] studio post-today")


if __name__ == "__main__":
    app()
