# AI Influencer Studio

A persona-driven AI Instagram content pipeline. ComfyUI + Flux + LoRAs (face consistency), Kling for occasional video, Claude for captions, GCP for the control plane, Modal Labs for serverless GPU.

The first persona is a wealthy young woman golfer (slow-living/wellness aesthetic, men 18–38 audience). She lives inside a network of 4–5 girlfriends and 1–2 boyfriends who appear in cross-tagged synchronized posts.

> **Status:** Stage 1 (base face generation) working. 30-day POC in progress.
>
> The pre-pivot Wikipedia-shorts generator is preserved at `archive/historical_shorts_v1/` for reference.

## Layout

```
src/ai_studio/        # Python package (db, personas, calendar, generation,
                      # training, curation, sme_ui, captions, posting, utils)
tests/                # pytest unit tests (external APIs always mocked)
workflows/            # ComfyUI API-format workflow JSONs
data/                 # YAML persona/activity configs; reference images (gitignored)
terraform/            # GCP infra (Cloud SQL, GCS, Secret Manager, budget alerts)
infra/                # Modal app definitions (modal_app.py, modal_train.py)
scripts/              # ad-hoc CLI wrappers
archive/              # pre-pivot code, kept for reference
```

## Dev setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # add your API keys (see table below)
pre-commit install
pytest
studio --help
```

**Required API keys** (fill in `.env`):

| Variable | Purpose | Get it at |
|---|---|---|
| `AISTUDIO_FAL_API_KEY` | FLUX 2 Pro + PuLID image generation | fal.ai/dashboard |
| `AISTUDIO_ANTHROPIC_API_KEY` | Caption generation | console.anthropic.com |

## Stage 1 — Base Face Generation

Generate candidate faces for a persona using FLUX 2 Pro (text-to-image, no LoRA yet):

```bash
studio generate-faces riley           # generates 20 candidates (~$1.40, ~3 min)
studio generate-faces riley --count 3 # quick test run
```

Output: `data/outputs/riley/stage1_candidates/candidate_001.jpg` ...
Face prompt and settings come from `data/personas/riley.yaml`, which mirrors the Character Bible in Notion.

## Phases

- **Phase 0** — train the primary persona's LoRA (Modal + ai-toolkit). Unblocks consistency.
- **Phase 1** — single-persona end-to-end POC: generate → score → SME pick → caption → post (sandbox).
- **Phase 2** — network of 6–7 personas, calendar coordination, cross-tagged posts, Meta App Review.
- **Phase 3** — Kling video, scheduled automation, b-roll authenticity mix, GCE migration evaluation.

See the plan file for full detail.
