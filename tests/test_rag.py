import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from ecomarket.rag import Assistant, route_question, validate_generated
from ecomarket.retrieval import load_documents, chunk_documents, fingerprint, build_index, Retriever
from ecomarket.settings import settings
from scripts.prepare_knowledge import verify


class FakeTokenizer:
    def encode(self, text, add_special_tokens=True):
        return text.split()


class FakeEmbeddings:
    """Solo verifica persistencia y contratos; no es evidencia de recuperación E5."""
    tokenizer = FakeTokenizer()
    revision = "TEST-ONLY"

    def embed_documents(self, texts):
        return [[float("plazo" in text.lower()), 1.0, 0.1] for text in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


class DocumentTests(unittest.TestCase):
    def test_derived_documents_match_canonical_sources(self):
        self.assertEqual(verify()["products"], 12)

    def test_three_document_kinds_and_no_orders(self):
        docs = load_documents()
        self.assertEqual({d.metadata["kind"] for d in docs}, {"policy", "product", "faq"})
        self.assertFalse(any("EM-100" in d.page_content for d in docs))

    def test_structured_records_remain_whole(self):
        docs = load_documents()
        chunks = chunk_documents(docs, FakeTokenizer(), settings())
        self.assertEqual(len([c for c in chunks if c.metadata["kind"] == "product"]), 12)
        self.assertEqual(len({c.metadata["chunk_id"] for c in chunks}), len(chunks))

    def test_embedding_config_changes_fingerprint(self):
        config = settings()
        self.assertNotEqual(fingerprint(config), fingerprint({**config, "chunk_tokens": 200}))

    def test_long_structured_record_is_not_silently_truncated(self):
        from langchain_core.documents import Document
        doc = Document(page_content="producto " * 600, metadata={"kind": "product", "source": "test", "location": "1"})
        with self.assertRaises(ValueError):
            chunk_documents([doc], FakeTokenizer(), settings())

    def test_persistent_index_and_stale_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            config = {**settings(), "index_dir": folder}
            manifest = build_index(config, FakeEmbeddings())
            retriever = Retriever(config, FakeEmbeddings())
            self.assertTrue(retriever.search("plazo"))
            self.assertEqual(manifest["chunks"], 36)
            with self.assertRaises(ValueError):
                Retriever({**config, "chunk_tokens": 200}, FakeEmbeddings())

    def test_missing_index_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "Primero construye"):
                Retriever({**settings(), "index_dir": folder}, FakeEmbeddings())


