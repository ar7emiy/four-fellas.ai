# Roadmap

Tracks the active work. Granular session-level todos go in PR descriptions; this is the durable shape of the project.

## Phase 0 — Train Riley's LoRA (current)

Unblocks consistency for everything after. Without this, every "Riley" looks like a different woman.

The CCDB workflow achieves dataset consistency via **reference image conditioning** (VAE-encode a reference photo → `ReferenceLatent`), not LoRAs. The realism LoRAs (InstaPic Ultrareal, Ultra Real Klein 9B) are pre-loaded here but used in Phase 1 inference, not dataset-build.

- [x] Scaffold project + Modal ComfyUI pipeline wired (`infra/modal_app.py`, `comfyui_client.py`, `studio dataset-build`)
- [x] Platform consolidation (Modal + Supabase, no GCP/Terraform)
- [x] Download Civitai 2325916 workflow → exported as API Format → saved as `workflows/consistent_character_dataset.json`
- [x] Fix workflow for Modal: add missing custom nodes (Comfyroll, comfyui-image-saver) to `infra/modal_app.py`; reconcile model paths (`FLUX.2/` subdir, `qwen_3_4b`, `flux2-vae`)
- [x] Fix workflow prompt injection: replace broken node 254 (`UNKNOWN`) with a plain `CLIPTextEncode` using `{{POSITIVE_PROMPT}}`
- [x] Add `reference_image` field to `riley.yaml` and `Persona` dataclass
- [x] Update `cli.py` to inject reference image path into workflow node 166 (`LoadImage`) and character name into nodes 238/239
- [ ] Copy reference image → `data/personas/riley/reference.jpeg` (manual: copy `Character Base.jpeg` from Civitai download)
- [ ] One-time Modal setup: `modal deploy infra/modal_app.py` + `modal run infra/modal_app.py::download_models`
- [ ] Pre-load realism LoRAs to Modal volume for Phase 1: `studio upload-lora ultra_real_v4.safetensors --name instapic_ultrareal.safetensors` and `studio upload-lora V1_flux_klein.safetensors --name ultra_real_klein_9b.safetensors`
- [ ] Generate 80 candidates: `studio dataset-build riley --count 80`
- [ ] Manually cull 80 → 35–40 (move keepers to `data/outputs/riley/culled/`)
- [ ] Implement `studio train` command — ai-toolkit on Modal L4
- [ ] Train Riley's identity LoRA, push `.safetensors` to Modal volume
- [ ] Holdout validation: 10 generations with LoRA loaded, eyeball face consistency

## Phase 1 — Single-Persona Post, End-to-End

One image of Riley posted to a sandbox IG Business account, with her identity LoRA on.

- [ ] Alembic migrations + SQLite schema (personas, events, generations, candidate_scores, posts, audit_log)
- [ ] Persona row + LoRA registry seeded from `data/personas/riley.yaml`
- [ ] ComfyUI inference workflow (`workflows/flux_lora_inference.json`): Riley's identity LoRA + InstaPic Ultrareal + Ultra Real Klein 9B realism LoRAs stacked on Flux.2 Klein base
- [ ] Prompt builder: activity YAML + persona → Flux prompt with LoRA trigger tag
- [ ] `studio generate --persona riley --activity ...` writes 8 candidates + cost to DB
- [ ] Curation stack: ArcFace face-consistency, LAION aesthetic, Falconsai NSFW, CLIP prompt-alignment, hand-quality
- [ ] Composite score + auto-pass thresholds in `candidate_scores` table
- [ ] Streamlit multi-page SME UI (`src/ai_studio/sme_ui/`):
  - [ ] Page 1: dataset cull (replaces manual cull in Phase 0 going forward)
  - [ ] Page 2: LoRA validation
  - [ ] Page 3: post-candidate review
  - [ ] Page 4: caption review
- [ ] Caption writer: Claude Sonnet w/ prompt caching, persona voice profile
- [ ] EXIF/C2PA metadata stripper before upload
- [ ] Instagram Graph API client (dev mode against sandbox IG Business account)
- [ ] `studio run-once` end-to-end orchestration
- [ ] Unit tests: every module fully mocked, schema fixtures asserted

## Phase 2 — Network + Cross-Tagged Coordination

- [ ] Provision Supabase project + migrate DB from SQLite to Postgres
- [ ] Train LoRAs for 4–5 girlfriends + 1–2 boyfriends (reuse Phase 0 pipeline)
- [ ] Network seed: persona rows + relationship rows (best_friend, dating, sister)
- [ ] Calendar engine: 7-day rolling plan w/ activity templates and `allow_group=True`
- [ ] Coordination logic: one event → multiple `event_personas` rows → multiple POV generations → cross-referencing captions
- [ ] PuLID-Flux face-swap workflow for variations the LoRA struggles with
- [ ] `content_continuity` table rejecting outfit/location repeats within 14 days
- [ ] **Meta App Review submission** for `instagram_content_publish` (2–4 week lead time — start at beginning of Phase 2)
- [ ] `studio generate-week --primary riley` produces 7 days of cross-coordinated drafts

## Phase 3 — Video + Automation + Authenticity

- [ ] Kling video client via fal.ai (1–2 reels/week for primary persona only)
- [ ] Modal Cron schedules `studio post-today` daily
- [ ] Time-of-day jitter (±90 min around target slot)
- [ ] B-roll mixer: 10–20% real-world Pexels/Unsplash imagery (no people)
- [ ] LoRA drift detector + monthly auto-retraining
- [ ] Migrate generated images from local disk to Supabase Storage
- [ ] Engagement metrics ingestion via Instagram Insights API → Supabase
- [ ] FB Business Manager compartmentalization (split 7 IG accounts across 2–3 BMs)
- [ ] Cost analysis dashboard (Modal spend + IG account health)

## Backlog (intentionally deferred)

- Celery / Redis (Typer CLI is fine for POC)
- Multi-platform (TikTok, Pinterest, X)
- Caption A/B testing
- Auto-DM responses
- Web dashboard beyond Streamlit
- Voice generation for video clips
- Self-hosted GPU on GCE (Modal economics win at our scale)
- Multi-region failover
