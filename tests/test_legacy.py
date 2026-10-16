import io
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
import app_legacy as app
import evaluate_legacy as evaluate
from ecomarket import domain
from ecomarket.llm import generate
from ecomarket.prompts import build_prompt
from ecomarket.validation import validate_response


class DomainTests(unittest.TestCase):
    def valid(self, tracking="EM-1010", **kwargs):
        inputs = dict(as_of="2026-09-24", opened=False, used=False, good_condition=True, packaging_ok=True)
        inputs.update(kwargs)
        return domain.evaluate_return(tracking, **inputs)

    def test_dataset_twelve_unique_orders(self):
        orders = domain.load_json("orders.json")
        self.assertEqual(len(orders), 12)
        self.assertEqual(len({o["tracking_number"] for o in orders}), 12)

    def test_lookup_normalizes(self):
        self.assertEqual(domain.find_order(" em-1001 ")["status"], "En tránsito")

    def test_missing_order(self):
        self.assertFalse(domain.order_facts("EM-9999")["found"])

    def test_missing_estimate(self):
        self.assertIsNone(domain.order_facts("EM-1005")["estimated_delivery"])

    def test_missing_delay_reason(self):
        self.assertIsNone(domain.order_facts("EM-1009")["delay_reason"])

    def test_eligible_textile(self):
        self.assertEqual(self.valid()["decision"], "elegible")

    def test_perishable_ordinary_excluded(self):
        self.assertEqual(self.valid("EM-1008")["decision"], "no_elegible")

    def test_perishable_defect_human(self):
        self.assertEqual(self.valid("EM-1008", reason="defecto")["decision"], "revision_humana")

    def test_open_hygiene(self):
        self.assertEqual(self.valid("EM-1002", opened=True)["decision"], "no_elegible")

    def test_open_cleaning(self):
        self.assertEqual(self.valid("EM-1011", opened=True)["decision"], "no_elegible")

    def test_used_textile(self):
        self.assertEqual(self.valid(used=True)["decision"], "no_elegible")

    def test_missing_condition(self):
        result = self.valid(used=None)
        self.assertEqual(result["decision"], "informacion_insuficiente")
        self.assertIn("used", result["missing_fields"])

    def test_unknown_sealed_is_not_false(self):
        self.assertEqual(self.valid("EM-1002", opened=None)["decision"], "informacion_insuficiente")

    def test_cancelled(self):
        self.assertEqual(self.valid("EM-1012")["reason_code"], "pedido_cancelado")

    def test_not_delivered(self):
        self.assertEqual(self.valid("EM-1001")["decision"], "revision_humana")

    def test_expired(self):
        self.assertEqual(self.valid("EM-1006")["reason_code"], "fuera_de_plazo")

    def test_day_30_allowed(self):
        self.assertEqual(self.valid(as_of="2026-10-15")["decision"], "elegible")

    def test_day_31_rejected(self):
        self.assertEqual(self.valid(as_of="2026-10-16")["decision"], "no_elegible")

    def test_future_delivery(self):
        self.assertEqual(self.valid(as_of="2026-09-01")["reason_code"], "fechas_inconsistentes")

    def test_invalid_date(self):
        with self.assertRaises(ValueError):
            self.valid(as_of="2026-02-30")

    def test_missing_delivery_date(self):
        order = dict(domain.find_order("EM-1010"), delivered_at=None)
        with patch("ecomarket.domain.find_order", return_value=order):
            self.assertEqual(self.valid()["decision"], "informacion_insuficiente")

    def test_unknown_category(self):
        order = dict(domain.find_order("EM-1010"), category="otra")
        with patch("ecomarket.domain.find_order", return_value=order):
            self.assertEqual(self.valid()["decision"], "revision_humana")

    def test_case_oracles(self):
        for case in domain.load_json("evaluation_cases.json"):
            with self.subTest(case=case["id"]):
                ctx = domain.build_context(case["task"], case["tracking"], **case.get("inputs", {}))
                for key, expected in case["expected"].items():
                    self.assertEqual(ctx["verified_facts"][key], expected)


