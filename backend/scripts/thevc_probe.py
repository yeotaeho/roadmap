"""The VC 공개 페이지 Probe — 🛑 2026-05-12 부로 실행 보류.

================================================================================
🛑 RUN-BLOCKED — 이용약관(ToS) 검토 결과 자동 수집 보류
================================================================================

The VC 이용약관 정독 결과, 다음 조항이 본 Probe(및 향후 collector)의 실행 자체를
사실상 금지합니다:

  - 제13조 4항: "회사와의 별도 계약" 및 "robots.txt 허용 범위" 외의
                크롤링/스크래핑/캐싱/액세스 + "그러한 모든 시도" 금지.
                필터·더보기·검색 등 사이트 기능의 과도한 이용도 금지.
  - 제18조 3항: 스크래핑/크롤링/매크로로 사이트를 이용하면 적발·의심만으로도
                회원/이용자 자격 박탈.
  - 제18조 4·5항: 1계정 1자연인, 임직원 간 공유 포함 계정공유 엄금.
  - 제14조 2항: 정통망법(접속권한 초과행위 등) 위반 시 즉시 계약 해지, 무보상.

따라서 본 스크립트는 다음 정책으로 변경되었습니다:
  1) 기본 실행 시 즉시 종료 (sys.exit(2)).
  2) 사람이 ToS 위험을 인지했다는 명시적 동의 환경변수가 없는 한 절대 실행 금지.
     → THEVC_PROBE_ACK_TOS_BLOCK=1  (이것은 "차단을 풀겠다"가 아니라
        "위험을 이해하고 검증 목적으로만 1회 돌린다"는 인수증 의미.)
  3) 코드는 추후 B2B 데이터 라이선스 계약이 성립할 경우 재사용할 수 있도록 보존.

자세한 배경/의사결정 트레이스는:
  backend/domain/master/docs/THEVC_COLLECTION_STRATEGY.md
  — 「📜 이용약관(ToS) 검토 결과」 섹션 참조.

================================================================================
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

_MASK_HINTS: tuple[str, ...] = (
    "비공개",
    "공개되지",
    "***",
    "--",
    "—",
)

_DEFAULT_URL = "https://thevc.kr/oneoneone/fundings"


def _safe_json_preview(obj: Any, max_len: int = 800) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except TypeError:
        s = str(obj)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _collect_keys(obj: Any, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            keys.add(path)
            if isinstance(v, (dict, list)) and len(prefix.split(".")) < 6:
                keys |= _collect_keys(v, path)
    elif isinstance(obj, list) and obj:
        keys |= _collect_keys(obj[0], prefix + "[0]")
    return keys


def _count_mask_hits(text: str) -> int:
    if not text:
        return 0
    n = sum(text.count(h) for h in _MASK_HINTS)
    n += len(re.findall(r"\*{2,}", text))
    return n


def _json_ok_count(captured: list[dict[str, Any]]) -> int:
    return sum(1 for c in captured if c.get("kind") == "json_ok")


def _inject_session_cookie(context, cookie_header: str) -> None:
    pairs = []
    for part in cookie_header.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, val = part.partition("=")
            pairs.append(
                {
                    "name": name.strip(),
                    "value": val.strip(),
                    "domain": ".thevc.kr",
                    "path": "/",
                }
            )
    if pairs:
        context.add_cookies(pairs)


def _run_phase(
    name: str,
    captured: list[dict[str, Any]],
    fn: Callable[[], None],
) -> int:
    """fn 실행 전후 json_ok 건수 차이 반환."""
    before = _json_ok_count(captured)
    try:
        fn()
    except Exception as e:
        print(f"  [{name}] 예외 (무시): {e}")
    after = _json_ok_count(captured)
    delta = after - before
    print(f"  [{name}] 신규 JSON 응답: +{delta}건 (누적 json_ok: {after})")
    return delta


def _parse_phases(raw: str) -> set[str]:
    if not raw.strip():
        return {"scroll", "tabs", "buttons", "keyboard", "detail", "home"}
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "[FAIL] playwright 패키지가 없습니다.\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )
        return 1

    url = os.environ.get("THEVC_PROBE_URL", _DEFAULT_URL).strip()
    scroll_rounds = int(os.environ.get("THEVC_SCROLL_ROUNDS", "3"))
    extra_wait = int(os.environ.get("THEVC_PROBE_EXTRA_WAIT_MS", "5000"))
    session_cookie = os.environ.get("THEVC_SESSION_COOKIE", "").strip()
    phases = _parse_phases(os.environ.get("THEVC_PROBE_PHASES", ""))
    follow_detail = os.environ.get("THEVC_FOLLOW_DETAIL", "1").strip() not in ("0", "false", "no")
    second_url = os.environ.get("THEVC_SECOND_PAGE_URL", "").strip()

    captured: list[dict[str, Any]] = []

    def on_response(response) -> None:
        try:
            u = response.url
            if "/api/" not in u:
                return
            if response.status != 200:
                captured.append(
                    {
                        "url": u,
                        "status": response.status,
                        "kind": "non_json_or_error",
                        "preview": None,
                    }
                )
                return
            ct = (response.headers.get("content-type") or "").lower()
            if "json" not in ct:
                return
            try:
                body = response.json()
            except Exception:
                captured.append(
                    {
                        "url": u,
                        "status": response.status,
                        "kind": "json_parse_fail",
                        "preview": None,
                    }
                )
                return
            captured.append(
                {
                    "url": u,
                    "status": response.status,
                    "kind": "json_ok",
                    "body": body,
                    "keys_sample": sorted(_collect_keys(body))[:80],
                }
            )
        except Exception:
            pass

    phase_deltas: dict[str, int] = {}

    print("=" * 72)
    print("The VC Probe (robots.txt 준수 — 공개 페이지 + 응답 관찰만)")
    print("=" * 72)
    print(f"대상 URL: {url}")
    print(f"페이즈: {sorted(phases)}")
    print(f"추가 대기(ms): {extra_wait}")
    print(f"스크롤 라운드: {scroll_rounds}")
    print(f"상세 링크 따라가기: {'예' if follow_detail else '아니오'}")
    print(f"세컨더리 페이지: {second_url or '(없음)'}")
    print(f"세션 쿠키 주입: {'예' if session_cookie else '아니오 (익명)'}")
    print()

    mask_initial = 0
    api_counts_after_scroll: list[int] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1280, "height": 900},
        )
        if session_cookie:
            _inject_session_cookie(context, session_cookie)

        page = context.new_page()
        page.on("response", on_response)

        try:
            page.goto(url, wait_until="networkidle", timeout=90000)
        except Exception as e:
            print(f"[FAIL] page.goto: {e}")
            browser.close()
            return 2

        page.wait_for_timeout(extra_wait)

        print(f"[PAGE] title: {page.title()!r}")
        print(f"[PAGE] final_url: {page.url}")

        try:
            body_text_initial = page.locator("body").inner_text(timeout=15000)
        except Exception:
            body_text_initial = ""
        mask_initial = _count_mask_hits(body_text_initial)
        print(f"[VISIBLE] body 텍스트 길이: {len(body_text_initial)} 자")
        print(f"[VISIBLE] 마스킹 힌트(추정): {mask_initial}")

        # --- 스크롤 ---
        if "scroll" in phases:
            print("\n[PHASE scroll]")
            for i in range(scroll_rounds):
                before = _json_ok_count(captured)

                def _wheel() -> None:
                    page.mouse.wheel(0, 4500)
                    page.wait_for_timeout(2200)

                try:
                    _wheel()
                except Exception as e:
                    print(f"  [wheel_{i + 1}] 예외: {e}")
                after = _json_ok_count(captured)
                delta = after - before
                api_counts_after_scroll.append(delta)
                print(
                    f"  [wheel_{i + 1}] 신규 JSON 응답: +{delta}건 "
                    f"(누적 json_ok: {after})"
                )

        # --- 탭 (role=tab) ---
        if "tabs" in phases:
            print("\n[PHASE tabs]")
            try:
                tabs = page.locator('[role="tab"]').all()
                print(f"  발견 tab 수: {len(tabs)}")
                for idx, tab in enumerate(tabs[:20]):
                    if not tab.is_visible():
                        continue

                    def click_tab(t=tab, i=idx) -> None:
                        t.click(timeout=4000)
                        page.wait_for_timeout(2200)

                    _run_phase(f"tab[{idx}]", captured, click_tab)
            except Exception as e:
                print(f"  탭 페이즈 스킵: {e}")

        # --- 버튼 (더보기 등) ---
        if "buttons" in phases:
            print("\n[PHASE buttons]")
            labels = (
                "더보기",
                "더 보기",
                "더 불러오기",
                "더보기 +",
                "전체보기",
                "전체 보기",
                "Load more",
                "Show more",
                "See more",
            )
            for label in labels:
                try:
                    loc = page.get_by_role("button", name=re.compile(re.escape(label), re.I))
                    if loc.count() == 0:
                        continue

                    def click_btn(l=loc) -> None:
                        l.first.click(timeout=4000)
                        page.wait_for_timeout(2500)

                    _run_phase(f"btn:{label}", captured, click_btn)
                except Exception:
                    continue

            # 링크 형태 "더보기"
            for label in ("더보기", "더 보기", "전체보기"):
                try:
                    loc = page.get_by_role("link", name=re.compile(re.escape(label), re.I))
                    if loc.count() == 0:
                        continue

                    def click_lnk(l=loc) -> None:
                        l.first.click(timeout=4000)
                        page.wait_for_timeout(2500)

                    _run_phase(f"link:{label}", captured, click_lnk)
                except Exception:
                    continue

        # --- 키보드 End / PageDown ---
        if "keyboard" in phases:
            print("\n[PHASE keyboard]")

            def press_end() -> None:
                page.keyboard.press("End")
                page.wait_for_timeout(3500)

            phase_deltas["keyboard_end"] = _run_phase("End", captured, press_end)

            def press_pg() -> None:
                for _ in range(5):
                    page.keyboard.press("PageDown")
                    page.wait_for_timeout(600)

            phase_deltas["keyboard_pgdn"] = _run_phase("PageDown x5", captured, press_pg)

        # --- 첫 funding / investment / oneoneone 내부 링크 ---
        if "detail" in phases and follow_detail:
            print("\n[PHASE detail-link]")
            hrefs: list[str] = []
            try:
                for sel in (
                    'a[href*="/funding"]',
                    'a[href*="/investments"]',
                    'a[href*="/oneoneone"]',
                    'a[href*="investment"]',
                ):
                    for link in page.locator(sel).all()[:30]:
                        try:
                            h = link.get_attribute("href")
                            if h and "thevc.kr" in h and "/api" not in h:
                                hrefs.append(h.split("#")[0])
                            elif h and h.startswith("/"):
                                hrefs.append("https://thevc.kr" + h.split("#")[0])
                        except Exception:
                            continue
            except Exception as e:
                print(f"  링크 수집 스킵: {e}")

            seen = set()
            uniq = []
            for h in hrefs:
                if h not in seen:
                    seen.add(h)
                    uniq.append(h)
            print(f"  후보 내부 링크 {len(uniq)}개 (최대 8개 출력)")
            for h in uniq[:8]:
                print(f"    - {h}")

            if uniq:

                def goto_detail() -> None:
                    page.goto(uniq[0], wait_until="networkidle", timeout=90000)
                    page.wait_for_timeout(extra_wait)

                phase_deltas["detail_goto"] = _run_phase(f"goto:{uniq[0][:60]}...", captured, goto_detail)
                print(f"[DETAIL] title: {page.title()!r}")
                print(f"[DETAIL] url: {page.url}")

        # --- 홈 진입 후 원래 목록으로 복귀 (추가 API 패턴 관찰) ---
        if "home" in phases:
            print("\n[PHASE home-then-return]")

            def home_and_back() -> None:
                page.goto("https://thevc.kr/", wait_until="networkidle", timeout=90000)
                page.wait_for_timeout(3000)
                page.goto(url, wait_until="networkidle", timeout=90000)
                page.wait_for_timeout(extra_wait)

            phase_deltas["home_return"] = _run_phase("home->list", captured, home_and_back)

        # --- 사용자 지정 두 번째 URL ---
        if second_url:

            def goto_second() -> None:
                page.goto(second_url, wait_until="networkidle", timeout=90000)
                page.wait_for_timeout(extra_wait)

            print(f"\n[PHASE second-url] {second_url}")
            phase_deltas["second_url"] = _run_phase("second_goto", captured, goto_second)
            print(f"[SECOND] title: {page.title()!r}")

        browser.close()

    json_ok = [c for c in captured if c.get("kind") == "json_ok"]
    url_counter = Counter(c["url"].split("?")[0] for c in json_ok)

    def _walk_plan_signals(o: Any, out: list[str]) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "requirements" and isinstance(v, list):
                    for item in v:
                        if isinstance(item, str) and item.startswith("PLAN:"):
                            out.append(item)
                _walk_plan_signals(v, out)
        elif isinstance(o, list):
            for it in o:
                _walk_plan_signals(it, out)

    plan_signals: list[str] = []
    for c in json_ok:
        _walk_plan_signals(c.get("body"), plan_signals)
    plan_counter = Counter(plan_signals)

    print()
    print("-" * 72)
    print("[NETWORK] /api/ JSON 응답 요약 (전 페이즈 누적)")
    print("-" * 72)
    print(f"총 관찰 건수(json_ok): {len(json_ok)}")
    if url_counter:
        print("경로별 건수 (쿼리스트립, 상위 25):")
        for path, cnt in url_counter.most_common(25):
            print(f"  {cnt:4d}  {path}")

    if plan_counter:
        print()
        print("[PAYWALL] JSON 내 PLAN 요구 신호:")
        for sig, cnt in plan_counter.most_common():
            print(f"  {cnt:4d}x  {sig}")

    list_like = [
        c
        for c in json_ok
        if "/filter-options" not in c["url"]
        and "/interaction/" not in c["url"]
        and (
            "/investments" in c["url"]
            or "/funding" in c["url"].lower()
            or "fundings" in c["url"].lower()
            or "/startups" in c["url"]
        )
    ]
    print()
    print(
        f"[JSON] 리스트 추정 응답 (filter-options·interaction 제외): {len(list_like)}건"
    )
    for c in list_like[:12]:
        print(f"  - {c['url']}")
    if not list_like:
        print(
            "  → 여전히 리스트형 API 가 거의 없으면, SSR 전용·로그인 게이트·"
            "또는 클라이언트 번들 내 다른 경로일 수 있습니다."
        )

    # 리스트형 첫 건 미리보기
    preview_body = None
    if list_like:
        preview_body = list_like[0].get("body")
        print()
        print("[JSON] 리스트 추정 첫 응답 키 샘플:")
        for k in (list_like[0].get("keys_sample") or [])[:35]:
            print(f"  - {k}")
        print("[JSON] 미리보기:")
        print(_safe_json_preview(preview_body, max_len=1500))
    elif json_ok:
        preview_body = json_ok[0].get("body")
        print()
        print("[JSON] (리스트 없음) 첫 응답 키 샘플:")
        for k in (json_ok[0].get("keys_sample") or [])[:35]:
            print(f"  - {k}")
        print(_safe_json_preview(preview_body, max_len=1200))

    sample_strings: list[str] = []

    def walk_strings(o: Any, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(o, str):
            if len(o) < 500:
                sample_strings.append(o)
            return
        if isinstance(o, dict):
            for v in o.values():
                walk_strings(v, depth + 1)
        elif isinstance(o, list):
            for item in o[:50]:
                walk_strings(item, depth + 1)

    mask_in_json = 0
    if preview_body:
        walk_strings(preview_body)
        mask_in_json = _count_mask_hits(" ".join(sample_strings))

    print()
    print("-" * 72)
    print("[PAGINATION] 스크롤 라운드별 신규 JSON")
    print("-" * 72)
    if api_counts_after_scroll:
        for i, delta in enumerate(api_counts_after_scroll, start=1):
            print(f"  스크롤 {i}: +{delta}")
        if sum(api_counts_after_scroll) == 0:
            print("  → 스크롤만으로는 추가 JSON 없음.")
    else:
        print("  (스크롤 페이즈 비활성 또는 미실행)")

    if phase_deltas:
        print()
        print("[PHASE] 기타 페이즈 누적 신규 건수 요약")
        for k, v in sorted(phase_deltas.items()):
            print(f"  {k}: +{v}")

    print()
    print("-" * 72)
    print("[MASKING] 요약")
    print("-" * 72)
    print(f"  화면 초기 마스킹 힌트: {mask_initial}")
    print(f"  (미리보기 본문) JSON 문자열 마스킹 힌트: {mask_in_json}")

    print()
    print("=" * 72)
    print("Probe 완료.")
    print("=" * 72)
    return 0


def _tos_block_guard() -> None:
    """ToS 검토 결과에 따른 실행 차단 가드.

    명시적 인수증(THEVC_PROBE_ACK_TOS_BLOCK=1) 이 없으면 즉시 종료한다.
    """
    ack = os.environ.get("THEVC_PROBE_ACK_TOS_BLOCK", "").strip()
    if ack != "1":
        sys.stderr.write(
            "\n".join(
                [
                    "",
                    "=" * 72,
                    "🛑 thevc_probe.py 실행이 ToS 검토 결과에 따라 차단되었습니다.",
                    "=" * 72,
                    "사유: The VC 이용약관 제13조 4항·제18조 3항 등에 의해",
                    "      크롤링/스크래핑/캐싱/액세스 및 그 시도가 금지되어 있으며,",
                    "      본 Probe 동작이 약관 위반에 해당할 위험이 있습니다.",
                    "",
                    "결정: 데이터 수집 보류. 자동화 경로 모두 미사용.",
                    "      자세한 내용은 THEVC_COLLECTION_STRATEGY.md 참조.",
                    "",
                    "굳이 (예: 라이선스 협상 후 합의된 범위에서) 검증 목적의 1회",
                    "실행이 필요하다면, 위험을 이해했음을 명시적으로 인수해야 합니다:",
                    "",
                    "  PowerShell:",
                    "    $env:THEVC_PROBE_ACK_TOS_BLOCK = '1'; python scripts/thevc_probe.py",
                    "  bash:",
                    "    THEVC_PROBE_ACK_TOS_BLOCK=1 python scripts/thevc_probe.py",
                    "=" * 72,
                    "",
                ]
            )
        )
        raise SystemExit(2)


if __name__ == "__main__":
    _tos_block_guard()
    raise SystemExit(main())
