#!/usr/bin/env python3
"""
historical_shorts.py — Generate and distribute historical drama shorts.

Pipeline:
  1. Pick a seed (random "on this day" or --seed "Topic")
  2. Traverse Wikipedia link graph; score neighbors by semantic similarity
     to build a coherent storyline (3-5 hops)
  3. Write a 45-60s dramatic narration via Claude API
  4. Pull illustrative images from Wikimedia Commons
  5. Synthesize voiceover, build 1080x1920 vertical video with ffmpeg
  6. Upload to YouTube / Instagram / Facebook / TikTok

Run:
  python historical_shorts.py --seed "Battle of Hastings"
  python historical_shorts.py --random
  python historical_shorts.py --seed "Rasputin" --no-upload
  python historical_shorts.py --seed "Pompeii" --platforms youtube,tiktok

Required:
  pip install -r requirements.txt
  ffmpeg installed and on PATH

Env vars (see .env.example):
  ANTHROPIC_API_KEY
  YOUTUBE_CLIENT_SECRETS, YOUTUBE_TOKEN_FILE
  META_ACCESS_TOKEN, META_PAGE_ID, IG_USER_ID, IG_PUBLIC_VIDEO_HOST
  TIKTOK_ACCESS_TOKEN
  ELEVENLABS_API_KEY (optional; falls back to pyttsx3)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.parse
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("shorts")

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_REST = "https://en.wikipedia.org/api/rest_v1"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "HistoricalShortsBot/0.1 (https://github.com/ar7emiy/historicalcontentgenerator)"

OUT_DIR = Path("output")
OUT_DIR.mkdir(exist_ok=True)


# ---------- 1. Wikipedia semantic-graph traversal ----------

@dataclass
class StoryNode:
    title: str
    summary: str
    url: str
    image: str | None = None


@dataclass
class Storyline:
    seed: str
    nodes: list[StoryNode] = field(default_factory=list)


def wiki_get(params: dict[str, Any], api: str = WIKI_API) -> dict:
    params = {"format": "json", **params}
    r = requests.get(api, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    return r.json()


def wiki_summary(title: str) -> StoryNode | None:
    try:
        url = f"{WIKI_REST}/page/summary/{urllib.parse.quote(title.replace(' ', '_'))}"
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        if r.status_code != 200:
            return None
        d = r.json()
        if d.get("type") == "disambiguation":
            return None
        return StoryNode(
            title=d.get("title", title),
            summary=d.get("extract", "") or "",
            url=d.get("content_urls", {}).get("desktop", {}).get("page", ""),
            image=(d.get("originalimage") or d.get("thumbnail") or {}).get("source"),
        )
    except Exception as e:
        log.warning("summary failed for %s: %s", title, e)
        return None


def wiki_links(title: str, limit: int = 50) -> list[str]:
    data = wiki_get({
        "action": "query",
        "titles": title,
        "prop": "links",
        "pllimit": limit,
        "plnamespace": 0,
    })
    pages = data.get("query", {}).get("pages", {})
    out = []
    for p in pages.values():
        for link in p.get("links", []) or []:
            t = link.get("title", "")
            if not t or ":" in t:
                continue
            if re.match(r"^(List of|ISBN|Index of)\b", t):
                continue
            out.append(t)
    return out


def random_historical_seed() -> str:
    today = dt.date.today()
    url = f"{WIKI_REST}/feed/onthisday/events/{today.month:02d}/{today.day:02d}"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        r.raise_for_status()
        events = r.json().get("events", [])
        if events:
            ev = random.choice(events[: min(20, len(events))])
            pages = ev.get("pages", [])
            if pages:
                return pages[0]["title"]
    except Exception as e:
        log.warning("on-this-day failed: %s", e)
    return random.choice([
        "Boudica", "Battle of Thermopylae", "Rasputin",
        "Eruption of Mount Vesuvius in 79 AD", "Hatshepsut",
        "Defenestrations of Prague", "Mansa Musa", "Tsar Bomba",
    ])


class SemanticScorer:
    """Embeds short texts; falls back to TF-IDF if sentence-transformers absent."""

    def __init__(self) -> None:
        self.mode = "tfidf"
        self.model = None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            self.mode = "st"
            log.info("semantic scorer: sentence-transformers")
        except Exception:
            log.info("semantic scorer: TF-IDF fallback")

    def score(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        if self.mode == "st":
            import numpy as np
            qv = self.model.encode([query], normalize_embeddings=True)
            cv = self.model.encode(candidates, normalize_embeddings=True)
            return (qv @ cv.T)[0].tolist()
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vec = TfidfVectorizer(stop_words="english").fit([query] + candidates)
        m = vec.transform([query] + candidates)
        return cosine_similarity(m[0:1], m[1:])[0].tolist()


def traverse(seed: str, hops: int = 4, fanout: int = 25) -> Storyline:
    log.info("traversing from seed: %s", seed)
    scorer = SemanticScorer()
    story = Storyline(seed=seed)
    visited: set[str] = set()
    cur = wiki_summary(seed)
    if not cur:
        raise RuntimeError(f"could not fetch seed page: {seed}")
    story.nodes.append(cur)
    visited.add(cur.title.lower())
    theme = (cur.summary or seed)[:600]

    for hop in range(hops):
        candidates = wiki_links(cur.title, limit=80)
        candidates = [c for c in candidates if c.lower() not in visited][:fanout]
        if not candidates:
            break
        scored = scorer.score(theme + " " + cur.summary[:300], candidates)
        ranked = sorted(zip(candidates, scored), key=lambda x: x[1], reverse=True)
        next_node = None
        for cand, _ in ranked[:8]:
            n = wiki_summary(cand)
            if n and len(n.summary) > 120:
                next_node = n
                break
        if not next_node:
            break
        story.nodes.append(next_node)
        visited.add(next_node.title.lower())
        log.info("  hop %d: %s", hop + 1, next_node.title)
        cur = next_node
    return story


# ---------- 2. Dramatic script via Claude ----------

@dataclass
class Script:
    title: str
    hook: str
    narration: str           # full voiceover text
    captions: list[str]      # short on-screen lines (one per scene)
    hashtags: list[str]
    description: str


def write_script(story: Storyline) -> Script:
    try:
        import anthropic
    except ImportError:
        raise SystemExit("Install anthropic: pip install anthropic")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic()
    storyline_text = "\n\n".join(
        f"[{i+1}] {n.title}\n{n.summary}" for i, n in enumerate(story.nodes)
    )
    sys_prompt = (
        "You are a viral short-form video writer specializing in tight, "
        "cinematic historical drama. Voice: urgent, vivid, present-tense, "
        "mid-sentence hooks, punchy 6-12 word lines. Strictly factual. "
        "No invented quotes from real people."
    )
    user_prompt = f"""Write a 45-60 second vertical video script from this Wikipedia storyline.

