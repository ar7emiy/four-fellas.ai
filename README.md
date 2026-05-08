# AI Influencer Studio

A persona-driven AI Instagram content pipeline. ComfyUI + Flux + LoRAs (face consistency), Kling for occasional video, Claude for captions, GCP for the control plane, Modal Labs for serverless GPU.

The first persona is a wealthy young woman golfer (slow-living/wellness aesthetic, men 18–38 audience). She lives inside a network of 4–5 girlfriends and 1–2 boyfriends who appear in cross-tagged synchronized posts.

> **Status:** scaffolded, no functional code yet. See `/root/.claude/plans/delete-this-entire-project-jaunty-parasol.md` for the full plan and phase breakdown.
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

## Dev setup (forthcoming)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fill in values
pre-commit install
pytest
studio --help
```

## Phases

- **Phase 0** — train the primary persona's LoRA (Modal + ai-toolkit). Unblocks consistency.
- **Phase 1** — single-persona end-to-end POC: generate → score → SME pick → caption → post (sandbox).
- **Phase 2** — network of 6–7 personas, calendar coordination, cross-tagged posts, Meta App Review.
- **Phase 3** — Kling video, scheduled automation, b-roll authenticity mix, GCE migration evaluation.

See the plan file for full detail.
