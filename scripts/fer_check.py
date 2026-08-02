"""FER(표정 감정 인식) 도입 전 검증 스크립트.

폰으로 찍은 영상을 넣으면
  프레임 추출 -> 얼굴 검출 -> EmotiEffLib 추론 -> 집계
까지 돌려보고, "이 파이프라인이 쓸 만한가"를 판단할 수 있는 수치를 출력한다.

핵심 확인 사항 3가지
  1. 얼굴 검출이 얼마나 자주 실패하는가          (실패율)
  2. neutral 로만 쏠리지 않는가                   (쏠림도)
  3. 감정이 프레임마다 흔들리지 않는가            (안정성)

사용법:
    python scripts/fer_check.py temp/my_video.mp4
    python scripts/fer_check.py temp/my_video.mp4 --fps 3 --model enet_b2_8_best
    python scripts/fer_check.py temp/my_video.mp4 --rotate 90    # 폰 세로 영상이 눕혀 나올 때

필요 패키지:
    pip install emotiefflib mediapipe opencv-python
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

DEFAULT_FPS = 3.0           # 초당 몇 장 뽑을지
DEFAULT_MODEL = "enet_b2_8_best"
DEFAULT_ENGINE = "onnx"     # "onnx" | "torch"
FACE_MARGIN = 0.15          # 검출된 얼굴 박스를 좌우상하로 15% 확장
MIN_DETECTION_CONF = 0.5

# EmotiEffLib 8-class 순서 (라벨을 못 읽어올 때의 폴백)
FALLBACK_LABELS = [
    "Anger", "Contempt", "Disgust", "Fear",
    "Happiness", "Neutral", "Sadness", "Surprise",
]

# EmotiEffLib 라벨 -> 프로젝트 EMOTION_CLASSES 매핑
# (services/emotion_session.py 의 emotion2vec 라벨과 맞춘다)
LABEL_MAP = {
    "Anger": "angry",
    "Contempt": "other",      # emotion2vec 에는 contempt 가 없다
    "Disgust": "disgusted",
    "Fear": "fearful",
    "Happiness": "happy",
    "Neutral": "neutral",
    "Sadness": "sad",
    "Surprise": "surprised",
}


@dataclass
class FrameResult:
    index: int
    timestamp: float
    detected: bool
    scores: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1단계: 영상 -> 프레임
# ---------------------------------------------------------------------------

def extract_frames(video_path: str, target_fps: float, rotate: int, max_frames: int):
    """영상에서 target_fps 간격으로 프레임을 뽑아 (index, timestamp, image) 로 내보낸다."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다: {video_path}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, int(round(src_fps / target_fps)))

    print(f"  원본 {src_fps:.1f}fps / 총 {total}프레임 -> {step}프레임마다 1장 추출")

    rot_map = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }

    idx = 0
    taken = 0
    while taken < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            if rotate in rot_map:
                frame = cv2.rotate(frame, rot_map[rotate])
            yield taken, idx / src_fps, frame
            taken += 1
        idx += 1

    cap.release()


# ---------------------------------------------------------------------------
# 2단계: 프레임 -> 얼굴 crop
# ---------------------------------------------------------------------------

class FaceCropper:
    """MediaPipe 로 얼굴 위치를 찾아 잘라낸다.

    FER 모델은 '얼굴만 꽉 찬 정사각 이미지'를 입력으로 받는다.
    폰으로 찍은 1080x1920 원본을 그대로 넣으면 결과가 의미 없으므로
    이 단계가 반드시 필요하다.
    """

    def __init__(self):
        import mediapipe as mp

        self._detector = mp.solutions.face_detection.FaceDetection(
            model_selection=1,                      # 1 = 2m 이내 근거리용
            min_detection_confidence=MIN_DETECTION_CONF,
        )

    def crop(self, frame_bgr: np.ndarray) -> np.ndarray | None:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._detector.process(rgb)

        if not result.detections:
            return None

        # 가장 신뢰도 높은 얼굴 하나만 사용
        best = max(result.detections, key=lambda d: d.score[0])
        box = best.location_data.relative_bounding_box

        x1 = box.xmin * w
        y1 = box.ymin * h
        bw = box.width * w
        bh = box.height * h

        # 여백 확장 (AffectNet 학습 이미지가 이마/턱을 포함하는 편)
        mx, my = bw * FACE_MARGIN, bh * FACE_MARGIN
        x1, y1 = int(max(0, x1 - mx)), int(max(0, y1 - my))
        x2, y2 = int(min(w, x1 + bw + 2 * mx)), int(min(h, y1 + bh + 2 * my))

        if x2 - x1 < 20 or y2 - y1 < 20:
            return None

        face = frame_bgr[y1:y2, x1:x2]
        return cv2.cvtColor(face, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------------------
# 3단계: 얼굴 crop -> 감정 스코어
# ---------------------------------------------------------------------------

def _softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64).ravel()
    e = np.exp(x - x.max())
    return e / e.sum()


