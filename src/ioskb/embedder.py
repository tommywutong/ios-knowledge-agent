"""bge-m3 本地 embedding，懒加载（首次 encode 才载入模型）。"""
import os


class Embedder:
    def __init__(self, cfg):
        e = cfg["embedding"]
        self.model_name = e["model"]
        self.batch_size = e.get("batch_size", 16)
        self._model = None

    def _load(self):
        if self._model is None:
            # sentence-transformers may probe for optional adapter metadata even
            # when local_files_only is passed. Disable Hub traffic for the whole
            # process so an already-installed model is genuinely offline.
            os.environ["HF_HUB_OFFLINE"] = "1"
            import torch
            from sentence_transformers import SentenceTransformer

            device = "mps" if torch.backends.mps.is_available() else "cpu"
            # The model is an installation-time dependency. Daily indexing and
            # search must remain fully local, and should not fail merely because
            # Hugging Face is temporarily unreachable.
            self._model = SentenceTransformer(
                self.model_name,
                device=device,
                local_files_only=True,
            )
        return self._model

    def encode(self, texts):
        import numpy as np

        model = self._load()
        vecs = model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 32,
        )
        return np.asarray(vecs, dtype=np.float32)
