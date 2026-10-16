"""Fuentes de verdad y reglas independientes del LLM."""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def find_order(tracking):
    key = tracking.strip().upper()
    return next((o for o in load_json("orders.json") if o["tracking_number"] == key), None)


def order_facts(tracking):
    order = find_order(tracking)
    if order is None:
        return {"tracking_number": tracking.strip().upper(), "found": False,
                "status": None, "estimated_delivery": None, "tracking_url": None,
                "delay_reason": None, "delivered_at": None}
    return {"tracking_number": order["tracking_number"], "found": True,
            **{k: order[k] for k in ("status", "estimated_delivery", "tracking_url",
                                    "delay_reason", "delivered_at")}}


def evaluate_return(tracking, as_of, opened=None, used=None, good_condition=None,
                    packaging_ok=None, reason="cambio_opinion"):
    """Nunca infiere que desconocido equivale a sellado, sin uso o buen estado."""
    request_date = date.fromisoformat(as_of)
    policy = load_json("return_policy.json")
    order = find_order(tracking)
    result = {"tracking_number": tracking.strip().upper(), "decision": "informacion_insuficiente",
              "reason_code": "pedido_no_encontrado", "days_since_delivery": None,
              "missing_fields": [], "next_step": "Verificar el número de seguimiento."}

    def decide(decision, code, step):
        result.update(decision=decision, reason_code=code, next_step=step)
        return result

    if order is None:
        return result
    if order["status"] == "Cancelado":
        return decide("no_elegible", "pedido_cancelado", "Consultar la cancelación con soporte; no iniciar una devolución.")
    if reason in policy["human_review_reasons"]:
        return decide("revision_humana", "reclamacion_especial", "Solicitar revisión humana por daño, defecto o producto equivocado.")
    if order["status"] != "Entregado":
        return decide("revision_humana", "pedido_no_entregado", "Consultar con soporte el pedido pendiente de entrega.")
    if not order["delivered_at"]:
        result["missing_fields"] = ["delivered_at"]
        return decide("informacion_insuficiente", "fecha_entrega_desconocida", "Confirmar la fecha efectiva de entrega.")
    elapsed = (request_date - date.fromisoformat(order["delivered_at"])).days
    result["days_since_delivery"] = elapsed
    if elapsed < 0:
        return decide("revision_humana", "fechas_inconsistentes", "Revisar fechas: la solicitud antecede a la entrega.")
    if elapsed > policy["return_window_days"]:
        return decide("no_elegible", "fuera_de_plazo", "Explicar el plazo de la política ficticia y ofrecer revisión humana.")
    category = order["category"]
    if category in policy["ordinary_excluded_categories"]:
        return decide("no_elegible", "categoria_excluida", "Explicar la exclusión para devolución ordinaria; las reclamaciones especiales requieren revisión.")
    if category not in policy["conditions_by_category"]:
        return decide("revision_humana", "categoria_sin_politica", "Consultar al agente responsable de políticas.")
    values = {"opened": opened, "used": used, "good_condition": good_condition, "packaging_ok": packaging_ok}
    conditions = policy["conditions_by_category"][category]
    failures = [key for key, expected in conditions.items() if values[key] is not None and values[key] != expected]
    if failures:
        return decide("no_elegible", "condiciones_incumplidas:" + ",".join(failures),
                      "Explicar las condiciones incumplidas; ofrecer revisión si existe una reclamación especial.")
    missing = [key for key in conditions if values[key] is None]
    if missing:
        result["missing_fields"] = missing
        return decide("informacion_insuficiente", "faltan_condiciones", "Solicitar únicamente las condiciones pendientes.")
    return decide("elegible", "cumple_politica", "Solicitar apertura del trámite a soporte; conservar producto y empaque. No se ha registrado ni aprobado un reembolso.")


def build_context(task, tracking, scope="all", **return_inputs):
    order = find_order(tracking)
    orders = load_json("orders.json") if scope == "all" else ([order] if order else [])
    facts = order_facts(tracking) if task == "order" else evaluate_return(tracking, **return_inputs)
    context = {"demo": "Datos sintéticos; enlaces simulados; sin conexión con transportadoras.",
               "task": task, "tracking_requested": tracking.strip().upper(),
               "orders": orders, "verified_facts": facts}
    if task == "return":
        context.update(policy=load_json("return_policy.json"), return_inputs=return_inputs)
    return context


def render_facts(task, facts):
    """Salida de referencia, no generación de IA."""
    if task == "return":
        missing = ", ".join(facts["missing_fields"]) or "ninguno"
        return (f"Decisión: {facts['decision']}. Motivo: {facts['reason_code']}. "
                f"Datos pendientes: {missing}. {facts['next_step']}")
    if not facts["found"]:
        return "No encuentro ese seguimiento en la base de prueba. Verifica el número o solicita apoyo humano."
    parts = [f"Pedido {facts['tracking_number']}: {facts['status']}."]
    if facts["delivered_at"]:
        parts.append(f"Entrega registrada: {facts['delivered_at']}.")
    elif facts["status"] != "Cancelado":
        parts.append(f"Entrega estimada: {facts['estimated_delivery'] or 'no disponible'}.")
    if facts["status"] == "Retrasado":
        parts.append(f"Lamentamos el retraso. Causa registrada: {facts['delay_reason'] or 'no disponible'}.")
    if facts["tracking_url"]:
        parts.append(f"Seguimiento simulado: {facts['tracking_url']}.")
    return " ".join(parts)
