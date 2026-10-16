"""Entrada de consola del Taller 2; conserva los comandos del Taller 1."""
import argparse
import json
import sys


def create_retriever(config):
    from ecomarket.embeddings import E5Embeddings
    from ecomarket.retrieval import Retriever
    return Retriever(config, E5Embeddings(config["embedding_model"], config["embedding_revision"]))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if any(arg in {"order", "return"} for arg in argv[:4]):
        from app_legacy import main as legacy_main
        return legacy_main(argv)
    parser = argparse.ArgumentParser(description="EcoMarket: recuperación documental y datos exactos")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("index", help="Crear o actualizar el índice documental")
    retrieve = subs.add_parser("retrieve", help="Inspeccionar fragmentos sin llamar al generador")
    retrieve.add_argument("question")
    ask = subs.add_parser("ask", help="Consultar el asistente híbrido")
    ask.add_argument("question")
    ask.add_argument("--without-rag", action="store_true")
    ask.add_argument("--json", action="store_true", help="Mostrar evidencia completa")
    ask.add_argument("--as-of")
    ask.add_argument("--reason", choices=["cambio_opinion", "defecto", "danado", "equivocado"], default="cambio_opinion")
    for flag in ("opened", "used", "good-condition", "packaging-ok"):
        ask.add_argument("--" + flag, choices=["si", "no", "desconocido"], default="desconocido")
    args = parser.parse_args(argv)
    try:
        from ecomarket.settings import settings
        config = settings()
        if args.command == "index":
            from ecomarket.embeddings import E5Embeddings
            from ecomarket.retrieval import build_index
            result = build_index(config, E5Embeddings(config["embedding_model"], config["embedding_revision"]))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "retrieve":
            print(json.dumps(create_retriever(config).search(args.question), ensure_ascii=False, indent=2))
            return 0
        from ecomarket.rag import Assistant, route_question
        route, _, _ = route_question(args.question)
        retriever = create_retriever(config) if not args.without_rag and route in {"documents", "return"} and (route != "return" or args.as_of) else None
        inputs = {"as_of": args.as_of, "reason": args.reason,
                  **{key: {"si": True, "no": False, "desconocido": None}[getattr(args, key)]
                     for key in ("opened", "used", "good_condition", "packaging_ok")}}
        result = Assistant(config, retriever).answer(args.question, use_rag=not args.without_rag, return_inputs=inputs)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("ECOMARKET - DEMOSTRACIÓN CON DATOS FICTICIOS")
            print(result["message"])
            for hit in result["hits"]:
                if hit["id"] in result["citations"]:
                    print(f"Fuente: {hit['source']} ({hit['location']}) [{hit['id']}]")
            if result["facts"]:
                print("Hechos verificados:", json.dumps(result["facts"], ensure_ascii=False))
            print("Origen:", "modelo local" if result["generated"] else "control del programa, sin generación")
            if result["generated"]:
                print("Los controles son parciales; revisa el respaldo de las afirmaciones.")
        return 0 if result["checks_passed"] else 2
    except Exception as exc:
        print(f"No se pudo completar la consulta: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
