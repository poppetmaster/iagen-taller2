"""Guarda resultados reales, sin sustituir inferencias fallidas por respuestas inventadas."""
import argparse
import csv
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from ecomarket.domain import build_context, load_json
from ecomarket.prompts import build_prompt
from ecomarket.llm import generate, model_identity, OPTIONS
from ecomarket.validation import validate_response


def main(argv=None):
    parser = argparse.ArgumentParser(description="Comparar prompts básicos y mejorados con el mismo contexto")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--case", action="append", help="ID de caso; se puede repetir. Omitir para los 15 casos.")
    parser.add_argument("--variant", choices=["baseline", "improved", "both"], default="both")
    parser.add_argument("--output", default="evaluacion/runs")
    args = parser.parse_args(argv)
    cases = load_json("evaluation_cases.json")
    if args.case:
        unknown = set(args.case) - {c["id"] for c in cases}
        if unknown:
            parser.error("Casos desconocidos: " + ", ".join(sorted(unknown)))
        cases = [c for c in cases if c["id"] in args.case]
    # Verificar los oráculos humanos antes de iniciar una inferencia.
    for case in cases:
        ctx = build_context(case["task"], case["tracking"], **case.get("inputs", {}))
        if any(ctx["verified_facts"].get(k) != v for k, v in case["expected"].items()):
            raise RuntimeError("El motor no coincide con el resultado esperado del caso " + case["id"])
    try:
        identity = model_identity(args.model)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = Path(args.output) / stamp
    folder.mkdir(parents=True, exist_ok=False)
    meta = {**identity, "options": OPTIONS, "started_at_utc": stamp,
            "python": platform.python_version(), "platform": platform.platform(),
            "context_scope": "all", "cases": [c["id"] for c in cases],
            "note": "Comprobaciones automáticas parciales; texto libre pendiente de revisión humana."}
    (folder / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    variants = ["baseline", "improved"] if args.variant == "both" else [args.variant]
    records = []
    # Se alterna el orden para reducir el efecto de ejecutar siempre el básico primero.
    with (folder / "results.jsonl").open("w", encoding="utf-8") as handle:
        for index, case in enumerate(cases):
            context = build_context(case["task"], case["tracking"], **case.get("inputs", {}))
            for variant in (variants if index % 2 == 0 else list(reversed(variants))):
                messages = build_prompt(context, variant, case.get("question"))
                record = {"case_id": case["id"], "variant": variant, "task": case["task"],
                          "expected": case["expected"], "context": context, "messages": messages}
                try:
                    generated = generate(messages, args.model)
                    validation = validate_response(generated["raw_response"], context)
                    record.update(generated, validation=validation, inference_completed=True)
                except RuntimeError as exc:
                    record.update(inference_completed=False, error=str(exc),
                                  validation={"checks_passed": False, "errors": ["inferencia_fallida"]})
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                records.append(record)
                print(f"{case['id']} / {variant}: {record['validation']['errors'] or 'comprobaciones automáticas superadas'}", flush=True)
    with (folder / "revision_humana.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "variant", "exactitud_0_1", "politica_0_1", "empatia_0_1", "sin_inventar_0_1", "escalamiento_0_1", "observaciones"])
        writer.writerows([[r["case_id"], r["variant"], "", "", "", "", "", ""] for r in records])
    lines = ["# Resultados de ejecución", "", f"Modelo: `{args.model}`. Digest: `{identity.get('digest')}`.",
             "", "Las cifras siguientes NO miden por sí solas la calidad semántica ni la ausencia de alucinaciones.",
             "", "| Variante | Intentos | Inferencias completadas | Comprobaciones superadas |", "|---|---:|---:|---:|"]
    for variant in variants:
        subset = [r for r in records if r["variant"] == variant]
        lines.append(f"| {variant} | {len(subset)} | {sum(r['inference_completed'] for r in subset)} | {sum(r['validation']['checks_passed'] for r in subset)} |")
    lines += ["", "Revisar cada salida en results.jsonl y completar revision_humana.csv.",
              "La primera inferencia puede incluir carga del modelo; no atribuir su latencia al diseño del prompt.",
              "Un error de infraestructura no equivale a una respuesta incorrecta del modelo.",
              "No concluir superioridad con una sola ejecución ni generalizar a tráfico empresarial."]
    (folder / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Evidencias guardadas en:", folder)
    return 0 if all(r["inference_completed"] for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
