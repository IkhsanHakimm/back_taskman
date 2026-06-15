"""
mistral_service.py
------------------
Service untuk memanggil Mistral AI API dan menghasilkan
AI Breakdown dari sebuah task (judul + deskripsi).

Output JSON harus sesuai dengan struktur AIBreakdown di Flutter:
{
  "summary": str,
  "estimasiTotal": str,
  "tingkatKesulitan": str,         // "Rendah" | "Sedang" | "Tinggi"
  "steps": [
    { "title": str, "description": str, "estimasi": str, "iconName": str }
  ],
  "tips": [str],
  "resources": [str]
}
"""

import json
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

# iconName yang valid sesuai Icons.* di Flutter yang sudah dipakai
_VALID_ICONS = [
    "architecture", "settings", "storage", "api", "bug_report",
    "design_services", "folder_open", "widgets", "smartphone", "rocket_launch",
    "menu_book", "list_alt", "edit_note", "bar_chart", "spellcheck",
    "analytics", "palette", "phone_android", "build", "smart_toy",
    "lightbulb_outline", "checklist", "play_circle_outline", "check_circle_outline",
    "task_alt", "school", "code", "data_object", "layers", "bolt",
    "calendar_today", "groups", "library_books", "science", "terminal",
]

_SYSTEM_PROMPT = """
Kamu adalah AI asisten akademik yang membantu mahasiswa memecah tugas kuliah menjadi langkah-langkah yang terstruktur.

Tugasmu: Buat rencana pengerjaan tugas secara detail dan praktis.

ATURAN KETAT:
1. Balas HANYA dengan JSON valid, tanpa penjelasan tambahan, tanpa markdown code block, tanpa awalan/akhiran teks apapun.
2. Struktur JSON HARUS persis seperti berikut:
{
  "summary": "Penjelasan singkat tentang scope dan tantangan utama task ini (2-3 kalimat)",
  "estimasiTotal": "X–Y jam",
  "tingkatKesulitan": "Rendah",
  "steps": [
    {
      "title": "Judul langkah singkat",
      "description": "Penjelasan detail apa yang harus dilakukan pada langkah ini",
      "estimasi": "X–Y menit",
      "iconName": "nama_icon"
    }
  ],
  "tips": ["tip 1", "tip 2", "tip 3"],
  "resources": ["Sumber belajar 1", "Sumber belajar 2"]
}
3. tingkatKesulitan hanya boleh: "Rendah", "Sedang", atau "Tinggi"
4. iconName harus salah satu dari: architecture, settings, storage, api, bug_report, design_services, folder_open, widgets, smartphone, rocket_launch, menu_book, list_alt, edit_note, bar_chart, spellcheck, analytics, palette, phone_android, build, smart_toy, lightbulb_outline, checklist, play_circle_outline, check_circle_outline, task_alt, school, code, data_object, layers, bolt, calendar_today, groups, library_books, science, terminal
5. steps harus antara 3 hingga 6 langkah
6. Gunakan Bahasa Indonesia
""".strip()


def generate_task_breakdown(task_title: str, task_description: str | None = None) -> dict:
    """
    Panggil Mistral API untuk menghasilkan AI Breakdown dari sebuah task.

    Args:
        task_title: Judul task.
        task_description: Deskripsi opsional task.

    Returns:
        Dict dengan struktur AIBreakdown yang siap disimpan ke MongoDB dan
        dikembalikan ke Flutter frontend.

    Raises:
        RuntimeError: Jika API call gagal atau response JSON tidak valid.
    """
    if not MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY tidak ditemukan di environment variables")

    user_content = f"Tugas: {task_title}"
    if task_description:
        user_content += f"\nDeskripsi: {task_description}"

    payload = {
        "model": MISTRAL_MODEL,
        "temperature": 0.3,       # lebih deterministik agar JSON konsisten
        "max_tokens": 1500,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            MISTRAL_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError("Request ke Mistral API timeout (>30 detik)")
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Gagal terhubung ke Mistral API: {exc}")

    raw_text = response.json()["choices"][0]["message"]["content"].strip()

    # Bersihkan jika Mistral masih membungkus dengan ```json ... ```
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)

    try:
        breakdown = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Gagal parse JSON dari Mistral: %s\nRaw: %s", exc, raw_text)
        raise RuntimeError(f"Mistral mengembalikan respons yang bukan JSON valid: {exc}")

    breakdown = _validate_and_sanitize(breakdown, task_title)
    return breakdown


def _validate_and_sanitize(data: dict, task_title: str) -> dict:
    """
    Validasi dan sanitasi struktur JSON dari Mistral agar aman disimpan dan dikembalikan.
    Jika ada field yang hilang, isi dengan nilai default yang masuk akal.
    """
    # Field utama
    if not isinstance(data.get("summary"), str) or not data["summary"]:
        data["summary"] = f'Breakdown AI untuk task "{task_title}".'

    if not isinstance(data.get("estimasiTotal"), str) or not data["estimasiTotal"]:
        data["estimasiTotal"] = "1–3 jam"

    if data.get("tingkatKesulitan") not in ("Rendah", "Sedang", "Tinggi"):
        data["tingkatKesulitan"] = "Sedang"

    # Steps
    if not isinstance(data.get("steps"), list) or len(data["steps"]) == 0:
        data["steps"] = [
            {
                "title": "Perencanaan",
                "description": "Pahami scope dan rencanakan pengerjaan task.",
                "estimasi": "15–30 menit",
                "iconName": "lightbulb_outline",
            },
            {
                "title": "Eksekusi",
                "description": "Kerjakan task sesuai rencana secara bertahap.",
                "estimasi": "Proporsi terbesar",
                "iconName": "play_circle_outline",
            },
            {
                "title": "Review",
                "description": "Cek dan finalisasi hasil pekerjaan.",
                "estimasi": "15–30 menit",
                "iconName": "check_circle_outline",
            },
        ]
    else:
        sanitized_steps = []
        for step in data["steps"]:
            sanitized_steps.append({
                "title": step.get("title", "Langkah"),
                "description": step.get("description", ""),
                "estimasi": step.get("estimasi", ""),
                "iconName": step.get("iconName", "task_alt") if step.get("iconName") in _VALID_ICONS else "task_alt",
            })
        data["steps"] = sanitized_steps

    # Tips & resources
    if not isinstance(data.get("tips"), list):
        data["tips"] = []
    if not isinstance(data.get("resources"), list):
        data["resources"] = []

    return data
