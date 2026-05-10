# Claude Code Workspace — Four Fellas AI

This file is the orientation doc for AI coding agents (Claude Code) working on this repo. Humans should read `README.md` first.

## What this project is

A persona-driven AI Instagram pipeline. One trained character LoRA per persona ensures face consistency across daily posts; ComfyUI on Modal does the inference; Anthropic Claude writes captions; Instagram Graph API publishes.

First persona is **Riley** — a wealthy young woman golfer (`data/personas/riley.yaml`). Future personas will form her network (friends, partner) with cross-tagged synchronized posts.

## Architecture principle

**KISS.** Simplest path to end-to-end first. Two platforms total: Modal + Supabase. No GCP, no Terraform, no Celery. Every Phase ships a working product.

## Stack

| Layer | Tool | Status |
|---|---|---|
| GPU compute, model cache, secrets, cron | Modal Labs | Phase 0 wired |
| DB (Phase 0–1) | SQLite | configured |
| DB + Storage (Phase 2+) | Supabase | not yet provisioned |
| Image gen | ComfyUI + Flux.2 Klein 4B GGUF + InstaPic Ultrareal + Ultra Real Klein 9B + SRPO face detailer | Phase 0 wired |
| LoRA training | ai-toolkit on Modal L4 | Phase 0 in progress |
| Curation ML | ArcFace (insightface), LAION aesthetic, Falconsai NSFW, CLIP | Phase 1 |
| Captions | Anthropic Claude Sonnet w/ prompt caching | Phase 1 |
| Review UI | Streamlit multi-page app (`src/ai_studio/sme_ui/`) | Phase 1 |
| Posting | Instagram Graph API | Phase 1 (sandbox) / Phase 2 (App Review) |
| Video | Kling via fal.ai | Phase 3 |

## Key files

```
src/ai_studio/cli.py                              Typer CLI (every command stubbed)
src/ai_studio/config.py                           pydantic-settings; .env in dev, Modal Secrets in prod
src/ai_studio/personas/__init__.py                Persona dataclass loader
src/ai_studio/generation/image_clients/
  comfyui_client.py                               Modal-backed ComfyUI HTTP client (Phase 0+)
  fal.py                                          Legacy fal.ai bare-Flux client (kept for fallback)
infra/modal_app.py                                Modal serverless app: ComfyUI on L4, model volume
workflows/consistent_character_dataset.json       Placeholder; replace with Civitai 2325916 (API Format)
data/personas/riley.yaml                          Primary persona definition
archive/historical_shorts_v1/                     Pre-pivot Wikipedia-shorts code; reference only
TODO.md                                           Phase 0–3 roadmap
```

## Phase 0 (current focus)

Goal: train Riley's identity LoRA so Phase 1 has face consistency from day 1.

Flow:
1. **Base Flux generates 80 candidates** with a fixed character prompt via the consistent-character workflow
2. **Human culls to 35–40** (manual file moving for Phase 0; proper SME UI lands in Phase 1)
3. **Train LoRA** with ai-toolkit on Modal L4 (~30–60 min)
4. **Validate** by generating 10 holdout images with the LoRA loaded

See `README.md` for the operator step-by-step. See `TODO.md` for granular tracking.

## CLI surface (current)

```bash
studio generate-faces riley --count 20     # legacy: bare Flux via fal.ai (no LoRA)
studio dataset-build riley --count 80      # Phase 0: ComfyUI on Modal w/ realism LoRA stack
studio upload-lora <path>                  # push .safetensors to Modal volume
studio train riley --dataset <path>        # stub — Phase 0 step 5
studio generate --persona riley --count 8  # stub — Phase 1
studio caption --post-id <id>              # stub — Phase 1
studio post --post-id <id>                 # stub — Phase 1
studio run-once --persona riley ...        # stub — Phase 1 orchestration
studio generate-week --primary riley       # stub — Phase 2
studio post-today                          # stub — Phase 3 (Modal Cron target)
```

## Dev setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env       # add Modal tokens + API keys
pre-commit install
pytest
```

Local ComfyUI override (skip Modal when iterating on workflows):
```bash
COMFYUI_LOCAL_URL=http://localhost:8188 studio dataset-build riley --count 3
```

## Modal setup (one-time)

```bash
modal token set --token-id <ID> --token-secret <SECRET>
modal deploy infra/modal_app.py
modal run infra/modal_app.py::download_models    # ~15 min: Flux.2 Klein GGUF + encoders + VAE
```

LoRAs live in the same Modal Volume as the base models. Upload them via `studio upload-lora`.

## Testing conventions

- Unit tests under `tests/unit/`; integration fixtures under `tests/fixtures/api_schemas/`
- **External APIs always mocked** (respx for httpx, responses for requests)
- Tests assert request shapes match documented schemas (Instagram Graph API, Claude Messages, ComfyUI, Modal)
- `pytest -v` before pushing; `pre-commit run --all-files` enforces ruff + mypy strict on `src/`

## Branches

- `main` — default branch, ship-ready
- Feature work: `<scope>/<short-desc>` (e.g. `phase1/curation-pipeline`)
- Open draft PR into `main`; squash-merge after review

## Coding conventions

- **No comments unless WHY is non-obvious.** Identifier names should explain WHAT.
- **No backwards-compat shims** for code we're actively replacing.
- **No defensive error handling for impossible cases.** Trust internal code; validate only at system boundaries.
- **All external API calls mocked in tests.** Never hit live endpoints from `pytest`.
- **External secrets via `config.get_settings()`**, never direct `os.environ` reads in business logic.
- **Modal functions stay in `infra/`**; business logic stays in `src/ai_studio/`.

## What NOT to add

The plan explicitly defers these. Don't add them speculatively:
- Celery / Redis async pipeline
- Multi-platform support (TikTok, Pinterest)
- Caption A/B testing
- Auto-DM responses
- Web dashboard beyond Streamlit
- Self-hosted GPU on GCE (we considered, dropped — Modal economics win at our scale)

## Useful references

- Modal docs: https://modal.com/docs
- Supabase docs: https://supabase.com/docs
- ComfyUI API guide: https://github.com/comfyanonymous/ComfyUI#api
- fal.ai docs: https://fal.ai/docs
- Instagram Graph API: https://developers.facebook.com/docs/instagram-platform
