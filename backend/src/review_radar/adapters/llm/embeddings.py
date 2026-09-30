"""Embedding models: a local hashing embedder for demo mode, any PydanticAI one otherwise."""

import hashlib
import math
import re
import time
from collections.abc import Sequence
from decimal import Decimal
from itertools import pairwise

from pydantic_ai import Embedder
from pydantic_ai.embeddings import EmbeddingModel, EmbeddingResult, EmbeddingSettings
from pydantic_ai.embeddings.result import EmbedInputType
from pydantic_ai.usage import RequestUsage

from review_radar.domain.errors import LlmError
from review_radar.domain.models import EMBEDDING_DIMENSIONS, LlmPurpose, LlmUsage

HASHING_MODEL_NAME = "hashing-256"

_STOPWORDS = frozenset(
    "a an the and or of to in on for with when after is are be it its app this that my i".split()  # noqa: SIM905
)
_WORD = re.compile(r"[a-z0-9]+")


def _features(text: str) -> list[str]:
    words = [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]
    # Crude stemming keeps "crash", "crashes" and "crashing" on one feature.
    stems = [w[:5] for w in words]
    return stems + [f"{a}_{b}" for a, b in pairwise(stems)]


def hash_embed(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """Signed feature hashing of word stems and bigrams, L2-normalized.

    blake2b rather than hash() so vectors are identical across processes;
    Python salts str hashes per interpreter.
    """
    vector = [0.0] * dimensions
    for feature in _features(text):
        digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "little") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class HashingEmbeddingModel(EmbeddingModel):
    """Offline, deterministic embeddings exposed through PydanticAI's interface."""

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        super().__init__()
        self._dimensions = dimensions

    @property
    def model_name(self) -> str:
        return HASHING_MODEL_NAME

    @property
    def system(self) -> str:
        return "local"

    async def embed(
        self,
        inputs: str | Sequence[str],
        *,
        input_type: EmbedInputType,
        settings: EmbeddingSettings | None = None,
    ) -> EmbeddingResult:
        texts, _ = self.prepare_embed(inputs, settings)
        return EmbeddingResult(
            embeddings=[hash_embed(t, self._dimensions) for t in texts],
            inputs=texts,
            input_type=input_type,
            model_name=self.model_name,
            provider_name=self.system,
            usage=RequestUsage(input_tokens=sum(len(_features(t)) for t in texts)),
        )


class PydanticAiTextEmbedder:
    """Adapts a PydanticAI Embedder to the TextEmbedder port."""

    def __init__(self, embedder: Embedder, *, model_name: str) -> None:
        self._embedder = embedder
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    async def embed(self, texts: Sequence[str]) -> tuple[list[list[float]], LlmUsage]:
        started = time.perf_counter()
        try:
            result = await self._embedder.embed_documents(
                texts, settings={"dimensions": EMBEDDING_DIMENSIONS}
            )
        except Exception as exc:
            raise LlmError(f"embedding failed: {exc}") from exc
        vectors = [list(map(float, v)) for v in result.embeddings]
        if any(len(v) != EMBEDDING_DIMENSIONS for v in vectors):
            raise LlmError("embedding model returned the wrong dimensionality")
        try:
            cost = Decimal(str(result.cost().total_price))
        except (LookupError, AssertionError):
            cost = Decimal(0)
        return vectors, LlmUsage(
            purpose=LlmPurpose.EMBEDDING,
            model_name=self._model_name,
            input_tokens=result.usage.input_tokens,
            output_tokens=0,
            cost_usd=cost,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


def build_embedder(model: str) -> PydanticAiTextEmbedder:
    if model == "demo":
        return PydanticAiTextEmbedder(
            Embedder(HashingEmbeddingModel()), model_name=HASHING_MODEL_NAME
        )
    return PydanticAiTextEmbedder(Embedder(model), model_name=model)
