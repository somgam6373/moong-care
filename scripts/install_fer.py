"""FER 의존성 설치 + 검증.

실행:
    python scripts/install_fer.py
    또는  .\\scripts\\install_fer.bat   (윈도우 더블클릭용 래퍼)

하는 일
    1. 가상환경이 활성화되어 있는지 확인
    2. requirements-fer.txt 설치
    3. numpy / opencv 버전이 프로젝트 제약을 지키는지 검증
"""

from __future__ import annotations

import os
import subprocess
import sys

# 윈도우 콘솔에서 한글이 깨지지 않도록
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQ = os.path.join(ROOT, "requirements-fer.txt")

LINE = "=" * 60


def fail(msg: str, *hints: str) -> int:
    print(f"\n[중단] {msg}")
    for h in hints:
        print(f"       {h}")
    print()
    return 1


def check_venv() -> bool:
    """가상환경 안에서 실행 중인지 확인."""
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def install() -> bool:
    cmd = [sys.executable, "-m", "pip", "install", "-r", REQ]
    print(f"  $ {' '.join(cmd)}\n")
    return subprocess.run(cmd).returncode == 0


def verify() -> bool:
    try:
        import cv2
        import mediapipe
        import numpy
        import onnxruntime
        import emotiefflib  # noqa: F401
    except ImportError as exc:
        print(f"  import 실패: {exc}")
        return False

    versions = {
        "numpy": numpy.__version__,
        "opencv": cv2.__version__,
        "onnxruntime": onnxruntime.__version__,
        "mediapipe": mediapipe.__version__,
    }
    for name, ver in versions.items():
        print(f"  {name:<12} {ver}")

    problems = []
    if not numpy.__version__.startswith("1."):
        problems.append("numpy 가 2.x 입니다 (torch/onnxruntime 이 깨집니다)")
    if not cv2.__version__.startswith("4."):
        problems.append("opencv 가 5.x 입니다 (numpy 2 를 요구합니다)")
    if not mediapipe.__version__.startswith("0.10."):
        problems.append("mediapipe 가 0.10.x 가 아닙니다 (mp.solutions 가 없을 수 있습니다)")

    if problems:
        print()
        for p in problems:
            print(f"  [문제] {p}")
        return False

    return True


def main() -> int:
    print(LINE)
    print(" MoongCare - FER 의존성 설치")
    print(LINE)

    if not os.path.exists(REQ):
        return fail(f"requirements-fer.txt 를 찾을 수 없습니다: {REQ}")

    print("\n[1/3] 가상환경 확인")
    if not check_venv():
        return fail(
            "가상환경이 활성화되어 있지 않습니다.",
            "전역 파이썬에 설치하면 프로젝트가 인식하지 못합니다.",
            "",
            "    .venv\\Scripts\\activate",
            "",
            "실행 정책 오류가 나면:",
            "    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass",
        )
    print(f"  {sys.prefix}")

    print("\n[2/3] 패키지 설치")
    if not install():
        return fail("설치 중 오류가 발생했습니다. 위 로그를 확인하세요.")

    print("\n[3/3] 설치 검증")
    if not verify():
        return fail(
            "버전 검증에 실패했습니다.",
            "아래를 실행해 되돌린 뒤 다시 시도하세요.",
            "",
            '    pip install "numpy<2" "opencv-python<5" "opencv-contrib-python<5" "mediapipe==0.10.14"',
        )

    print("\n  OK - 모든 패키지가 정상입니다")
    print(f"\n{LINE}")
    print(" 설치 완료")
    print(LINE)
    print("\n 다음 단계 - 영상을 temp\\ 에 넣고 검증 스크립트를 실행하세요.\n")
    print("     python scripts/fer_check.py temp/test1.mp4 --fps 5\n")
    print(" 자세한 내용: docs/fer.md\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
