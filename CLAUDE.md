# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
| Image gen (dataset-build) | ComfyUI + Flux.2 Klein 4B GGUF + reference image conditioning | Phase 0 wired |
| Image gen (inference) | ComfyUI + Flux.2 Klein 4B GGUF + Riley LoRA + InstaPic Ultrareal + Ultra Real Klein 9B | Phase 1 |
| LoRA training | ai-toolkit on Modal L4 | Phase 0 in progress |
| Curation ML | ArcFace (insightface), LAION aesthetic, Falconsai NSFW, CLIP | Phase 1 |
| Captions | Anthropic Claude Sonnet w/ prompt caching | Phase 1 |
| Review UI | Streamlit multi-page app (`src/ai_studio/sme_ui/`) | Phase 1 |
| Posting | Instagram Graph API | Phase 1 (sandbox) / Phase 2 (App Review) |
| Video | Kling via fal.ai | Phase 3 |

## Module structure

Most `src/ai_studio/` submodules are **empty stubs** — they exist to hold Phase 1+ code:

```
src/ai_studio/
  cli.py                    Typer CLI — see "CLI surface" below
  config.py                 pydantic-settings; env prefix AISTUDIO_
  personas/__init__.py      Persona dataclass + YAML loader
  generation/
    image_clients/
      comfyui_client.py     Modal-backed ComfyUI HTTP client (Phase 0+) — IMPLEMENTED
      fal.py                Legacy fal.ai bare-Flux client (fallback) — IMPLEMENTED
    video_clients/          STUB
  calendar/                 STUB (Phase 2)
  captions/                 STUB (Phase 1)
  curation/                 STUB (Phase 1)
  db/                       STUB (Phase 1)
  posting/                  STUB (Phase 1)
  sme_ui/                   STUB (Phase 1)
  training/                 STUB (Phase 0 step 5)
  utils/                    STUB
infra/modal_app.py          Modal serverless app: ComfyUI on L4, model volume
workflows/
  consistent_character_dataset.json   API-format ComfyUI workflow (see Workflow section)
data/personas/riley.yaml    Primary persona definition
archive/historical_shorts_v1/         Pre-pivot Wikipedia-shorts code; reference only
TODO.md                     Phase 0–3 roadmap
```

## CLI surface

```bash
# IMPLEMENTED
studio generate-faces riley --count 20     # fal.ai FLUX Pro 2 (no LoRA; legacy path)
studio dataset-build riley --count 80      # ComfyUI on Modal with realism LoRA stack
studio upload-lora <path>                  # push .safetensors to Modal volume

# STUBS
studio train riley --dataset <path>        # Phase 0 step 5: ai-toolkit on Modal L4
studio generate --persona riley --count 8  # Phase 1
studio caption --post-id <id>              # Phase 1
studio post --post-id <id>                 # Phase 1
studio run-once --persona riley ...        # Phase 1 orchestration
studio generate-week --primary riley       # Phase 2
studio post-today                          # Phase 3 (Modal Cron target)
```

## Key implementation details

**Prompt injection (`cli.py:_inject_persona_prompt`):** walks the workflow dict looking for `CLIPTextEncode` nodes whose `inputs.text` equals `{{POSITIVE_PROMPT}}` or `{{NEGATIVE_PROMPT}}` and replaces them with the persona's `face.base_prompt` / `face.negative_prompt`. The workflow file must use exactly those sentinel strings.

**ComfyUI routing (`comfyui_client.py`):** if `COMFYUI_LOCAL_URL` (or `local_url` arg) is set, runs against local ComfyUI; otherwise calls `modal.Cls.from_name("ai-studio-comfyui", "ComfyUIRunner")`. Modal path returns raw image bytes; local path polls `/history/{prompt_id}` then GETs `/view`.

**Modal app (`infra/modal_app.py`):**
- `model_volume` — `ai-studio-comfyui-models`, mounted at `/comfyui/models`; stores base models + LoRAs
- `ComfyUIRunner` — L4 GPU, 10 min timeout, 5 min idle warmth; starts ComfyUI subprocess on `127.0.0.1:8188`
- Custom nodes in the image: ComfyUI-Manager, ComfyUI-Impact-Pack, comfyui-reactor-node, **ComfyUI-GGUF** (required for `UnetLoaderGGUF`)
- Models downloaded: Flux.2 Klein 4B Q8_0 GGUF, clip_l, t5xxl_fp8, ae VAE

