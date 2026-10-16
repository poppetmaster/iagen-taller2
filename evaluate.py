"""Compara el mismo modelo con y sin recuperación, conservando evidencia cruda."""
import argparse
import csv
import importlib.metadata
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from ecomarket.settings import ROOT, settings


def relevance(case, hits):
    if "relevant_locations" in case:
        return any(h["location"] in case["relevant_locations"] and h["kind"] in {"policy", "faq"} for h in hits)
    if "relevant_product" in case:
        return any(h["kind"] == "product" and case["relevant_product"] in h["text"] for h in hits)
    return None


def versions():
    names = ["langchain-core", "langchain-chroma", "langchain-ollama", "chromadb", "sentence-transformers", "torch", "pypdf"]
    return {name: importlib.metadata.version(name) for name in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--variant", choices=["both", "rag", "without_rag"], default="both")
    parser.add_argument("--case", action="append")
    parser.add_argument("--output", default=str(ROOT / "evaluacion/runs"))
    args = parser.parse_args()
    from app import create_retriever
    from ecomarket.rag import Assistant, model_identity, normalize
    config = settings()
    try:
        retriever = create_retriever(config)
        filename = "calibration_cases.json" if args.calibrate else "rag_cases.json"
        cases = json.loads((ROOT / "data" / filename).read_text(encoding="utf-8"))
        if args.case:
            unknown = set(args.case) - {c["id"] for c in cases}
            if unknown:
                parser.error("Casos desconocidos: " + ", ".join(sorted(unknown)))
            cases = [c for c in cases if c["id"] in args.case]
        retrieval_only = args.retrieval_only or args.calibrate
        identity = {} if retrieval_only else model_identity(config)
        assistant = None if retrieval_only else Assistant(config, retriever)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        folder = Path(args.output) / stamp
        folder.mkdir(parents=True, exist_ok=False)
        metadata = {"started_at_utc": stamp, "kind": "calibration" if args.calibrate else "retrieval" if retrieval_only else "generation",
                    "config": {k: v for k, v in config.items() if k != "index_dir"}, "index": retriever.manifest,
                    "versions": versions(), "python": platform.python_version(), "platform": platform.platform(),
                    "cases": [c["id"] for c in cases], **identity}
        (folder / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        records = []
        variants = ["rag", "without_rag"] if args.variant == "both" else [args.variant]
        with (folder / "results.jsonl").open("w", encoding="utf-8") as file:
            for index, case in enumerate(cases):
                for variant in (["retrieval"] if retrieval_only else variants if index % 2 == 0 else list(reversed(variants))):
                    record = {"case_id": case["id"], "variant": variant, "expected": case}
                    try:
                        if retrieval_only:
                            started = time.perf_counter()
                            hits = retriever.search(case["question"])
                            result = {"hits": hits, "retrieval_seconds": round(time.perf_counter() - started, 4)}
                        else:
                            result = assistant.answer(case["question"], use_rag=variant == "rag")
                        record.update(result, execution_completed=True)
                        record["relevant_hit_at_k"] = relevance(case, result["hits"])
                        if not retrieval_only:
                            parsed = result.get("validation", {}).get("parsed") or {}
                            record["expected_status_matched"] = parsed.get("status") == case["expected_status"]
                            text = normalize(str(parsed.get("message", "")))
                            record["expected_terms_present"] = all(normalize(term) in text for term in case["expected_terms"])
                    except Exception as exc:
                        record.update(execution_completed=False, error=str(exc))
                    file.write(json.dumps(record, ensure_ascii=False) + "\n")
                    file.flush()
                    records.append(record)
                    print(case["id"], variant, "completado" if record["execution_completed"] else record["error"], flush=True)
        if not retrieval_only:
            with (folder / "revision.csv").open("w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["case_id", "variant", "exactitud_0_1", "respaldo_citas_0_1", "limites_0_1", "empatia_0_1", "evaluador", "observaciones"])
                writer.writerows([[r["case_id"], r["variant"], "", "", "", "", "", ""] for r in records])
        lines = ["# Resultados de ejecución", "", "Esta tabla presenta controles parciales. No equivale a una calificación semántica.", "",
                 "| Variante | Intentos | Completados | Contrato superado | Estado esperado | Evidencia pertinente entre los primeros k |",
                 "|---|---:|---:|---:|---:|---:|"]
        for variant in sorted({r["variant"] for r in records}):
            subset = [r for r in records if r["variant"] == variant]
            eligible = [r for r in subset if r.get("relevant_hit_at_k") is not None]
            hit_score = f"{sum(r['relevant_hit_at_k'] for r in eligible)}/{len(eligible)}" if eligible else "NA"
            lines.append(f"| {variant} | {len(subset)} | {sum(r['execution_completed'] for r in subset)} | {sum(r.get('checks_passed', False) for r in subset) if not retrieval_only else 'NA'} | {sum(r.get('expected_status_matched', False) for r in subset) if not retrieval_only else 'NA'} | {hit_score} |")
        if args.calibrate:
            values = [{"id": r["case_id"], "answerable": r["expected"]["answerable"],
                       "maximum_similarity": max((h["similarity"] for h in r.get("hits", [])), default=None)} for r in records]
            (folder / "calibration.json").write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            lines += ["", "Los casos de calibración son distintos a los de evaluación. Revisar el solapamiento de similitudes antes de proponer un umbral; no son probabilidades de respuesta correcta."]
        lines += ["", "Las respuestas y los fragmentos completos están en results.jsonl. Los errores de infraestructura se reportan aparte."]
        (folder / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("Evidencia:", folder, flush=True)
        return 0 if all(r["execution_completed"] for r in records) else 1
    except Exception as exc:
        print("No se inició la evaluación:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