def list_available_models() -> list[str]:
    try:
        from emotiefflib.facial_analysis import get_model_list

        return list(get_model_list())
    except Exception:
        return []


class EmotionScorer:
    """모델/엔진 조합이 실패하면 다른 조합으로 자동 폴백한다.

    EmotiEffLib 저장소에 모든 모델의 ONNX 버전이 올라와 있지는 않아서
    (예: enet_b2_8_best 는 .pt 만 존재) 다운로드가 404 로 실패할 수 있다.
    그럴 때 torch 엔진이나 다른 모델로 넘어간다.
    """

    def __init__(self, model_name: str, engine: str, device: str):
        candidates = self._build_candidates(model_name, engine)
        last_error: Exception | None = None

        for cand_model, cand_engine in candidates:
            try:
                self._fer = self._load(cand_model, cand_engine, device)
            except Exception as exc:  # noqa: BLE001 - 어떤 실패든 다음 후보로
                last_error = exc
                reason = str(exc).split("\n")[0][:90]
                print(f"  [실패] {cand_model} ({cand_engine}) -> {reason}")
                continue

            if (cand_model, cand_engine) != (model_name, engine):
                print(f"  [폴백] {cand_model} ({cand_engine}) 로 대체했습니다.")
            self.model_name = cand_model
            self.engine = cand_engine
            self.labels = self._resolve_labels()
            return

        available = list_available_models()
        hint = f"\n사용 가능한 모델: {available}" if available else ""
        raise RuntimeError(f"모델을 하나도 로딩하지 못했습니다.{hint}") from last_error

    @staticmethod
    def _build_candidates(model_name: str, engine: str) -> list[tuple[str, str]]:
        other = "torch" if engine == "onnx" else "onnx"
        cands = [(model_name, engine), (model_name, other)]
        # 저장소에 ONNX/PT 가 모두 확실히 있는 모델들
        for fallback in ("enet_b0_8_best_vgaf", "enet_b0_8_best_afew", "enet_b2_8"):
            if fallback != model_name:
                cands.append((fallback, engine))
                cands.append((fallback, other))
        return cands

    @staticmethod
    def _load(model_name: str, engine: str, device: str):
        from emotiefflib.facial_analysis import EmotiEffLibRecognizer

        kwargs = {"engine": engine, "model_name": model_name}
        if engine == "torch":
            kwargs["device"] = device
        return EmotiEffLibRecognizer(**kwargs)

    def _resolve_labels(self) -> list[str]:
        """라이브러리 버전마다 속성명이 달라서 방어적으로 찾는다."""
        for attr in ("idx_to_emotion_class", "idx_to_class", "emotion_classes", "classes"):
            val = getattr(self._fer, attr, None)
            if isinstance(val, dict):
                return [val[k] for k in sorted(val)]
            if isinstance(val, (list, tuple)) and val:
                return list(val)
        return list(FALLBACK_LABELS)

    def score(self, face_rgb: np.ndarray) -> dict[str, float]:
        out = self._fer.predict_emotions(face_rgb, logits=True)
        # 버전에 따라 (label, scores) 또는 ([label], [scores]) 를 반환
        raw = out[1] if isinstance(out, tuple) else out
        raw = np.asarray(raw, dtype=np.float64)
        if raw.ndim > 1:
            raw = raw[0]

        probs = _softmax(raw)
        return {label: float(p) for label, p in zip(self.labels, probs)}


# ---------------------------------------------------------------------------
# 4단계: 집계
# ---------------------------------------------------------------------------

