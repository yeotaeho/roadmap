# Alembic migrations package
# 로컬 패키지가 설치 패키지를 가릴 때 — context·op 를 sys.modules 에 미리 등록 후 자신으로 복귀

import os
import sys

_THIS_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_PACKAGE_DIR)


def _matches_backend(p: str) -> bool:
    """주어진 sys.path 항목이 backend/ 디렉토리인지 확인(상대·절대 경로 모두)."""
    try:
        return os.path.normpath(os.path.abspath(p)) == os.path.normpath(_BACKEND_DIR)
    except Exception:
        return False


if "alembic.context" not in sys.modules:
    # backend/ 경로를 일시 제거하고 설치된 alembic 하위 모듈을 로드
    _removed = [p for p in sys.path if _matches_backend(p)]
    _new_path = [p for p in sys.path if not _matches_backend(p)]

    if _removed:
        # 자기 자신(로컬 alembic)을 임시 제거
        _self_mod = sys.modules.pop("alembic", None)
        sys.path[:] = _new_path

        try:
            import importlib
            _real = importlib.import_module("alembic")
            importlib.import_module("alembic.context")
            importlib.import_module("alembic.op")
        except Exception:
            pass
        finally:
            # sys.path 복원
            for _p in reversed(_removed):
                sys.path.insert(0, _p)
            # sys.modules["alembic"] 을 로컬 패키지(자기 자신)로 복원
            # — 이렇게 해야 import alembic.env 가 backend/alembic/env.py 를 찾음
            if _self_mod is not None:
                sys.modules["alembic"] = _self_mod

# 로드된 서브모듈을 패키지 속성으로 노출 (from alembic import context 지원)
if "alembic.context" in sys.modules:
    context = sys.modules["alembic.context"]
if "alembic.op" in sys.modules:
    op = sys.modules["alembic.op"]
