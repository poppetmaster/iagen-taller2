"""Carga, segmentación e índice persistente. Los pedidos no se indexan."""
import csv
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from ecomarket.settings import ROOT
from scripts.prepare_knowledge import verify


def load_documents():
    verify()
    documents = []
    for page_number, page in enumerate(PdfReader(ROOT / "knowledge/politica_devoluciones.pdf").pages, 1):
        documents.append(Document(page_content=page.extract_text(), metadata={
            "source": "knowledge/politica_devoluciones.pdf", "location": "página " + str(page_number), "kind": "policy", "fictional": True}))
    with (ROOT / "knowledge/catalogo.csv").open(encoding="utf-8", newline="") as file:
        for row_number, row in enumerate(csv.DictReader(file), 2):
            documents.append(Document(page_content=f"Producto: {row['product']}. Categoría: {row['category']}. Solo se conocen el nombre y la categoría. No hay datos de precio, existencias ni características adicionales.",
                                      metadata={"source": "knowledge/catalogo.csv", "location": "fila " + str(row_number), "kind": "product", "fictional": True}))
    for faq in json.loads((ROOT / "knowledge/faq.json").read_text(encoding="utf-8")):
        documents.append(Document(page_content=f"Pregunta: {faq['question']}\nRespuesta: {faq['answer']}", metadata={
            "source": "knowledge/faq.json", "location": faq["id"], "kind": "faq", "fictional": True}))
    return documents


def chunk_documents(documents, tokenizer, config):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config["chunk_tokens"], chunk_overlap=config["chunk_overlap"],
        length_function=lambda text: len(tokenizer.encode(text, add_special_tokens=False)),
        separators=["\n\n", "\n", ". ", " ", ""])
    result = []
    for document in documents:
        pieces = splitter.split_documents([document]) if document.metadata["kind"] == "policy" else [document]
        for ordinal, piece in enumerate(pieces, 1):
            if len(tokenizer.encode("passage: " + piece.page_content)) > 512:
                raise ValueError("Fragmento demasiado largo: " + piece.metadata["source"])
            identity = f"{piece.metadata['source']}:{piece.metadata['location']}:{ordinal}:{piece.page_content}"
            piece.metadata.update(chunk_id=hashlib.sha256(identity.encode()).hexdigest()[:20],
                                  policy_id="ECOMARKET-DEMO-1", part=ordinal)
            result.append(piece)
    return result


def fingerprint(config):
    names = ["data/return_policy.json", "data/orders.json", "knowledge/provenance.json",
             "knowledge/politica_devoluciones.pdf", "knowledge/catalogo.csv", "knowledge/faq.json",
             "ecomarket/retrieval.py", "ecomarket/embeddings.py"]
    values = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}
    values["config"] = {key: config[key] for key in ["embedding_model", "embedding_revision", "chunk_tokens", "chunk_overlap"]}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def build_index(config, embeddings):
    from langchain_chroma import Chroma
    signature = fingerprint(config)
    folder = Path(config["index_dir"])
    folder.mkdir(parents=True, exist_ok=True)
    chunks = chunk_documents(load_documents(), embeddings.tokenizer, config)
    collection_name = "ecomarket_" + signature[:20]
    store = Chroma(collection_name=collection_name, embedding_function=embeddings,
                   persist_directory=str(folder / "chroma"), collection_metadata={"hnsw:space": "cosine"})
    store.add_documents(chunks, ids=[c.metadata["chunk_id"] for c in chunks])
    manifest = {"fingerprint": signature, "collection": collection_name, "chunks": len(chunks),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "embedding_model": config["embedding_model"], "embedding_revision": embeddings.revision,
                "metric": "cosine", "kinds": sorted({d.metadata["kind"] for d in chunks})}
    temporary = folder / "manifest.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(folder / "manifest.json")
    (folder / "chunks.json").write_text(json.dumps([{"text": c.page_content, **c.metadata} for c in chunks], ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


class Retriever:
    def __init__(self, config, embeddings):
        from langchain_chroma import Chroma
        self.config = config
        folder = Path(config["index_dir"])
        if not (folder / "manifest.json").is_file():
            raise ValueError("Primero construye el índice: python app.py index")
        self.manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        verify()
        if self.manifest["fingerprint"] != fingerprint(config):
            raise ValueError("El índice quedó desactualizado. Ejecuta python app.py index.")
        if self.manifest["embedding_revision"] != embeddings.revision:
            raise ValueError("La revisión del embedding difiere de la usada al indexar.")
        self.store = Chroma(collection_name=self.manifest["collection"], embedding_function=embeddings,
                            persist_directory=str(folder / "chroma"))

    def search(self, query):
        if not query.strip():
            raise ValueError("La consulta está vacía.")
        results = self.store.similarity_search_with_score(query, k=self.config["top_k"])
        hits = []
        for document, distance in results:
            similarity = 1.0 - float(distance)
            if not math.isfinite(similarity):
                continue
            threshold = self.config["minimum_similarity"]
            if threshold is not None and similarity < threshold:
                continue
            hits.append({"id": document.metadata["chunk_id"], "text": document.page_content,
                         "similarity": round(similarity, 6), "source": document.metadata["source"],
                         "location": document.metadata["location"], "kind": document.metadata["kind"]})
        return hits
