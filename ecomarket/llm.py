import json
import socket
import time
import urllib.error
import urllib.request

URL = "http://127.0.0.1:11434"
OPTIONS = {"temperature": 0.2, "seed": 42, "num_ctx": 8192, "num_predict": 1000}


def request_json(path, payload=None, timeout=180):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(URL + path, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Ollama respondió HTTP {exc.code}: {detail}. Comprueba 'ollama list'.") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise RuntimeError("Ollama no responde. Abre la aplicación o ejecuta 'ollama serve'; verifica el modelo instalado. La inferencia puede exceder el tiempo límite.") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("Ollama devolvió una respuesta HTTP no interpretable como JSON.") from exc


def model_identity(model):
    tags = request_json("/api/tags", timeout=10)
    record = next((m for m in tags.get("models", []) if m.get("name") == model or m.get("model") == model), None)
    if record is None:
        raise RuntimeError(f"Modelo no instalado: {model}. Ejecuta: ollama pull {model}")
    version = request_json("/api/version", timeout=10).get("version", "desconocida")
    return {"model": model, "digest": record.get("digest"), "ollama_version": version}


def generate(messages, model="qwen2.5:7b"):
    start = time.perf_counter()
    data = request_json("/api/generate", {"model": model, **messages, "stream": False,
                                           "format": "json", "options": OPTIONS})
    raw = data.get("response")
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError("El modelo devolvió una respuesta vacía. No se sustituye silenciosamente por una plantilla.")
    return {"raw_response": raw, "elapsed_seconds": round(time.perf_counter() - start, 4),
            "done_reason": data.get("done_reason"), "prompt_tokens": data.get("prompt_eval_count"),
            "output_tokens": data.get("eval_count")}
