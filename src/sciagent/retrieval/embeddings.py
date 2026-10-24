"""Feature-hashing embedder.

A dependency-free embedder for local runs and tests. In production the agent
service swaps in the embedding endpoint served next to the LLM; the vector
store only depends on the ``embed`` signature.
"""

from __future__ import annotations

import hashlib
import itertools
import re

import numpy as np

TOKEN = re.compile(r"[a-z0-9]+")


class HashingEmbedder:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def _features(self, text: str) -> list[str]:
        toks = TOKEN.findall(text.lower())
        return toks + [f"{a}_{b}" for a, b in itertools.pairwise(toks)]

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for feat in self._features(text):
            h = int.from_bytes(hashlib.blake2b(feat.encode(), digest_size=8).digest(), "big")
            vec[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec
