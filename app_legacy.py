"""CLI: por defecto invoca IA; --mode rules identifica explícitamente el modo sin IA."""
import argparse
import json
import sys
from ecomarket.domain import build_context, render_facts
from ecomarket.prompts import build_prompt
from ecomarket.llm import generate
from ecomarket.validation import validate_response


def optional_bool(value):
    return {"si": True, "no": False, "desconocido": None}[value]


def main(argv=None):
    parser = argparse.ArgumentParser(description="EcoMarket: prototipo académico con datos sintéticos")
    parser.add_argument("--mode", choices=["llm", "rules"], default="llm")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--variant", choices=["baseline", "improved"], default="improved")
    parser.add_argument("--context", choices=["all", "single"], default="all",
                        help="all incorpora los 12 pedidos ficticios al prompt para cumplir el enunciado")
    parser.add_argument("--show-prompt", action="store_true")
    parser.add_argument("--question", help="Consulta opcional para pruebas de comportamiento")
    subs = parser.add_subparsers(dest="task", required=True)
    subs.add_parser("order").add_argument("tracking")
    ret = subs.add_parser("return")
    ret.add_argument("tracking")
    ret.add_argument("--as-of", required=True, help="Fecha de solicitud YYYY-MM-DD; explícita para reproducibilidad")
    ret.add_argument("--reason", choices=["cambio_opinion", "defecto", "danado", "equivocado"], default="cambio_opinion")
    for flag in ("opened", "used", "good-condition", "packaging-ok"):
        ret.add_argument("--" + flag, choices=["si", "no", "desconocido"], default="desconocido")
    args = parser.parse_args(argv)
    inputs = {}
    if args.task == "return":
        inputs = {"as_of": args.as_of, "reason": args.reason,
                  **{k: optional_bool(getattr(args, k)) for k in ("opened", "used", "good_condition", "packaging_ok")}}
    try:
        context = build_context(args.task, args.tracking, scope=args.context, **inputs)
        messages = build_prompt(context, args.variant, args.question)
        if args.show_prompt:
            print(json.dumps(messages, ensure_ascii=False, indent=2))
        if args.mode == "rules":
            print("MODO REGLAS: esta respuesta NO fue generada por IA.")
            print(render_facts(args.task, context["verified_facts"]))
            return 0
        output = generate(messages, args.model)
        result = validate_response(output["raw_response"], context)
        if not result["checks_passed"]:
            print("La respuesta generada no superó las comprobaciones. Requiere revisión humana.")
            print("Motivos:", ", ".join(result["errors"]))
            print("Referencia verificada:", render_facts(args.task, context["verified_facts"]))
            return 2
        print("ASISTENTE VIRTUAL — DEMOSTRACIÓN CON DATOS SINTÉTICOS")
        print(result["parsed"]["message"])
        print("\nHechos verificados:", json.dumps(context["verified_facts"], ensure_ascii=False))
        print("\nEl texto libre requiere revisión semántica; el control automático es parcial.")
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
