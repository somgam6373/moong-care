#!/bin/bash
# RP1 PWM 커널 모듈을 로드하고 GPIO12를 PWM 핀으로 설정합니다.
#
# 재부팅/전원 재인가마다 다시 실행해야 합니다 (아직 영구 등록이 안 되어 있음).
# led_controller.py 가 C 브릿지를 띄우기 직전에 이 스크립트를 자동으로 호출하므로
# main.py 를 쓰는 정상적인 사용에서는 손으로 실행할 일이 없습니다.
# LED만 따로 확인해보고 싶을 때 수동으로 돌리는 용도입니다.
#
# main.py 는 이미 sudo -E 로 통째로 root 권한으로 돌기 때문에, 이 스크립트
# 자체에는 sudo를 안 붙입니다. 손으로 실행할 땐 sudo 로 실행하세요.

set -e

WS281X_DIR="${MOONG_WS281X_DIR:-$HOME/rpi_ws281x}"
MODULE_DIR="$WS281X_DIR/rp1_ws281x_pwm"
MODULE="$MODULE_DIR/rp1_ws281x_pwm.ko"

if [ "$(id -u)" -ne 0 ]; then
    echo "[led_setup] root 권한이 필요합니다. sudo bash led_setup.sh 로 실행하세요." >&2
    exit 1
fi

if lsmod | grep -q '^rp1_ws281x_pwm'; then
    echo "[led_setup] 커널 모듈 이미 로드됨, 건너뜀"
else
    if [ ! -f "$MODULE" ]; then
        echo "[led_setup] 모듈을 찾을 수 없음: $MODULE" >&2
        echo "[led_setup] MOONG_WS281X_DIR 환경변수로 rpi_ws281x(pi5 브랜치) 경로를 알려주세요." >&2
        exit 1
    fi
    echo "[led_setup] 커널 모듈 로드: $MODULE"
    insmod "$MODULE" pwm_channel=0
fi

cd "$MODULE_DIR"
dtoverlay -d . rp1_ws281x_pwm
pinctrl set 12 a0 pn
echo "[led_setup] 완료"
