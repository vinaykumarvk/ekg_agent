from dataclasses import dataclass

@dataclass
class Intent:
    route: str = "hybrid"  # "kg"|"vector"|"hybrid"
    hops: int = 1
    top_k: int = 6

def clarify_intent(q: str) -> Intent:
    t = q.lower()
    if any(k in t for k in ["kra", "ytd", "relationship", "maker-checker", "edge", "node"]):
        return Intent(route="kg", hops=1, top_k=6)
    if any(k in t for k in ["overview", "compare", "explain", "pros", "cons"]):
        return Intent(route="vector", hops=1, top_k=8)
    return Intent(route="hybrid", hops=2, top_k=8)
