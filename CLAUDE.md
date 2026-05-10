# Four Fellas AI — Claude Code Workspace

## Project Overview

AI Instagram influencer pipeline: Persona-driven content generation with face consistency via LoRAs. Stack: Modal (GPU) + Supabase (DB + storage).

**Current status:** Phase 0 (dataset generation + LoRA training) in progress.

## Key Files

- `README.md` — quick start + Phase 0 instructions
- `src/ai_studio/` — main package (generation, curation, posting, SME UI)
- `infra/modal_app.py` — Modal serverless ComfyUI wrapper
- `workflows/consistent_character_dataset.json` — ComfyUI workflow for dataset gen (to be replaced with Civitai 2325916)
- `data/personas/riley.yaml` — primary persona (wealthy golfer, slow-living aesthetic)
- `pyproject.toml` — dependencies (Modal, Supabase, Anthropic, SQLAlchemy)

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
pytest
studio --help
```

## Architecture

**2 platforms:**
- **Modal Labs** — ComfyUI serverless, L4 GPU, LoRA training, model caching, secrets, cron
- **Supabase** — Postgres (Phase 2+), file storage (Phase 2+)

**Phase 0 pipeline:**
1. Generate 80 base Flux images (consistent-character workflow on Modal)
2. Human cull to 35–40 (SME UI)
3. Train LoRA via ai-toolkit on Modal L4
4. Validate on holdout test images

**Phase 1:** Single-persona end-to-end (generate → score → caption → post to sandbox IG)

**Phase 2:** Multi-persona network, calendar coordination, cross-tagged posts, Meta App Review

**Phase 3:** Kling video, Modal Cron daily posting, Supabase Storage, cost analysis

## Modal Setup

```bash
# Get tokens from modal.com → Settings → API Tokens
modal token set --token-id <ID> --token-secret <SECRET>

# Deploy ComfyUI
modal deploy infra/modal_app.py

# Download Flux.2 Klein model (one-time, ~15 min)
modal run infra/modal_app.py::download_models
```

## Running Phase 0

See README.md for the step-by-step 10-item checklist.

## Key Commands

```bash
studio dataset-build riley --count 80      # Generate candidates
studio upload-lora <path>                  # Upload LoRA to Modal volume
studio train riley --dataset <path>        # Train LoRA
studio generate --persona riley --count 8  # Phase 1+: generate with LoRA
```

## Testing

```bash
pytest                          # Run all tests
pytest -v tests/unit/           # Verbose unit tests
pre-commit run --all-files      # Lint + type check
```

## Environment

See `.env.example` for all variables. Minimum for Phase 0:
- `AISTUDIO_MODAL_TOKEN_ID` + `AISTUDIO_MODAL_TOKEN_SECRET`
- `AISTUDIO_FAL_API_KEY` (for Phase 3 Kling video)
- `AISTUDIO_ANTHROPIC_API_KEY` (for captions)

## Notes

- Database defaults to SQLite (Phase 0–1), can swap to Supabase Postgres (Phase 2+)
- All generated images saved to `data/outputs/` (gitignored)
- Pre-pivot Wikipedia-shorts code archived at `archive/historical_shorts_v1/`
- ComfyUI workflows (Flux inference, face swap) to be added in Phase 1–2

## References

- Plan: `/root/.claude/plans/delete-this-entire-project-jaunty-parasol.md` (on session machine)
- Modal docs: modal.com/docs
- Supabase docs: supabase.com/docs
- ComfyUI: github.com/comfyanonymous/ComfyUI
