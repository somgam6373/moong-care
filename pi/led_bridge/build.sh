#!/bin/bash
# led_bridge 빌드.
#
# WS281X_DIR 는 rpi_ws281x 의 pi5 브랜치를 클론+빌드해둔 경로입니다.
# (libws2811.a, ws2811.h 가 그 바로 아래 있어야 합니다.)
#
# 사용법:
#   ./build.sh                              # 기본값 ~/rpi_ws281x 사용
#   ./build.sh /다른/경로                    # 경로 직접 지정
#   WS281X_DIR=/다른/경로 ./build.sh         # 환경변수로 지정해도 됨

set -e

WS281X_DIR="${1:-${WS281X_DIR:-$HOME/rpi_ws281x}}"

if [ ! -f "$WS281X_DIR/libws2811.a" ]; then
    echo "libws2811.a 를 찾을 수 없습니다: $WS281X_DIR" >&2
    echo "rpi_ws281x 의 pi5 브랜치를 클론+빌드한 경로를 인자로 넘겨주세요." >&2
    exit 1
fi

cd "$(dirname "$0")"
gcc led_bridge.c -o led_bridge -I"$WS281X_DIR" -L"$WS281X_DIR" -lws2811 -lm -lpthread
echo "빌드 완료: $(pwd)/led_bridge"
