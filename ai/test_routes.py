"""
FastAPI 앱의 등록된 라우트 확인 스크립트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

from main import app

print("=" * 60)
print("등록된 라우트 목록:")
print("=" * 60)

# 모든 라우트 출력
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        methods = ', '.join(sorted(route.methods))
        print(f"{methods:15} {route.path}")

print("=" * 60)
print(f"총 {len([r for r in app.routes if hasattr(r, 'path')])}개의 라우트가 등록되었습니다.")
print("=" * 60)

# 뉴스 관련 라우트만 필터링
news_routes = [r for r in app.routes if hasattr(r, 'path') and '/news' in r.path]
if news_routes:
    print("\n뉴스 관련 라우트:")
    for route in news_routes:
        methods = ', '.join(sorted(route.methods))
        print(f"  {methods:15} {route.path}")
else:
    print("\n⚠️  뉴스 관련 라우트가 등록되지 않았습니다!")

