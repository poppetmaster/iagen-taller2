"""Configuración explícita del experimento; las rutas no dependen de la consola."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def settings():
    result = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    result["ollama_url"] = os.environ.get("OLLAMA_BASE_URL", result["ollama_url"])
    result["model"] = os.environ.get("ECOMARKET_MODEL", result["model"])
    result["index_dir"] = str(Path(os.environ.get("ECOMARKET_INDEX_DIR", ROOT / ".index")).resolve())
    return result
