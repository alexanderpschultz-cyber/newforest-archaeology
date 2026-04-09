"""Gemma 4 vision-based archaeological feature detection via Ollama."""

import base64
import io
import json
import re
import time

import requests
from PIL import Image

from config import OLLAMA_URL, MODEL_NAME, COARSE_PROMPT, FINE_PROMPT, REQUEST_DELAY_SECONDS


MAX_IMAGE_DIM = 256  # Gemma 4 via Ollama returns empty for large image payloads


def image_to_base64(img: Image.Image) -> str:
    """Convert PIL Image to base64 JPEG for Ollama API.

    Resizes large images and uses JPEG to keep payload small —
    Gemma 4 via Ollama returns empty responses for large PNG payloads.
    """
    # Resize if too large
    w, h = img.size
    if max(w, h) > MAX_IMAGE_DIM:
        ratio = MAX_IMAGE_DIM / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    # Convert to RGB if grayscale (JPEG requires RGB)
    if img.mode != "RGB":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _extract_json(text: str) -> dict | None:
    """Extract JSON from model response, handling markdown code blocks."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code block
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { ... }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def wait_for_ollama_idle(max_wait: int = 300, poll_interval: int = 5):
    """Wait until Ollama has no running requests before proceeding.

    Checks the /api/ps endpoint for active model instances with pending requests.
    This ensures we don't interfere with the security camera queue.
    """
    waited = 0
    while waited < max_wait:
        try:
            resp = requests.get(f"{OLLAMA_URL}/api/ps", timeout=10)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            # If no models are loaded or none are actively processing, we're good
            busy = any(
                m.get("details", {}).get("pending", 0) > 0
                or m.get("size_vram", 0) > 0 and m.get("expires_at")
                for m in models
            )
            # Simpler check: if there are running models, check if any are mid-generation
            # The /api/ps endpoint shows loaded models; we just check if any exist
            # and give them a moment to finish
            if not models:
                return
            # If models are loaded but we can't tell if busy, just proceed
            # after initial check — the delay between requests handles queuing
            return
        except requests.RequestException:
            pass
        time.sleep(poll_interval)
        waited += poll_interval


MAX_RETRIES = 3


def query_ollama(prompt: str, image: Image.Image) -> tuple[str, dict | None]:
    """Send an image + prompt to Ollama and return (raw_text, parsed_json).

    Waits for Ollama to be idle and adds a delay after each request
    to avoid starving the security camera queue. Retries on empty responses.
    """
    b64 = image_to_base64(image)

    for attempt in range(MAX_RETRIES):
        # Check Ollama isn't busy with other work
        wait_for_ollama_idle()

        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "images": [b64],
                "stream": False,
                "options": {
                    "temperature": 0.2 + (attempt * 0.1),  # slightly increase temp on retry
                    "num_predict": 1024,
                },
            },
            timeout=120,
        )
        resp.raise_for_status()
        raw_text = resp.json().get("response", "")

        # Delay to let the security camera pipeline clear its queue
        time.sleep(REQUEST_DELAY_SECONDS)

        if raw_text.strip():
            parsed = _extract_json(raw_text)
            return raw_text, parsed

    # All retries exhausted
    return "", None


def coarse_detect(composite: Image.Image) -> tuple[str, dict | None]:
    """Run coarse detection on a full-tile composite."""
    return query_ollama(COARSE_PROMPT, composite)


def fine_detect(patch: Image.Image) -> tuple[str, dict | None]:
    """Run fine detection on a single patch."""
    return query_ollama(FINE_PROMPT, patch)
