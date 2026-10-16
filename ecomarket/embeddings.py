"""Embeddings E5 con prefijos y normalización, también para consultas en español."""
from langchain_core.embeddings import Embeddings


class E5Embeddings(Embeddings):
    def __init__(self, model_name, revision):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name, revision=revision, device="cpu", trust_remote_code=False)
        self.tokenizer = self.model.tokenizer
        self.revision = getattr(self.model[0].auto_model.config, "_commit_hash", None) or revision

    def _encode(self, texts, prefix):
        prefixed = [prefix + text for text in texts]
        if any(len(self.tokenizer.encode(text)) > 512 for text in prefixed):
            raise ValueError("Un texto supera 512 tokens de E5. Divide el documento o acorta la consulta.")
        return self.model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False).tolist()

    def embed_documents(self, texts):
        return self._encode(texts, "passage: ")

    def embed_query(self, text):
        return self._encode([text], "query: ")[0]
