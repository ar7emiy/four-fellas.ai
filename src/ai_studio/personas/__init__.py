from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class FaceConfig(BaseModel):
    base_prompt: str
    negative_prompt: str = ""
    candidate_count: int = 20
    aspect_ratio: str = "9:16"


class PulidConfig(BaseModel):
    reference_strength: float = 0.8


class VoiceConfig(BaseModel):
    design_prompt: str
    voice_id: str | None = None


class Persona(BaseModel):
    name: str
    niche: str
    status: str
    reference_image: str | None = None
    face: FaceConfig
    pulid: PulidConfig = PulidConfig()
    voice: VoiceConfig
    tone: str

    @classmethod
    def load(cls, slug: str) -> "Persona":
        path = Path("data/personas") / f"{slug}.yaml"
        with path.open() as f:
            return cls.model_validate(yaml.safe_load(f))
