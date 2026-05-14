"""Modal serverless ComfyUI app.

Exposes a single endpoint: POST /run_workflow(workflow_json, loras) → list[bytes]

Models and custom nodes are cached in a Modal Volume so they only download once.
First cold start will take ~15 min (downloading Flux.2 Klein GGUF + custom nodes).
Subsequent starts are <30s.

Usage:
    modal deploy infra/modal_app.py          # deploy
    modal run infra/modal_app.py::test_ping  # smoke test
"""

from __future__ import annotations

import io
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

import modal

# ---------------------------------------------------------------------------
# Volumes & image
# ---------------------------------------------------------------------------

COMFYUI_DIR = Path("/comfyui")
VOLUME_NAME = "ai-studio-comfyui-models"

# Cache models + custom nodes across runs
model_volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

# ---------------------------------------------------------------------------
# Container image
# ---------------------------------------------------------------------------

# Install ComfyUI + all required custom nodes for the realism stack
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "libgl1", "libglib2.0-0", "wget")
    .pip_install(
        "torch==2.3.1",
        "torchvision==0.18.1",
        "torchaudio==2.3.1",
        index_url="https://download.pytorch.org/whl/cu121",
    )
    .pip_install(
        "comfy-cli",
        "httpx",
        "tqdm",
        "Pillow",
        "numpy",
        "aiohttp",
        "accelerate",
        "transformers",
        "safetensors",
        "einops",
        "kornia",
        "spandrel",
        "soundfile",
    )
    .run_commands(
        # Install latest ComfyUI — version 0.3.40 predates Flux.2 Klein nodes
        f"comfy --skip-prompt --workspace={COMFYUI_DIR} install --fast-deps --nvidia",
        # ComfyUI-GGUF provides UnetLoaderGGUF, ReferenceLatent, Flux2Scheduler,
        # EmptyFlux2LatentImage — all required by the CCDB workflow
        f"git clone https://github.com/city96/ComfyUI-GGUF {COMFYUI_DIR}/custom_nodes/ComfyUI-GGUF",
        f"git clone https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes {COMFYUI_DIR}/custom_nodes/ComfyUI_Comfyroll_CustomNodes",
        f"pip install gguf",  # required by ComfyUI-GGUF
        # Clear the models dir so Modal can mount the volume there
        f"rm -rf {COMFYUI_DIR}/models",
    )
)

app = modal.App("ai-studio-comfyui", image=image)

# ---------------------------------------------------------------------------
# Model download helper (runs once into the volume)
# ---------------------------------------------------------------------------

MODELS = {
    # ComfyUI standard subdirs: unet/, text_encoders/, vae/
    # Workflow nodes reference these as "FLUX.2/<filename>" which ComfyUI
    # resolves relative to each type's root folder.
    "unet/FLUX.2/flux-2-klein-4b-Q8_0.gguf": (
        "https://huggingface.co/unsloth/FLUX.2-klein-4B-GGUF/resolve/main/"
        "flux-2-klein-4b-Q8_0.gguf"
    ),
    "text_encoders/FLUX.2/qwen_3_4b.safetensors": (
        "https://huggingface.co/Comfy-Org/flux2-klein-4B/resolve/main/"
        "split_files/text_encoders/qwen_3_4b.safetensors"
    ),
    "vae/flux2-vae.safetensors": (
        "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/"
        "split_files/vae/flux2-vae.safetensors"
    ),
}


@app.function(
    volumes={str(COMFYUI_DIR / "models"): model_volume},
    timeout=1800,  # 30 min — only needed on first run
    cpu=4,
)
def download_models() -> None:
    """Download all base models into the volume. Run once."""
    models_dir = COMFYUI_DIR / "models"
    for rel_path, url in MODELS.items():
        dest = models_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            print(f"  skip (exists): {rel_path}")
            continue
        print(f"  downloading: {rel_path}")
        urllib.request.urlretrieve(url, str(dest))
        print(f"  done: {dest.stat().st_size / 1e6:.0f} MB")
    model_volume.commit()
    print("All models cached.")