STORYLINE NODES:
{storyline_text}

Return STRICT JSON:
{{
  "title": "<<70 chars, dramatic>",
  "hook": "first 1 sentence, must stop the scroll",
  "narration": "full voiceover, ~140 words, plain prose, no stage directions",
  "captions": ["6-10 short on-screen text lines covering the narration in order"],
  "hashtags": ["#history", "#shorts", ...8-12 tags],
  "description": "2-3 sentence YouTube/Meta description, ends with source: en.wikipedia.org"
}}
"""
    log.info("writing script with Claude (claude-sonnet-4-6)")
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=sys_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    data = json.loads(raw)
    return Script(**data)


# ---------- 3. Media fetch ----------

def fetch_images(story: Storyline, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, node in enumerate(story.nodes):
        if not node.image:
            continue
        try:
            r = requests.get(node.image, headers={"User-Agent": USER_AGENT}, timeout=30)
            r.raise_for_status()
            ext = ".jpg" if "jpeg" in r.headers.get("content-type", "") else ".png"
            p = dest / f"img_{i:02d}{ext}"
            p.write_bytes(r.content)
            paths.append(p)
            log.info("  image: %s", node.title)
        except Exception as e:
            log.warning("image fetch failed for %s: %s", node.title, e)
    return paths


# ---------- 4. TTS ----------

def synth_voice(text: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get("ELEVENLABS_API_KEY"):
        try:
            voice = os.environ.get("ELEVENLABS_VOICE_ID", "ErXwobaYiN019PkySvjV")
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                headers={
                    "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
                    "accept": "audio/mpeg",
                    "content-type": "application/json",
                },
                json={"text": text, "model_id": "eleven_turbo_v2_5"},
                timeout=120,
            )
            r.raise_for_status()
            dest.write_bytes(r.content)
            log.info("voiceover: ElevenLabs (%d bytes)", len(r.content))
            return dest
        except Exception as e:
            log.warning("ElevenLabs failed, falling back: %s", e)
    try:
        import pyttsx3  # type: ignore
        wav = dest.with_suffix(".wav")
        eng = pyttsx3.init()
        eng.setProperty("rate", 185)
        eng.save_to_file(text, str(wav))
        eng.runAndWait()
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav), "-codec:a", "libmp3lame", "-qscale:a", "2", str(dest)],
            check=True, capture_output=True,
        )
        wav.unlink(missing_ok=True)
        log.info("voiceover: pyttsx3 offline")
        return dest
    except Exception as e:
        raise SystemExit(f"TTS failed (install pyttsx3 or set ELEVENLABS_API_KEY): {e}")


def audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


# ---------- 5. Vertical video assembly ----------

def build_video(images: list[Path], audio: Path, captions: list[str], dest: Path) -> Path:
    if not images:
        raise SystemExit("no images available for video assembly")
    dur = audio_duration(audio)
    n = len(images)
    per = max(2.0, dur / n)
    work = dest.parent / "scenes"
    work.mkdir(exist_ok=True, parents=True)
    scene_files: list[Path] = []

    for i, img in enumerate(images):
        cap = captions[i] if i < len(captions) else ""
        cap_safe = cap.replace("'", "\u2019").replace(":", " ")
        scene = work / f"scene_{i:02d}.mp4"
        zoom = "zoompan=z='min(zoom+0.0008,1.25)':d=125*{d}:s=1080x1920:fps=25".format(d=int(per * 25 / 125 + 1))
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            f"{zoom},"
            "drawbox=y=ih-360:x=0:w=iw:h=360:color=black@0.55:t=fill,"
            f"drawtext=text='{cap_safe}':fontcolor=white:fontsize=58:"
            "x=(w-text_w)/2:y=h-260:line_spacing=10:box=0"
        )
        subprocess.run(
            ["ffmpeg", "-y", "-loop", "1", "-i", str(img),
             "-t", f"{per:.2f}", "-vf", vf,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25", str(scene)],
            check=True, capture_output=True,
        )
        scene_files.append(scene)

    concat_list = work / "concat.txt"
    concat_list.write_text("\n".join(f"file '{s.resolve()}'" for s in scene_files))
    silent = work / "silent.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(silent)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(silent), "-i", str(audio),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(dest)],
        check=True, capture_output=True,
    )
    log.info("video built: %s (%.1fs)", dest, dur)
    return dest


# ---------- 6. Distribution ----------

def upload_youtube(video: Path, script: Script) -> str | None:
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        log.warning("YouTube: install google-api-python-client google-auth-oauthlib")
        return None
    secrets = os.environ.get("YOUTUBE_CLIENT_SECRETS", "client_secrets.json")
    token_file = Path(os.environ.get("YOUTUBE_TOKEN_FILE", "youtube_token.json"))
    if not Path(secrets).exists():
        log.warning("YouTube: %s missing, skipping", secrets)
        return None
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(secrets, scopes)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json())
    yt = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": script.title[:95],
            "description": f"{script.description}\n\n{' '.join(script.hashtags)}",
            "tags": [t.lstrip("#") for t in script.hashtags],
            "categoryId": "27",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video), chunksize=-1, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = req.execute()
    vid = resp.get("id")
    log.info("YouTube uploaded: https://youtu.be/%s", vid)
    return vid


def upload_meta(video: Path, script: Script, target: str) -> str | None:
    """target: 'facebook' or 'instagram'"""
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        log.warning("Meta: META_ACCESS_TOKEN not set, skipping %s", target)
        return None
    caption = f"{script.hook}\n\n{script.description}\n\n{' '.join(script.hashtags)}"
    if target == "facebook":
        page_id = os.environ.get("META_PAGE_ID")
        if not page_id:
            log.warning("FB: META_PAGE_ID not set"); return None
        with open(video, "rb") as f:
            r = requests.post(
                f"https://graph-video.facebook.com/v19.0/{page_id}/videos",
                params={"access_token": token, "description": caption,
                        "title": script.title[:95]},
                files={"source": f}, timeout=600,
            )
        r.raise_for_status()
        vid = r.json().get("id")
        log.info("Facebook posted: id=%s", vid)
        return vid
    # Instagram Reels: needs publicly hosted MP4 URL
    ig_user = os.environ.get("IG_USER_ID")
    public_url = os.environ.get("IG_PUBLIC_VIDEO_URL")
    if not (ig_user and public_url):
        log.warning("IG: set IG_USER_ID and IG_PUBLIC_VIDEO_URL (host the mp4 first)")
        return None
    create = requests.post(
        f"https://graph.facebook.com/v19.0/{ig_user}/media",
        params={"access_token": token, "media_type": "REELS",
                "video_url": public_url, "caption": caption},
        timeout=120,
    ).json()
    container = create.get("id")
    if not container:
        log.warning("IG container failed: %s", create); return None
    for _ in range(30):
        time.sleep(5)
        st = requests.get(
            f"https://graph.facebook.com/v19.0/{container}",
            params={"access_token": token, "fields": "status_code"},
            timeout=30,
        ).json()
        if st.get("status_code") == "FINISHED":
            break
    pub = requests.post(
        f"https://graph.facebook.com/v19.0/{ig_user}/media_publish",
        params={"access_token": token, "creation_id": container},
        timeout=60,
    ).json()
    log.info("Instagram posted: %s", pub)
    return pub.get("id")


def upload_tiktok(video: Path, script: Script) -> str | None:
    token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if not token:
        log.warning("TikTok: TIKTOK_ACCESS_TOKEN not set, skipping")
        return None
    size = video.stat().st_size
    init = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json={
            "post_info": {
                "title": f"{script.hook} {' '.join(script.hashtags[:5])}"[:2200],
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_comment": False,
                "disable_duet": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            },
        },
        timeout=60,
    ).json()
    upload_url = init.get("data", {}).get("upload_url")
    publish_id = init.get("data", {}).get("publish_id")
    if not upload_url:
        log.warning("TikTok init failed: %s", init); return None
    with open(video, "rb") as f:
        put = requests.put(
            upload_url,
            headers={"Content-Range": f"bytes 0-{size-1}/{size}",
                     "Content-Type": "video/mp4"},
            data=f.read(), timeout=600,
        )
    put.raise_for_status()
    log.info("TikTok uploaded: publish_id=%s", publish_id)
    return publish_id


def distribute(video: Path, script: Script, platforms: list[str]) -> dict[str, str | None]:
    results: dict[str, str | None] = {}
    if "youtube" in platforms:
        try: results["youtube"] = upload_youtube(video, script)
        except Exception as e: log.warning("YouTube upload failed: %s", e); results["youtube"] = None
    if "facebook" in platforms:
        try: results["facebook"] = upload_meta(video, script, "facebook")
        except Exception as e: log.warning("Facebook upload failed: %s", e); results["facebook"] = None
    if "instagram" in platforms:
        try: results["instagram"] = upload_meta(video, script, "instagram")
        except Exception as e: log.warning("Instagram upload failed: %s", e); results["instagram"] = None
    if "tiktok" in platforms:
        try: results["tiktok"] = upload_tiktok(video, script)
        except Exception as e: log.warning("TikTok upload failed: %s", e); results["tiktok"] = None
    return results


# ---------- CLI ----------

def slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()[:60]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", help="Wikipedia article title to start from")
    ap.add_argument("--random", action="store_true", help="Pick from today's 'on this day' events")
    ap.add_argument("--hops", type=int, default=4, help="Storyline hops (default 4)")
    ap.add_argument("--no-upload", action="store_true", help="Build only; skip distribution")
    ap.add_argument("--platforms", default="youtube,instagram,facebook,tiktok",
                    help="Comma-separated subset")
    ap.add_argument("--out", type=Path, default=OUT_DIR, help="Output directory root")
    args = ap.parse_args()

    if not args.seed and not args.random:
        ap.error("provide --seed or --random")
    if not shutil.which("ffmpeg"):
        ap.error("ffmpeg not found on PATH")

    seed = args.seed or random_historical_seed()
    log.info("=== HISTORICAL DRAMA SHORT ===")
    log.info("seed: %s", seed)

    story = traverse(seed, hops=args.hops)
    if len(story.nodes) < 2:
        log.error("storyline too thin (%d nodes); try a different seed", len(story.nodes))
        return 1

    job = args.out / f"{dt.datetime.now():%Y%m%d_%H%M%S}_{slug(seed)}"
    job.mkdir(parents=True, exist_ok=True)
    (job / "storyline.json").write_text(json.dumps(asdict(story), indent=2))

    script = write_script(story)
    (job / "script.json").write_text(json.dumps(asdict(script), indent=2))
    log.info("title: %s", script.title)

    images = fetch_images(story, job / "images")
    if len(images) < 2:
        log.warning("only %d images; video will be sparse", len(images))

    audio = synth_voice(script.narration, job / "voice.mp3")
    video = build_video(images, audio, script.captions, job / "short.mp4")

    if args.no_upload:
        log.info("skipping uploads (--no-upload). video at %s", video)
        return 0

    platforms = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]
    results = distribute(video, script, platforms)
    (job / "uploads.json").write_text(json.dumps(results, indent=2))
    log.info("done. uploads: %s", results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
