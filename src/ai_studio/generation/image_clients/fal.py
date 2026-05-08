from __future__ import annotations

from pathlib import Path

import fal_client
import httpx
from tqdm import tqdm

from ai_studio.config import get_settings

_MODEL = "fal-ai/flux-pro/v1.1-ultra"


def generate_faces(
    prompt: str,
    count: int,
    output_dir: Path,
    aspect_ratio: str = "9:16",
    negative_prompt: str = "",
) -> list[Path]:
    api_key = get_settings().fal_api_key
    client = fal_client.SyncClient(key=api_key)
    output_dir.mkdir(parents=True, exist_ok=True)

    arguments: dict = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "output_format": "jpeg",
    }
    if negative_prompt:
        arguments["negative_prompt"] = negative_prompt

    saved: list[Path] = []

    with httpx.Client(timeout=120) as http:
        for i in tqdm(range(count), desc="Generating faces", unit="img"):
            result = client.run(_MODEL, arguments=arguments)
            image_url = result["images"][0]["url"]

            img_bytes = http.get(image_url).raise_for_status().content
            path = output_dir / f"candidate_{i + 1:03d}.jpg"
            path.write_bytes(img_bytes)
            saved.append(path)

    return saved
