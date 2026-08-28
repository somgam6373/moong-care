"""현재 활성 세션 하나를 전역으로 추적한다 (기기 1대 전제, DB 아님).

Pi가 /api/v1/care/turn 을 호출할 때마다 adopt()로 그 session_id 를 "현재 세션"으로
자동 채택한다 — 그래서 Pi 쪽 코드는 이 개념을 몰라도 된다. front-ui 는 이 모듈을 통해
front 버튼(시작/종료)으로도 같은 "현재 세션"을 조작할 수 있다.
"""

import uuid

_current_session_id: str | None = None


def start_session() -> str:
    global _current_session_id
    _current_session_id = uuid.uuid4().hex
    return _current_session_id


def get_current() -> str | None:
    return _current_session_id


def adopt(session_id: str) -> None:
    global _current_session_id
    _current_session_id = session_id


def clear() -> None:
    global _current_session_id
    _current_session_id = None
