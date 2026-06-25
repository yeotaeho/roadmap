# 트렌딩 키워드 결정론 조립 — 키워드 빈도 dict → CLOUD/TICKER(DB 비의존 순수함수)

from __future__ import annotations


def _cloud(recent: dict[str, int], cloud_limit: int) -> list[dict]:
    ordered = sorted(recent.items(), key=lambda kv: (-kv[1], kv[0]))[:cloud_limit]
    return [{"keyword": k, "weight": w, "rank": i + 1} for i, (k, w) in enumerate(ordered)]


def _ticker(
    recent: dict[str, int], prior: dict[str, int], ticker_limit: int, ticker_min_recent: int
) -> list[dict]:
    # 상승 또는 신규(prior 0)만, recent df가 노이즈 컷 이상인 키워드를 추린다.
    items: list[tuple[str, int, int | None]] = []
    for kw, r in recent.items():
        if r < ticker_min_recent:
            continue
        p = prior.get(kw, 0)
        if p == 0:
            items.append((kw, r, None))  # 신규
        else:
            delta = round((r - p) / p * 100)
            if delta > 0:
                items.append((kw, r, delta))
    # 신규(∞) → 큰 델타 → recent df → keyword 사전순.
    items.sort(key=lambda t: (-(float("inf") if t[2] is None else t[2]), -t[1], t[0]))
    out: list[dict] = []
    for i, (kw, _r, delta) in enumerate(items[:ticker_limit]):
        label = "신규" if delta is None else f"+{delta}%"
        out.append({"keyword": kw, "value_label": label, "delta_pct": delta, "rank": i + 1})
    return out


def assemble_keywords(
    recent: dict[str, int],
    prior: dict[str, int],
    cloud_limit: int = 30,
    ticker_limit: int = 12,
    ticker_min_recent: int = 2,
) -> dict:
    """recent/prior 윈도우 키워드 빈도(df) → CLOUD(빈도)·TICKER(상승 델타) 조립(결정론·DB 비의존)."""
    return {
        "cloud": _cloud(recent, cloud_limit),
        "ticker": _ticker(recent, prior, ticker_limit, ticker_min_recent),
    }
