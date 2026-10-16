"""Comprobaciones parciales: NO certifican veracidad semántica del texto libre."""
import json
import re


def validate_response(raw, context):
    errors = []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"checks_passed": False, "errors": ["json_invalido"], "parsed": None}
    if not isinstance(parsed, dict) or set(parsed) != {"facts", "message"}:
        return {"checks_passed": False, "errors": ["contrato_invalido"], "parsed": parsed}
    # Serialización canónica distingue false de 0 y mantiene el tipo de los datos.
    if json.dumps(parsed["facts"], sort_keys=True) != json.dumps(context["verified_facts"], sort_keys=True):
        errors.append("hechos_estructurados_distintos")
    message = parsed["message"]
    if not isinstance(message, str) or not message.strip():
        errors.append("mensaje_vacio_o_invalido")
    else:
        expected = context["tracking_requested"]
        if any(x != expected for x in re.findall(r"EM-\d+", message, flags=re.I)):
            errors.append("otro_pedido_en_texto")
        allowed = {o["tracking_url"] for o in context["orders"]
                   if o["tracking_number"] == expected and o.get("tracking_url")}
        urls = {u.rstrip(".,;)") for u in re.findall(r"https?://[^\s<>\"']+", message)}
        if not urls.issubset(allowed):
            errors.append("enlace_no_autorizado")
    return {"checks_passed": not errors, "errors": errors, "parsed": parsed}