@app.function(
    volumes={str(COMFYUI_DIR / "models"): model_volume},
    timeout=60,
)
def upload_lora(lora_name: str, data: bytes) -> None:
    """Upload a LoRA .safetensors file into the model volume."""
    dest = COMFYUI_DIR / "models" / "loras" / lora_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    model_volume.commit()
    print(f"Uploaded LoRA: {lora_name} ({len(data) / 1e6:.1f} MB)")


# ---------------------------------------------------------------------------
# ComfyUI server
# ---------------------------------------------------------------------------

COMFYUI_HOST = "127.0.0.1"
COMFYUI_PORT = 8188


def _start_comfyui() -> None:
    subprocess.Popen(
        [
            "python",
            str(COMFYUI_DIR / "main.py"),
            "--listen",
            COMFYUI_HOST,
            "--port",
            str(COMFYUI_PORT),
            "--disable-auto-launch",
            "--disable-metadata",
        ],
        cwd=str(COMFYUI_DIR),
    )
    # Wait until the server is accepting connections
    base = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{base}/system_stats", timeout=2)
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError("ComfyUI did not start in time")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_image_to_comfyui(base_url: str, filename: str, data: bytes) -> None:
    """Upload an image to ComfyUI's input folder via the /upload/image endpoint."""
    import urllib.request as _req

    boundary = "comfyupload"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = _req.Request(
        f"{base_url}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    _req.urlopen(req)


# ---------------------------------------------------------------------------
# Main inference endpoint
# ---------------------------------------------------------------------------

@app.cls(
    gpu="L4",
    volumes={str(COMFYUI_DIR / "models"): model_volume},
    timeout=600,
    # Keep 1 container warm for 5 min to amortise cold starts across a batch
    scaledown_window=300,
)
class ComfyUIRunner:
    @modal.enter()
    def start(self) -> None:
        _start_comfyui()
        self._base = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"

    @modal.method()
    def run_workflow(
        self,
        workflow: dict[str, Any],
        output_node_ids: list[str] | None = None,
        input_images: dict[str, bytes] | None = None,
    ) -> list[bytes]:
        """Submit a ComfyUI API-format workflow and return output images as bytes.

        Args:
            workflow: ComfyUI API-format dict (the JSON you'd POST to /prompt).
            output_node_ids: node IDs whose outputs to collect. If None, collects
                             all nodes whose class_type is 'SaveImage' or 'PreviewImage'.
            input_images: mapping of filename → bytes to upload before running (for LoadImage nodes).
        """
        import json as _json
        import urllib.request as _req

        if input_images:
            for filename, data in input_images.items():
                _upload_image_to_comfyui(self._base, filename, data)

        client_id = "modal-runner"
        payload = _json.dumps({"prompt": workflow, "client_id": client_id}).encode()

        # Submit
        req = _req.Request(
            f"{self._base}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            resp = _req.urlopen(req)
        except Exception as e:
            import urllib.error as _err
            if isinstance(e, _err.HTTPError):
                body = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"ComfyUI /prompt rejected workflow (HTTP {e.code}): {body}") from None
            raise
        prompt_id = _json.loads(resp.read())["prompt_id"]

        # Poll until done
        for _ in range(300):  # up to 10 min
            time.sleep(2)
            history_resp = _req.urlopen(f"{self._base}/history/{prompt_id}")
            history = _json.loads(history_resp.read())
            if prompt_id in history:
                break
        else:
            raise TimeoutError(f"Prompt {prompt_id} did not complete in time")

        # Collect images
        outputs = history[prompt_id]["outputs"]
        images: list[bytes] = []

        if output_node_ids is None:
            output_node_ids = [
                k
                for k, v in workflow.items()
                if v.get("class_type") in ("SaveImage", "PreviewImage")
            ]

        for node_id in output_node_ids:
            for img_meta in outputs.get(node_id, {}).get("images", []):
                params = f"filename={img_meta['filename']}&subfolder={img_meta.get('subfolder','')}&type={img_meta['type']}"
                img_resp = _req.urlopen(f"{self._base}/view?{params}")
                images.append(img_resp.read())

        return images


# ---------------------------------------------------------------------------
# Dev smoke test
# ---------------------------------------------------------------------------

@app.function()
def test_ping() -> str:
    runner = ComfyUIRunner()
    runner.start.remote()
    return "ComfyUI started OK"
