"""MSIT 수집 워터마크 — URL 쿼리 순서 변화에 강한 비교 + (게시일, 안정 ID) 튜플.

Bronze `raw_economic_data.source_url` 은 수집 시점 문자열 그대로 저장되므로,
증분 수집 시 비교만 정규화하고 저장 값을 강제로 바꾸지는 않는다
(UniqueConstraint on source_url 과의 호환).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def normalize_msit_url(url: str) -> str:
    """쿼리 키 알파벳 순 정렬, 빈 값 제거, 호스트·경로 소문자(스킴·호스트·경로만).

    fragment(#) 는 제거한다.
    """
    if not url or not url.strip():
        return ""
    p = urlparse(url.strip())
    host = (p.hostname or "").lower()
    netloc = host
    if p.port and not ((p.scheme == "http" and p.port == 80) or (p.scheme == "https" and p.port == 443)):
        netloc = f"{host}:{p.port}"
    if p.username:
        auth = p.username
        if p.password:
            auth = f"{auth}:{p.password}"
        netloc = f"{auth}@{netloc}"

    path = (p.path or "/").rstrip("/") or "/"
    if path != "/":
        path = path.lower()

    qs = parse_qs(p.query, keep_blank_values=False)
    flat: list[tuple[str, str]] = []
    for k in sorted(qs.keys()):
        for v in qs[k]:
            if v is None or v == "":
                continue
            flat.append((k, v))
    query = urlencode(flat, doseq=True)
    return urlunparse((p.scheme.lower(), netloc, path, "", query, ""))


def parse_ntt_seq_no_from_url(url: str) -> int | None:
    """view/list URL 쿼리의 nttSeqNo 정수."""
    vals = parse_qs(urlparse(url).query).get("nttSeqNo")
    raw = vals[0] if vals else None
    if not raw or not str(raw).isdigit():
        return None
    return int(raw)


def watermark_tuple(
    published_at: datetime | None,
    stable_id: str | int | None,
) -> tuple[Any, ...]:
    """로그·비교용 정렬 가능 튜플 (None 은 일관된 플레이스홀더)."""
    sid: Any = stable_id
    if isinstance(sid, str) and sid.isdigit():
        sid = int(sid)
    pub = published_at.isoformat() if published_at else None
    return (pub, sid)


def row_ntt_seq_no(row: dict[str, Any]) -> int | None:
    """정규화 row dict 에서 nttSeqNo (메타 주입 또는 URL 파싱)."""
    v = row.get("ntt_seq_no")
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.isdigit():
        return int(v)
    u = row.get("url")
    if isinstance(u, str):
        return parse_ntt_seq_no_from_url(u)
    return None


def bbs_row_matches_watermark(
    row: dict[str, Any],
    *,
    last_norm_url: str | None,
    last_ntt: int | None,
    last_published_at: datetime | None,
) -> bool:
    """목록의 한 행이 DB 최신 건과 동일(증분 중단 지점)인지."""
    row_url = row.get("url")
    if not isinstance(row_url, str):
        return False
    row_norm = normalize_msit_url(row_url)
    if last_norm_url and row_norm == last_norm_url:
        return True
    row_ntt = row_ntt_seq_no(row)
    row_pub = row.get("published_at")
    if (
        last_ntt is not None
        and row_ntt is not None
        and row_ntt == last_ntt
        and last_published_at is not None
        and isinstance(row_pub, datetime)
        and row_pub == last_published_at
    ):
        return True
    return False
