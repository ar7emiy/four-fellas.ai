"""ComfyUI client — wraps the Modal-hosted ComfyUI runner.

For local dev/testing, can also target a local ComfyUI instance directly via
COMFYUI_LOCAL_URL env var (e.g. http://localhost:8188).
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any


class ComfyUIClient:
    """Thin client that either calls the Modal runner or a local ComfyUI server."""

    def __init__(self, local_url: str | None = None) -> None:
        self._local_url = local_url or os.getenv("COMFYUI_LOCAL_URL")

    def run_workflow(
        self,
        workflow: dict[str, Any],
        output_dir: Path,
        filename_prefix: str = "output",
        output_node_ids: list[str] | None = None,
    ) -> list[Path]:
        """Run a workflow and save output images to output_dir.

        Prefers Modal runner unless COMFYUI_LOCAL_URL is set.
        """
        if self._local_url:
            images = self._run_local(workflow, output_node_ids)
        else:
            images = self._run_modal(workflow, output_node_ids)

        output_dir.mkdir(parents=True, exist_ok=True)
        saved: list[Path] = []
        for i, img_bytes in enumerate(images):
            ext = _sniff_ext(img_bytes)
            path = output_dir / f"{filename_prefix}_{i + 1:03d}{ext}"
            path.write_bytes(img_bytes)
            saved.append(path)
        return saved

    # ------------------------------------------------------------------
    # Modal path
    # ------------------------------------------------------------------

    def _run_modal(
        self,
        workflow: dict[str, Any],
        output_node_ids: list[str] | None,
    ) -> list[bytes]:
        import modal  # lazy import — only needed when using Modal

        ComfyUIRunner = modal.Cls.from_name("ai-studio-comfyui", "ComfyUIRunner")
        runner = ComfyUIRunner()
        return runner.run_workflow.remote(workflow, output_node_ids)

    # ------------------------------------------------------------------
    # Local path (dev / testing)
    # ------------------------------------------------------------------

    def _run_local(
        self,
        workflow: dict[str, Any],
        output_node_ids: list[str] | None,
    ) -> list[bytes]:
        assert self._local_url
        base = self._local_url.rstrip("/")

        client_id = f"studio-{int(time.time())}"
        payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode()

        req = urllib.request.Request(
            f"{base}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req)
        prompt_id = json.loads(resp.read())["prompt_id"]

        # Poll
        for _ in range(300):
            time.sleep(2)
            history = json.loads(
                urllib.request.urlopen(f"{base}/history/{prompt_id}").read()
            )
            if prompt_id in history:
                break
        else:
            raise TimeoutError(f"Prompt {prompt_id} timed out")

        # Collect
        outputs = history[prompt_id]["outputs"]
        if output_node_ids is None:
            output_node_ids = [
                k
                for k, v in workflow.items()
                if v.get("class_type") in ("SaveImage", "PreviewImage")
            ]

        images: list[bytes] = []
        for node_id in output_node_ids:
            for img_meta in outputs.get(node_id, {}).get("images", []):
                params = (
                    f"filename={img_meta['filename']}"
                    f"&subfolder={img_meta.get('subfolder', '')}"
                    f"&type={img_meta['type']}"
                )
                images.append(urllib.request.urlopen(f"{base}/view?{params}").read())
        return images

    # ------------------------------------------------------------------
    # LoRA upload helper
    # ------------------------------------------------------------------

    def upload_lora(self, lora_path: Path) -> None:
        """Upload a local LoRA .safetensors into the Modal model volume."""
        import modal

        upload_lora = modal.Function.from_name("ai-studio-comfyui", "upload_lora")
        upload_lora.remote(lora_path.name, lora_path.read_bytes())
        print(f"Uploaded LoRA '{lora_path.name}' to Modal volume.")


def _sniff_ext(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    return ".jpg"