class PromptValidationTests(unittest.TestCase):
    def setUp(self):
        self.context = domain.build_context("order", "EM-1003")

    def response(self, **changes):
        payload = {"facts": self.context["verified_facts"], "message": "Lamentamos el retraso de EM-1003."}
        payload.update(changes)
        return json.dumps(payload)

    def test_full_document_in_context(self):
        self.assertEqual(len(self.context["orders"]), 12)
        prompt = build_prompt(self.context)["prompt"]
        self.assertIn("EM-1012", prompt)

    def test_single_context(self):
        self.assertEqual(len(domain.build_context("order", "EM-1003", scope="single")["orders"]), 1)

    def test_same_context_both_variants(self):
        basic = build_prompt(self.context, "baseline")["prompt"].split("CONTEXTO_JSON\n")[1]
        improved = build_prompt(self.context, "improved")["prompt"].split("CONTEXTO_JSON\n")[1]
        self.assertEqual(basic, improved)

    def test_valid_response(self):
        self.assertTrue(validate_response(self.response(), self.context)["checks_passed"])

    def test_wrong_facts(self):
        self.assertFalse(validate_response(self.response(facts={}), self.context)["checks_passed"])

    def test_invalid_json(self):
        self.assertFalse(validate_response("hola", self.context)["checks_passed"])

    def test_other_order(self):
        self.assertFalse(validate_response(self.response(message="El pedido EM-1002"), self.context)["checks_passed"])

    def test_invented_url(self):
        self.assertFalse(validate_response(self.response(message="Mira https://falso.example/x"), self.context)["checks_passed"])

    def test_empty_message(self):
        self.assertFalse(validate_response(self.response(message=""), self.context)["checks_passed"])

    def test_free_text_semantics_not_certified(self):
        # Documenta el límite real del validador: requiere revisión humana.
        text = self.response(message="Tu pedido llegará mañana sin falta.")
        self.assertTrue(validate_response(text, self.context)["checks_passed"])


class IntegrationTests(unittest.TestCase):
    def test_rules_cli(self):
        with redirect_stdout(io.StringIO()) as output:
            code = app.main(["--mode", "rules", "order", "EM-1003"])
        self.assertEqual(code, 0)
        self.assertIn("NO fue generada por IA", output.getvalue())

    def test_model_failure_not_hidden(self):
        with patch("app_legacy.generate", side_effect=RuntimeError("sin servicio")), redirect_stderr(io.StringIO()):
            self.assertEqual(app.main(["order", "EM-1003"]), 1)

    def test_invalid_llm_output_not_displayed(self):
        with patch("app_legacy.generate", return_value={"raw_response": "CONTENIDO_INCORRECTO"}), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(app.main(["order", "EM-1003"]), 2)
        self.assertNotIn("CONTENIDO_INCORRECTO", output.getvalue())

    def test_llm_payload_with_mock_not_actual_inference(self):
        with patch("ecomarket.llm.request_json", return_value={"response": "{}"}) as mocked:
            generate({"system": "s", "prompt": "p"})
        self.assertEqual(mocked.call_args.args[1]["options"]["seed"], 42)
        self.assertFalse(mocked.call_args.args[1]["stream"])

    def test_empty_llm_response(self):
        with patch("ecomarket.llm.request_json", return_value={"response": " "}):
            with self.assertRaises(RuntimeError):
                generate({"system": "s", "prompt": "p"})

    def test_evaluator_records_mocked_runs_and_blank_human_review(self):
        context = domain.build_context("order", "EM-1003")
        response = {"raw_response": json.dumps({"facts": context["verified_facts"], "message": "Retraso registrado."}), "elapsed_seconds": 0.01}
        identity = {"model": "test-double", "digest": "TEST-ONLY", "ollama_version": "TEST-ONLY"}
        with tempfile.TemporaryDirectory() as folder:
            with patch("evaluate_legacy.model_identity", return_value=identity), patch("evaluate_legacy.generate", return_value=response), redirect_stdout(io.StringIO()):
                result = evaluate.main(["--case", "pedido_retrasado", "--output", folder])
            self.assertEqual(result, 0)
            run = next(Path(folder).iterdir())
            records = [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines()]
            self.assertEqual(len(records), 2)
            self.assertTrue(all(r["inference_completed"] for r in records))
            self.assertIn("pedido_retrasado,baseline,,,,,,", (run / "revision_humana.csv").read_text())
            self.assertTrue((run / "SUMMARY.md").exists())

    def test_evaluator_does_not_create_evidence_without_model(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("evaluate_legacy.model_identity", side_effect=RuntimeError("no model")), redirect_stderr(io.StringIO()):
                self.assertEqual(evaluate.main(["--case", "pedido_retrasado", "--output", folder]), 1)
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
