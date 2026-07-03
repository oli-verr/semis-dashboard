"""
Fetch GPU spot prices from RunPod's public GraphQL API (no auth required).
Tracks the GPUs that matter for AI workloads: H100, H200, A100, B200, B300.

Spot price = cheapest available slot (community spot > secure spot > on-demand).
A rising H100 spot price means hyperscalers are absorbing cloud GPU supply.
"""
import requests
import pandas as pd
from datetime import datetime, timezone

_URL = "https://api.runpod.io/graphql"

_QUERY = """
query {
  gpuTypes {
    id
    displayName
    memoryInGb
    communitySpotPrice
    secureSpotPrice
    communityPrice
    securePrice
  }
}
"""

# GPU IDs to track — others (gaming, workstation, MIG slices) are noise
_TRACK_IDS = {
    "NVIDIA H100 80GB HBM3",   # H100 SXM — flagship AI GPU
    "NVIDIA H100 NVL",         # H100 NVL
    "NVIDIA H100 PCIe",        # H100 PCIe — cheaper variant
    "NVIDIA H200",             # H200 SXM — current gen
    "NVIDIA H200 NVL",         # H200 NVL
    "NVIDIA A100-SXM4-80GB",   # A100 SXM — previous gen workhorse
    "NVIDIA A100 80GB PCIe",   # A100 PCIe
    "NVIDIA B200",             # B200 — Blackwell
    "NVIDIA B300 SXM6 AC",     # B300 — Blackwell next-gen
    "NVIDIA GeForce RTX 4090", # RTX 4090 — inference / small-scale
}


def _best_price(*prices) -> float | None:
    """Return the lowest non-None, non-zero price from the candidates."""
    valid = [p for p in prices if p is not None and p > 0]
    return min(valid) if valid else None


def fetch_gpu_prices() -> pd.DataFrame | None:
    """
    Query RunPod for current GPU spot and on-demand prices.
    Returns a DataFrame with one row per tracked GPU, or None on failure.
    """
    try:
        r = requests.post(_URL, json={"query": _QUERY}, timeout=15,
                          headers={"Content-Type": "application/json"})
        r.raise_for_status()
        gpus = r.json()["data"]["gpuTypes"]
    except Exception as e:
        print(f"[runpod] API request failed: {e}")
        return None

    fetch_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = []
    for g in gpus:
        if g["id"] not in _TRACK_IDS:
            continue
        spot = _best_price(g.get("communitySpotPrice"), g.get("secureSpotPrice"))
        on_demand = _best_price(g.get("communityPrice"), g.get("securePrice"))
        rows.append({
            "fetch_date": fetch_date,
            "gpu_id": g["id"],
            "gpu_name": g["displayName"],
            "mem_gb": g.get("memoryInGb"),
            "spot_price": spot,
            "on_demand": on_demand,
        })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    print(f"[runpod] fetched {len(df)} GPU price rows for {fetch_date}")
    return df
