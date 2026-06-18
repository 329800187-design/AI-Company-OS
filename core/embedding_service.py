"""
Embedding 语义搜索服务 — 用 AI API 生成向量，替代纯本地 TF-IDF

支持:
  - OpenAI text-embedding-3-small / text-embedding-ada-002
  - DeepSeek (通过 CC Switch 或兼容接口)
  - 本地 TF-IDF 降级

用法:
  emb = get_embedding_service()
  query_vec = emb.embed("Python code review security")
  results = emb.similarity(query_vec, doc_vectors)
"""
import json
import math
import os
import hashlib
import threading
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from backend.config import get_ai_config, AI_PROVIDER

# 维度 (OpenAI text-embedding-3-small = 1536)
EMBEDDING_DIM = 1536


class EmbeddingService:
    """AI 驱动的 Embedding 服务 + 本地降级"""

    def __init__(self, dim: int = 1536):
        self.dim = dim
        self._lock = threading.Lock()
        self._embed_cache: Dict[str, List[float]] = {}  # text_hash → vector
        self._api_available: Optional[bool] = None  # 懒探测
        self._api_calls = 0
        self._local_calls = 0

    def embed(self, text: str) -> List[float]:
        """生成文本的 embedding 向量"""
        if not text or not text.strip():
            return [0.0] * self.dim

        cache_key = hashlib.md5(text.encode()).hexdigest()
        with self._lock:
            if cache_key in self._embed_cache:
                return self._embed_cache[cache_key]

        # 尝试 AI API
        if self._check_api():
            vec = self._call_embedding_api(text)
            if vec:
                with self._lock:
                    self._embed_cache[cache_key] = vec
                    self._api_calls += 1
                return vec

        # 降级: 本地 TF-IDF 向量
        vec = self._local_embed(text)
        with self._lock:
            self._embed_cache[cache_key] = vec
            self._local_calls += 1
        return vec

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成 embeddings（更高效）"""
        if self._check_api():
            try:
                return self._call_embedding_api_batch(texts)
            except Exception:
                pass
        return [self.embed(t) for t in texts]

    def similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """余弦相似度"""
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a**2 for a in vec_a))
        norm_b = math.sqrt(sum(b**2 for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(self, query: str, documents: List[Tuple[str, Any]],
               top_k: int = 5) -> List[Tuple[str, Any, float]]:
        """
        语义搜索: query → [doc_texts] → top_k 结果

        Args:
          query: 搜索查询
          documents: [(doc_text, payload), ...]
          top_k: 返回条数
        Returns:
          [(doc_text, payload, similarity_score), ...]
        """
        if not documents:
            return []

        query_vec = self.embed(query)
        scored = []
        for doc_text, payload in documents:
            doc_vec = self.embed(doc_text)
            score = self.similarity(query_vec, doc_vec)
            scored.append((doc_text, payload, score))

        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:top_k]

    def stats(self) -> Dict:
        return {
            "cached_embeddings": len(self._embed_cache),
            "api_calls": self._api_calls,
            "local_calls": self._local_calls,
            "api_available": self._check_api(),
            "dimension": self.dim,
        }

    # ── 内部 ──────────────────────────────────────────

    def _check_api(self) -> bool:
        if self._api_available is not None:
            return self._api_available
        # 优先用本地 sentence-transformers（质量最高，零API成本）
        if self._check_local_model():
            self._api_available = True
            return True
        try:
            config = get_ai_config()
            self._api_available = bool(config.get("api_key"))
        except Exception:
            self._api_available = False
        return self._api_available

    def _check_local_model(self) -> bool:
        """Check if sentence-transformers is available"""
        try:
            import sentence_transformers
            return True
        except ImportError:
            return False

    def _get_local_model(self):
        """Lazy-load sentence-transformers model"""
        if not hasattr(self, '_local_model'):
            try:
                from sentence_transformers import SentenceTransformer
                self._local_model = SentenceTransformer('all-MiniLM-L6-v2')
                self.dim = 384  # MiniLM output dimension
            except Exception as e:
                print(f"[Embedding] sentence-transformers load failed: {e}")
                self._local_model = None
        return self._local_model

    def _call_embedding_api(self, text: str) -> Optional[List[float]]:
        """Smart embedding: local model > API > TF-IDF fallback"""
        # Try local sentence-transformers first (best quality, zero cost)
        model = self._get_local_model()
        if model:
            try:
                vec = model.encode(text, normalize_embeddings=True)
                self.dim = len(vec)
                return vec.tolist()
            except Exception:
                pass

        # Try API
        try:
            import urllib.request
            config = get_ai_config()
            api_key = config["api_key"]
            base_url = config["base_url"].rstrip("/")

            # OpenAI embeddings
            url = f"{base_url}/embeddings"
            payload = json.dumps({
                "model": "text-embedding-3-small",
                "input": text,
                "encoding_format": "float",
            }).encode("utf-8")
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            vec = data["data"][0]["embedding"]
            if len(vec) != self.dim:
                self.dim = len(vec)
            return vec
        except Exception as e:
            # 静默降级到本地
            self._api_available = False
            return None

    def _call_embedding_api_batch(self, texts: List[str]) -> List[List[float]]:
        try:
            import urllib.request
            config = get_ai_config()
            api_key = config["api_key"]
            base_url = config["base_url"].rstrip("/")

            url = f"{base_url}/embeddings"
            payload = json.dumps({
                "model": "text-embedding-3-small",
                "input": texts,
                "encoding_format": "float",
            }).encode("utf-8")
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
        except Exception:
            raise

    def _local_embed(self, text: str) -> List[float]:
        """本地 TF-IDF → 稀疏向量映射到固定维度"""
        # Tokenize
        tokens = []
        for word in text.lower().split():
            if any('一' <= c <= '鿿' for c in word):
                tokens.extend(list(word))
            else:
                tokens.append(word)

        # TF vector → hash to fixed dim
        vec = [0.0] * self.dim
        if not tokens:
            return vec

        tf = Counter(tokens)
        total = len(tokens) or 1

        for token, count in tf.most_common(self.dim):
            # Hash token to a deterministic position
            h = int(hashlib.md5(token.encode()).hexdigest()[:8], 16)
            idx = h % self.dim
            vec[idx] += count / total

        # Normalize
        norm = math.sqrt(sum(v**2 for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec


# 全局单例
_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service
