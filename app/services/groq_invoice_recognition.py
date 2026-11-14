"""Groq Qwen vision and extraction for invoice files."""
import base64
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx
from fastapi import HTTPException

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_PAGES = 20


def _chat(messages, *, json_mode=False):
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured")
    payload = {"model": os.getenv("GROQ_INVOICE_MODEL", "qwen/qwen3.8-27b"),
               "messages": messages, "temperature": 0, "max_completion_tokens": 8192}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        response = httpx.post(GROQ_URL, headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=120)
        if response.status_code == 429:
            raise HTTPException(status_code=503, detail="Groq: превышен лимит запросов, повторите позже")
        if response.status_code in (401, 403):
            raise HTTPException(status_code=502, detail="Groq: ключ недействителен или у него нет доступа к модели")
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty model response")
        return content
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Не удалось получить результат от Groq") from exc


def _image_url(data, mime):
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Изображение превышает 4 МиБ")
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def _pages(file_path, content):
    suffix = Path(file_path).suffix.lower()
    if suffix in (".jpg", ".jpeg", ".png", ".webp"):
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[suffix]
        yield _image_url(content, mime)
        return
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="Поддерживаются PDF, JPEG, PNG и WebP")
    if not shutil.which("pdfinfo") or not shutil.which("pdftoppm"):
        raise HTTPException(status_code=503, detail="Для PDF установите poppler-utils (pdfinfo и pdftoppm)")
    try:
        info = subprocess.run(["pdfinfo", file_path], capture_output=True, text=True, timeout=30, check=True)
        match = re.search(r"^Pages:\s*(\d+)", info.stdout, re.MULTILINE)
        if not match:
            raise ValueError("missing page count")
        pages = int(match.group(1))
        if pages < 1 or pages > MAX_PAGES:
            raise HTTPException(status_code=400, detail=f"PDF должен содержать от 1 до {MAX_PAGES} страниц")
        with tempfile.TemporaryDirectory(prefix="invoice-groq-") as directory:
            for page in range(1, pages + 1):
                prefix = str(Path(directory) / "page")
                subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-singlefile", "-r", "140", "-jpeg", file_path, prefix], capture_output=True, timeout=60, check=True)
                yield _image_url(Path(prefix + ".jpg").read_bytes(), "image/jpeg")
    except HTTPException:
        raise
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Не удалось обработать PDF") from exc


def recognize_invoice_text(file_path, content):
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Файл счёта превышает 15 МиБ")
    results = []
    for image in _pages(file_path, content):
        results.append(_chat([{"role": "user", "content": [
            {"type": "text", "text": "Transcribe every detail of this invoice page exactly as written. Preserve all table rows, numbers, prices, totals, VAT, dates, INN, bank details and line breaks. Do not guess. Output only the transcription."},
            {"type": "image_url", "image_url": {"url": image}},
        ]}]))
    return "\n\n".join(results)


def extract_invoice_json(prompt):
    return _chat([{"role": "user", "content": prompt}], json_mode=True)