def aggregate(results: list[FrameResult], labels: list[str]) -> dict[str, dict[str, float]]:
    """세 가지 집계 방식을 모두 계산해서 비교할 수 있게 한다."""
    hits = [r.scores for r in results if r.detected]
    if not hits:
        return {}

    matrix = np.array([[s.get(l, 0.0) for l in labels] for s in hits])

    mean = matrix.mean(axis=0)

    # 상위 30% 프레임만 평균 (neutral 쏠림 완화용)
    k = max(1, int(len(matrix) * 0.3))
    topk = np.zeros(len(labels))
    for j in range(len(labels)):
        topk[j] = np.sort(matrix[:, j])[-k:].mean()
    topk = topk / topk.sum()

    # neutral 을 제외하고 재정규화
    ni = labels.index("Neutral") if "Neutral" in labels else -1
    wo_neutral = mean.copy()
    if ni >= 0:
        wo_neutral[ni] = 0.0
        total = wo_neutral.sum()
        wo_neutral = wo_neutral / total if total > 0 else wo_neutral

    return {
        "mean": dict(zip(labels, mean)),
        "top30": dict(zip(labels, topk)),
        "mean_without_neutral": dict(zip(labels, wo_neutral)),
    }


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------

def print_bar_table(title: str, scores: dict[str, float]) -> None:
    print(f"\n[{title}]")
    for label, val in sorted(scores.items(), key=lambda kv: -kv[1]):
        bar = "#" * int(round(val * 40))
        mapped = LABEL_MAP.get(label, "?")
        print(f"  {label:<10} ({mapped:<9}) {val:6.3f}  {bar}")


def print_timeline(results: list[FrameResult]) -> None:
    print("\n[프레임별 최상위 감정]")
    for r in results:
        if not r.detected:
            print(f"  t={r.timestamp:5.2f}s  --- 얼굴 검출 실패 ---")
            continue
        top = sorted(r.scores.items(), key=lambda kv: -kv[1])[:2]
        parts = "   ".join(f"{l} {v:.3f}" for l, v in top)
        print(f"  t={r.timestamp:5.2f}s  {parts}")


def print_diagnosis(results: list[FrameResult], agg: dict) -> None:
    total = len(results)
    hits = sum(1 for r in results if r.detected)
    fail_rate = 1 - (hits / total) if total else 1.0

    print("\n" + "=" * 62)
    print("진단")
    print("=" * 62)

    # 1. 얼굴 검출
    print(f"\n1) 얼굴 검출 성공 {hits}/{total}  (실패율 {fail_rate:.0%})")
    if fail_rate > 0.3:
        print("   [문제] 실패율이 높습니다. 조명/거리/각도를 바꿔 다시 찍어보세요.")
        print("          --rotate 옵션이 필요한 영상일 수도 있습니다.")
    elif fail_rate > 0.1:
        print("   [주의] 검출을 놓치는 구간이 있습니다. 실서비스에선 fallback 처리가 필요합니다.")
    else:
        print("   [양호] 검출은 안정적입니다.")

    if not agg:
        print("\n   얼굴을 하나도 못 찾아 이후 분석을 건너뜁니다.")
        return

    mean = agg["mean"]
    neutral = mean.get("Neutral", 0.0)
    top_label, top_val = max(mean.items(), key=lambda kv: kv[1])

    # 2. neutral 쏠림
    print(f"\n2) neutral 평균 {neutral:.3f}")
    if neutral > 0.7:
        print("   [문제] neutral 로 심하게 쏠립니다. 단순 평균 집계로는 감정 신호가 안 잡힙니다.")
        print("          -> 위 [상위 30% 평균] 또는 [neutral 제외] 표를 보세요.")
        print("             그쪽에서 의미 있는 분포가 나오면 집계 방식만 바꾸면 됩니다.")
    elif neutral > 0.5:
        print("   [주의] neutral 비중이 큽니다. 가중치를 낮춰 융합하는 편이 좋습니다.")
    else:
        print("   [양호] 감정이 분산되어 잡힙니다.")

    # 3. 프레임 간 안정성
    hit_scores = [r.scores for r in results if r.detected]
    tops = [max(s.items(), key=lambda kv: kv[1])[0] for s in hit_scores]
    changes = sum(1 for a, b in zip(tops, tops[1:]) if a != b)
    volatility = changes / max(1, len(tops) - 1)

    print(f"\n3) 프레임 간 최상위 감정 변동률 {volatility:.0%}")
    if volatility > 0.6:
        print("   [문제] 프레임마다 결과가 튑니다. 개별 프레임은 신뢰할 수 없습니다.")
        print("          반드시 여러 프레임을 집계해서 쓰세요.")
    else:
        print("   [양호] 예측이 비교적 일관적입니다.")

    # 4. 결론
    print(f"\n4) 최종 판정: {top_label} ({LABEL_MAP.get(top_label, '?')}) {top_val:.3f}")
    usable = fail_rate <= 0.3 and neutral <= 0.7
    if usable:
        print("\n=> 도입해도 좋아 보입니다. services/fer_service.py 로 옮기세요.")
    else:
        print("\n=> 이대로는 붙이기 이릅니다. 위 [문제] 항목부터 해결하세요.")


# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="FER 파이프라인 검증")
    p.add_argument("video", help="분석할 영상 파일 경로 (mp4, mov, webm ...)")
    p.add_argument("--fps", type=float, default=DEFAULT_FPS, help=f"초당 추출 프레임 수 (기본 {DEFAULT_FPS})")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"EmotiEffLib 모델명 (기본 {DEFAULT_MODEL})")
    p.add_argument("--engine", default=DEFAULT_ENGINE, choices=["onnx", "torch"])
    p.add_argument("--device", default="cpu", help="engine=torch 일 때만 사용 (cpu / cuda:0)")
    p.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270], help="프레임 회전 각도")
    p.add_argument("--max-frames", type=int, default=200)
    p.add_argument("--json", default=None, help="프레임별 원시 스코어를 저장할 JSON 경로")
    p.add_argument("--list-models", action="store_true", help="사용 가능한 모델명만 출력하고 종료")
    args = p.parse_args()

    if args.list_models:
        models = list_available_models()
        print("사용 가능한 모델:")
        for m in models or ["(목록을 가져오지 못했습니다)"]:
            print(f"  - {m}")
        return 0

    if not os.path.exists(args.video):
        print(f"파일이 없습니다: {args.video}")
        return 1

    print("=" * 62)
    print(f"FER 검증  |  {os.path.basename(args.video)}")
    print("=" * 62)

    print("\n[1/4] 모델 로딩")
    t0 = time.time()
    scorer = EmotionScorer(args.model, args.engine, args.device)
    cropper = FaceCropper()
    print(f"  {scorer.model_name} ({scorer.engine}) 로딩 완료 - {time.time() - t0:.1f}초")
    print(f"  라벨: {scorer.labels}")

    print("\n[2/4] 프레임 추출 + 얼굴 검출 + 추론")
    results: list[FrameResult] = []
    t1 = time.time()
    for idx, ts, frame in extract_frames(args.video, args.fps, args.rotate, args.max_frames):
        face = cropper.crop(frame)
        if face is None:
            results.append(FrameResult(idx, ts, detected=False))
            continue
        results.append(FrameResult(idx, ts, detected=True, scores=scorer.score(face)))

    elapsed = time.time() - t1
    if not results:
        print("  프레임을 하나도 읽지 못했습니다.")
        return 1

    print(f"  {len(results)}프레임 처리 - {elapsed:.1f}초 "
          f"(프레임당 {elapsed / len(results) * 1000:.0f}ms)")

    print("\n[3/4] 결과")
    print_timeline(results)

    agg = aggregate(results, scorer.labels)
    if agg:
        print_bar_table("전체 평균 (기본 집계)", agg["mean"])
        print_bar_table("상위 30% 프레임 평균", agg["top30"])
        print_bar_table("neutral 제외 후 재정규화", agg["mean_without_neutral"])

    print("\n[4/4] 진단")
    print_diagnosis(results, agg)

    if args.json:
        payload = {
            "video": args.video,
            "model": scorer.model_name,
            "engine": scorer.engine,
            "fps": args.fps,
            "labels": scorer.labels,
            "frames": [
                {"t": round(r.timestamp, 3), "detected": r.detected, "scores": r.scores}
                for r in results
            ],
            "aggregate": agg,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n원시 스코어 저장: {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