class RoutingTests(unittest.TestCase):
    def test_exact_order(self):
        self.assertEqual(route_question("¿Dónde está EM-1003?")[:2], ("order", "EM-1003"))

    def test_return_and_documental_policy_are_distinct(self):
        self.assertEqual(route_question("¿Puedo devolver EM-1010?")[0], "return")
        self.assertEqual(route_question("¿Cuál es el plazo de devolución?")[0], "documents")

    def test_unknown_tracking_requests_clarification(self):
        self.assertEqual(route_question("¿Dónde está mi pedido?")[0], "clarify")

    def test_multi_order_and_actions_are_stopped(self):
        self.assertEqual(route_question("EM-1001 y EM-1002")[0], "clarify")
        self.assertEqual(route_question("Cancela mi pedido EM-1001")[0], "unsupported")


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.hits = [{"id": "abc", "source": "policy", "location": "1", "text": "Plazo 30 días"}]

    def payload(self, **changes):
        result = {"status": "answered", "message": "El plazo es 30 días.", "citations": ["abc"], "facts": {}}
        result.update(changes)
        return json.dumps(result)

    def check(self, **changes):
        return validate_generated(self.payload(**changes), {}, self.hits, "documents")

    def test_valid_citation_contract(self):
        self.assertTrue(self.check()["passed"])

    def test_unknown_citation_and_missing_citation(self):
        self.assertFalse(self.check(citations=["inventada"])["passed"])
        self.assertFalse(self.check(citations=[])["passed"])

    def test_citation_type_is_validated(self):
        self.assertFalse(self.check(citations=[{}])["passed"])

    def test_no_context_requires_abstention(self):
        result = validate_generated(self.payload(citations=[]), {}, [], "documents")
        self.assertIn("respuesta_sin_evidencia", result["errors"])

    def test_changed_facts_are_rejected(self):
        self.assertFalse(self.check(facts={"decision": "elegible"})["passed"])

    def test_action_claim_is_rejected(self):
        self.assertFalse(self.check(message="Ya emití tu reembolso.")["passed"])
        self.assertTrue(self.check(message="No puedo emitir reembolsos.")["passed"])

    def test_markdown_url_is_not_a_false_positive(self):
        facts = {"tracking_number": "EM-1003", "tracking_url": "https://tracking.example/EM-1003"}
        raw = self.payload(facts=facts, citations=[], message="Seguimiento simulado: [ver](https://tracking.example/EM-1003).")
        self.assertTrue(validate_generated(raw, facts, [], "order")["passed"])

    def test_other_order_is_rejected(self):
        self.assertFalse(self.check(message="Consulta el pedido EM-1001.")["passed"])

    def test_markdown_url_label_can_be_the_url_itself(self):
        facts = {"tracking_number": "EM-1003", "tracking_url": "https://tracking.example/EM-1003"}
        url = facts["tracking_url"]
        raw = self.payload(facts=facts, citations=[], message=f"Seguimiento simulado: [{url}]({url}).")
        self.assertTrue(validate_generated(raw, facts, [], "order")["passed"])

    def test_simulated_link_requires_an_explicit_label(self):
        facts = {"tracking_number": "EM-1003", "tracking_url": "https://tracking.example/EM-1003"}
        raw = self.payload(facts=facts, citations=[], message="Rastrea en https://tracking.example/EM-1003")
        self.assertIn("seguimiento_simulado_sin_aclaracion", validate_generated(raw, facts, [], "order")["errors"])

    def test_valid_format_does_not_certify_semantics(self):
        self.assertTrue(self.check(message="El plazo es un millón de días.")["passed"])

    def test_type_and_json_errors_are_visible(self):
        self.assertFalse(validate_generated("no json", {}, [], "documents")["passed"])
        self.assertFalse(self.check(message={})["passed"])


class FlowTests(unittest.TestCase):
    def llm(self, payload):
        return RunnableLambda(lambda messages: AIMessage(content=json.dumps(payload)))

    def test_without_rag_calls_model_with_no_documents(self):
        llm = self.llm({"status": "insufficient", "message": "No tengo documentos.", "citations": [], "facts": {}})
        result = Assistant(settings(), llm=llm).answer("¿Cuál es el plazo?", use_rag=False)
        self.assertTrue(result["generated"])
        self.assertEqual(result["hits"], [])

    def test_failed_model_is_not_replaced_by_fake_generation(self):
        def fail(value):
            raise RuntimeError("servicio no disponible")
        with self.assertRaises(RuntimeError):
            Assistant(settings(), llm=RunnableLambda(fail)).answer("¿Cuál es el plazo?", use_rag=False)

    def test_clarification_needs_no_model_call(self):
        llm = RunnableLambda(lambda messages: self.fail("No debe llamar al modelo"))
        result = Assistant(settings(), llm=llm).answer("¿Puedo devolver EM-1010?")
        self.assertEqual(result["status"], "clarify")
        self.assertFalse(result["generated"])

    def test_invalid_generation_is_withheld(self):
        llm = self.llm({"status": "answered", "message": "Inventado", "citations": [], "facts": {}})
        result = Assistant(settings(), llm=llm).answer("¿Cuál es el plazo?", use_rag=False)
        self.assertEqual(result["status"], "withheld")
        self.assertNotEqual(result["message"], "Inventado")

    def test_exact_order_context_does_not_include_all_orders(self):
        from ecomarket.domain import order_facts
        facts = order_facts("EM-1003")
        llm = self.llm({"status": "answered", "message": "Pedido retrasado.", "citations": [], "facts": facts})
        result = Assistant(settings(), llm=llm).answer("¿Dónde está EM-1003?")
        self.assertNotIn("EM-1002", result["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()
