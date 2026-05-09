# AI Influencer Studio

Persona-driven AI Instagram content pipeline. Two platforms only: **Modal** (GPU + compute) + **Supabase** (DB + storage).

The first persona is Riley — a wealthy young woman golfer (slow-living/wellness aesthetic). She lives inside a network of 4–5 girlfriends + 1–2 boyfriends with cross-tagged synchronized posts.

> **Status:** Phase 0 in progress — Modal ComfyUI pipeline wired, working on first realistic dataset generation.
>
> Pre-pivot Wikipedia-shorts generator preserved at `archive/historical_shorts_v1/`.

---

## Stack

| Layer | Tool |
|---|---|
| GPU compute | Modal Labs (serverless L4, ComfyUI + LoRA training) |
| Model/LoRA storage | Modal Volume |
| Secrets + Cron | Modal Secrets + Modal Cron |
| Database | SQLite (Phase 0–1) → Supabase Postgres (Phase 2+) |
| File storage | Local disk (Phase 0–1) → Supabase Storage (Phase 2+) |
| Image gen | ComfyUI + Flux.2 Klein 4B GGUF + InstaPic Ultrareal LoRA + SRPO face detailer |
| Captions | Anthropic Claude Sonnet (prompt caching) |
| Posting | Instagram Graph API |

No GCP. No Terraform. No Railway.

---

## Layout

```
src/ai_studio/      # Python package
infra/              # Modal app (modal_app.py, modal_train.py)
workflows/          # ComfyUI API-format workflow JSONs
data/personas/      # YAML persona configs
data/activities/    # YAML activity templates
data/outputs/       # Generated images (gitignored)
archive/            # Pre-pivot code
```

---

## Dev setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in Modal tokens + API keys
pre-commit install
pytest
studio --help
```

**Minimum required for Phase 0:**

| Variable | Where |
|---|---|
| `AISTUDIO_MODAL_TOKEN_ID` + `AISTUDIO_MODAL_TOKEN_SECRET` | modal.com → Settings → API Tokens |
| `AISTUDIO_FAL_API_KEY` | fal.ai/dashboard (for Kling video later) |
| `AISTUDIO_ANTHROPIC_API_KEY` | console.anthropic.com |

---

## Phase 0 — Dataset generation (current)

```bash
# 1. Download from Civitai (free, login required):
#    Workflow: civitai.com/models/2325916  → Save (API Format) → replace workflows/consistent_character_dataset.json
#    LoRA 1:   civitai.com/models/2168120  (InstaPic Ultrareal)
#    LoRA 2:   civitai.com/models/2462105  (Ultra Real Klein 9B)

# 2. Deploy Modal + seed models (one-time, ~20 min for Flux.2 Klein GGUF download)
modal deploy infra/modal_app.py
modal run infra/modal_app.py::download_models

# 3. Upload LoRAs to Modal Volume
studio upload-lora ~/Downloads/instapic_ultrareal.safetensors
studio upload-lora ~/Downloads/ultra_real_klein_9b.safetensors

# 4. Generate candidates
studio dataset-build riley --count 3    # quick test
studio dataset-build riley --count 80   # full dataset for LoRA training
```

Output: `data/outputs/riley/dataset_candidates/`

---

## Phases

- **Phase 0** — Train the persona LoRA (base Flux → cull → ai-toolkit on Modal L4)
- **Phase 1** — Single-persona end-to-end: generate → score → SME pick → caption → post (sandbox)
- **Phase 2** — Network of 6–7 personas, calendar coordination, cross-tagged posts. Switch DB to Supabase.
- **Phase 3** — Kling video, Modal Cron for daily posting, Supabase Storage for images

See the plan file for full detail.