**Config (`config.py`):** all env vars prefixed `AISTUDIO_` (e.g. `AISTUDIO_MODAL_TOKEN_ID`). Key fields: `database_url`, `modal_token_id/secret`, `anthropic_api_key`, `fal_api_key`, `supabase_url/key`, `meta_app_id/secret`.

**Persona (`personas/__init__.py`):** `Persona.load("riley")` reads `data/personas/{slug}.yaml`. Key fields: `face.base_prompt`, `face.negative_prompt`, `face.aspect_ratio`, `tone`.

## Workflow JSON — how the CCDB workflow works

`workflows/consistent_character_dataset.json` is the Civitai 2325916 workflow exported in ComfyUI API format. It achieves character consistency via **reference image conditioning**, not LoRAs:

1. `LoadImage` (node 166) loads `Character Base.jpeg` — the reference face photo
2. `ImageScaleToTotalPixels` → `VAEEncode` → `ReferenceLatent` — the reference is encoded and attached to the conditioning
3. `CLIPTextEncode` (node 252) encodes the text prompt; both positive and negative conditionings carry the reference latent
4. `SamplerCustomAdvanced` generates at 4 steps (Flux.2 Klein is step-distilled)

**Models required** (different from the old placeholder):

| Node | Model path in volume |
|---|---|
| `UnetLoaderGGUF` | `FLUX.2/flux-2-klein-4b-Q8_0.gguf` |
| `CLIPLoader` | `FLUX.2/qwen_3_4b.safetensors` |
| `VAELoader` | `FLUX.2/flux2-vae.safetensors` |

**Custom nodes required** (beyond ComfyUI-GGUF):
- `ComfyUI_Comfyroll_CustomNodes` — `JoinStringMulti`, `SetImageSize`, `PrimitiveString`
- `comfyui-image-saver` — image save node (node 228)

**CLI injection points** (what `dataset-build` must set at runtime):
- Node 166 `inputs.image` → reference image filename (e.g. `riley_reference.jpeg`)
- Node 238 `inputs.value` → persona first name
- Node 239 `inputs.value` → persona last name
- Node 252 `inputs.text` → `{{POSITIVE_PROMPT}}` sentinel → replaced by persona's `face.base_prompt`

Node 254 ("Type Character Prompts") exported with `UNKNOWN` class — replace with a plain `CLIPTextEncode` wired to the same text.

**The realism LoRAs (InstaPic Ultrareal, Ultra Real Klein 9B) are NOT used in dataset-build.** They belong in the Phase 1 inference workflow (`workflows/flux_lora_inference.json`) stacked with Riley's trained identity LoRA.

## Dev setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env       # add AISTUDIO_MODAL_TOKEN_ID etc.
pre-commit install
pytest
pytest tests/unit/test_cli_smoke.py::test_root_help -v   # single test
```

Local ComfyUI override (skip Modal when iterating on workflows):
```bash
COMFYUI_LOCAL_URL=http://localhost:8188 studio dataset-build riley --count 3
```

## Modal setup (one-time)

```bash
modal token set --token-id <ID> --token-secret <SECRET>
modal deploy infra/modal_app.py
modal run infra/modal_app.py::download_models    # ~15 min: downloads all models to volume
```

LoRAs live in the same Modal Volume as base models. Upload via `studio upload-lora`.

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

- **No comments unless WHY is non-obvious.** Identifier names explain WHAT.
- **No backwards-compat shims** for code we're actively replacing.
- **No defensive error handling for impossible cases.** Trust internal code; validate only at system boundaries.
- **All external API calls mocked in tests.** Never hit live endpoints from `pytest`.
- **External secrets via `config.get_settings()`**, never direct `os.environ` reads in business logic.
- **Modal functions stay in `infra/`**; business logic stays in `src/ai_studio/`.

## What NOT to add

Explicitly deferred — don't add speculatively:
- Celery / Redis async pipeline
- Multi-platform support (TikTok, Pinterest)
- Caption A/B testing
- Auto-DM responses
- Web dashboard beyond Streamlit
- Self-hosted GPU (Modal economics win at our scale)

## Useful references

- Modal docs: https://modal.com/docs
- Supabase docs: https://supabase.com/docs
- ComfyUI API guide: https://github.com/comfyanonymous/ComfyUI#api
- fal.ai docs: https://fal.ai/docs
- Instagram Graph API: https://developers.facebook.com/docs/instagram-platform
