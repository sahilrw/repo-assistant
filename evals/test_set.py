"""Retrieval eval: (question -> file that should be retrieved) pairs over psf/requests.

recall_at_k(retrieve_fn) measures how often the expected file lands in the top-k,
so retrieval changes can be compared before/after.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


EVAL_SET = [
    {"q": "where is connection retry logic configured?", "expect": "adapters.py"},
    {"q": "how are authentication handlers defined?", "expect": "auth.py"},
    {"q": "where is the Session object defined?", "expect": "sessions.py"},
    {"q": "how is a Response object built?", "expect": "models.py"},
    {"q": "where are the top-level verbs like get, post, and patch exposed?", "expect": "api.py"},
    {"q": "how does the library parse or handle cookies?", "expect": "cookies.py"},
    {"q": "where are custom exception types like ConnectionError declared?", "expect": "exceptions.py"},
    {"q": "how does requests handle SSL certificate verification or find its bundle?", "expect": "certs.py"},
    {"q": "where are status code lookups and the codes dictionary configured?", "expect": "status_codes.py"},
    {"q": "where are internal utility functions like proxy_bypass or urlparse defined?", "expect": "utils.py"},
]


def recall_at_k(retrieve_fn, k: int = 3) -> float:
    hits = 0
    for ex in EVAL_SET:
        results = retrieve_fn(ex["q"])[:k]

        paths = [metadata["path"] for _, _, metadata in results]

        if any(path.endswith(ex["expect"]) for path in paths):
            hits += 1

    return hits / len(EVAL_SET)

if __name__ == "__main__":
    from src.rag import retrieve
    score = recall_at_k(retrieve, k=3)
    print(f"\n=========================================")
    print(f" Baseline Vector Recall@3: {score * 100:.1f}%")
    print(f"=========================================\n")