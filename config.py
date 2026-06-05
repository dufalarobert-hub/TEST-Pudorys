"""
Konfigurácia + načítanie Gemini API kľúča.

Kľúč (poradie):
  1) env GEMINI_API_KEY  (PRODUKCIA — nastav na Verceli)
  2) súbor ~/.cihlomat_gemini_key  (lokálny dev)
  3) fallback: ~/nanobanana/*.py  (lokálny dev pohodlie)

Upload adresár: /tmp (na Verceli je len /tmp zapisovateľný; lokálne tiež OK).
"""
import os
import re
import glob
import tempfile
from pathlib import Path

HOME = Path.home()
BASE_DIR = Path(__file__).resolve().parent

# Model pre víziu. 3.5-flash + thinking_budget 512 = ~13s a presné čítanie kót
# (3.1-pro-preview bol presný ale ~90s = nepoužiteľné na web). Fallback 2.5-pro.
GEMINI_VISION_MODEL = os.environ.get("GEMINI_VISION_MODEL", "models/gemini-3.5-flash")
GEMINI_VISION_FALLBACK = "models/gemini-2.5-pro"
GEMINI_THINKING_BUDGET = int(os.environ.get("GEMINI_THINKING_BUDGET", "512"))

# Zapisovateľný adresár pre dočasné uploady (Vercel: len /tmp; lokálne: temp).
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR") or (Path(tempfile.gettempdir()) / "cihlomat_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_gemini_key() -> str:
    # 1) env (produkcia)
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key.strip()

    # 2) lokálny key súbor
    key_file = HOME / ".cihlomat_gemini_key"
    if key_file.exists():
        return key_file.read_text().strip()

    # 3) fallback – lokálny nanobanana skript (len dev pohodlie)
    for f in glob.glob(str(HOME / "nanobanana" / "*.py")):
        try:
            m = re.search(r"AIza[A-Za-z0-9_\-]{20,}", open(f, encoding="utf-8").read())
            if m:
                return m.group(0)
        except Exception:
            continue

    raise RuntimeError(
        "Chýba GEMINI_API_KEY. Na Verceli nastav environment variable GEMINI_API_KEY, "
        "lokálne `export GEMINI_API_KEY=...` alebo ulož do ~/.cihlomat_gemini_key"
    )
