# 배포 인프라 작업 기록 (Audit Trail)

## 2026-07-11 — wepon.kr 프로덕션 첫 배포 — Vultr 단일 인스턴스 + GHCR CI/CD + HTTPS
- **무엇** — 로컬 전용이던 풀스택을 Vultr 서울 인스턴스(vc2-1c-2gb, $10/월)에 첫 프로덕션 배포. GitHub Actions가 api·web 이미지를 GHCR에 빌드·푸시하고 SSH로 compose 재기동하는 CI/CD 구축, nginx TLS 리버스 프록시로 https://wepon.kr 가동.
- **왜** — 배포 요구(평시 저비용·트래픽 비례)에 단일 VM + docker-compose가 최적. DB(Neon)·Redis(Upstash)가 이미 외부라 앱 컨테이너만 올리면 되는 구조. 구글 OAuth가 IP 리다이렉트 URI를 거부해 도메인(wepon.kr, 가비아)+Let's Encrypt HTTPS 전환까지 포함.
- **어디** — [deploy/docker-compose.yml](docker-compose.yml)(nginx·web·api·worker 4컨테이너, api 헬스체크·mem_limit) · [deploy/nginx.conf](nginx.conf)(80→443 리다이렉트·www→apex 통합·/api 프록시·SSE 버퍼링 off) · [.github/workflows/deploy.yml](../.github/workflows/deploy.yml)(main push 트리거, PUBLIC_ORIGIN 빌드타임 베이크) · [www.yeotaeho.kr/Dockerfile](../www.yeotaeho.kr/Dockerfile)(Next 16 standalone 멀티스테이지) · login/signup/OAuth 콜백 5페이지 localhost 하드코딩 제거. 커밋 ff521d3·3bf1fd4·8dfa38f.
- **검증** — compose config·워크플로우 YAML 파싱 통과. code-reviewer 1차 리뷰에서 HIGH 1건(OAuth 콜백 3종 localhost 하드코딩 → 프로덕션 로그인 단절) 발견·즉시 수정. 배포 후 컨테이너 4종 Up(api healthy)·https 200·HTTP→HTTPS 301·api /health healthy·카카오/네이버/구글 소셜 로그인 실테스트 통과·certbot 갱신 dry-run 성공(webroot+nginx reload hook).
- **후속** — 이미지 :latest 고정 → sha 핀닝+롤백 게이트 도입 검토. worker 의 full uvicorn 대신 경량 스케줄러 엔트리포인트 검토. Codex 2차 리뷰 미실행(세션에 커맨드 부재) — 필요 시 `/codex:review --base 2a1396a --scope branch`.
