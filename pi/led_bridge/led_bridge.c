/*
 * led_bridge — 상주 프로세스로 WS2812 24구를 렌더링한다.
 *
 * 이미 검증된 rpi_ws281x 의 pi5 브랜치 (libws2811.a, ws2811.h) 를 그대로 링크해서
 * 쓴다. 파이썬 바인딩은 전혀 쓰지 않는다 — led_controller.py 는 매 프레임(60fps)
 * 계산한 24개 픽셀의 RGB 값을 이 프로세스의 stdin으로 한 줄씩 흘려보내고,
 * 여기서는 그 값을 그대로 ws2811_render() 에 넘기기만 한다.
 *
 * 프로토콜
 *   한 줄에 "r,g,b,r,g,b,...,r,g,b\n" (LED_COUNT * 3 개의 0~255 정수, 콤마 구분)
 *   파싱에 실패한 줄은 무시하고 다음 줄을 기다린다 (죽지 않음).
 *   stdin이 닫히거나(EOF) SIGINT/SIGTERM을 받으면 검정으로 끄고 깨끗이 종료한다.
 *
 * 밝기
 *   led_controller.py 가 무지개 회전/음량 연동/호흡 등을 전부 계산해서
 *   "최종" RGB 값(0~255)을 이미 만들어 보낸다. 그래서 여기 BRIGHTNESS는
 *   추가 감쇠 없이 255(패스스루)로 고정한다. 밝기를 바꾸고 싶으면
 *   led_controller.py 의 STYLE 딕셔너리를 고치는 게 맞다.
 *
 * 빌드 (Makefile 이 자동으로 해줌, 수동으로 하려면):
 *   gcc led_bridge.c -o led_bridge -I<rpi_ws281x_repo> -L<rpi_ws281x_repo> \
 *       -lws2811 -lm -lpthread
 *
 * 실행 전제조건: rp1_ws281x_pwm 커널 모듈 로드 + dtoverlay + pinctl 이 먼저
 * 되어 있어야 한다 (led_controller.py 의 _ensure_kernel_driver() 가 이 프로세스를
 * 띄우기 직전에 자동으로 해준다. 수동 실행 시 pi/led_setup.sh 참고).
 * 하드웨어 레지스터를 직접 건드리므로 root 권한이 필요하다.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

#include "ws2811.h"

#define TARGET_FREQ  WS2811_TARGET_FREQ
#define GPIO_PIN     12
#define DMA          10
#define LED_COUNT    24
#define STRIP_TYPE   WS2811_STRIP_GRB
#define BRIGHTNESS   255   /* 패스스루. 실제 밝기는 파이썬이 계산해서 보냄 */

static ws2811_t ledstring = {
    .freq = TARGET_FREQ,
    .dmanum = DMA,
    .channel = {
        [0] = {
            .gpionum = GPIO_PIN,
            .invert = 0,
            .count = LED_COUNT,
            .strip_type = STRIP_TYPE,
            .brightness = BRIGHTNESS,
        },
        [1] = {0},
    },
};

static volatile sig_atomic_t g_stop = 0;

static void handle_signal(int sig) {
    (void)sig;
    g_stop = 1;
}

static void blackout(void) {
    for (int i = 0; i < LED_COUNT; i++) {
        ledstring.channel[0].leds[i] = 0;
    }
    ws2811_render(&ledstring);
}

static int clamp_byte(int v) {
    if (v < 0) return 0;
    if (v > 255) return 255;
    return v;
}

int main(void) {
    signal(SIGINT, handle_signal);
    signal(SIGTERM, handle_signal);

    ws2811_return_t ret = ws2811_init(&ledstring);
    if (ret != WS2811_SUCCESS) {
        fprintf(stderr, "led_bridge: ws2811_init 실패 (code %d)\n", ret);
        fprintf(stderr, "led_bridge: 커널 모듈/dtoverlay/pinctl 이 먼저 됐는지 확인하세요 "
                         "(led_setup.sh 참고)\n");
        return 1;
    }
    fprintf(stderr, "led_bridge: 준비 완료 (gpio=%d dma=%d count=%d)\n",
            GPIO_PIN, DMA, LED_COUNT);
    fflush(stderr);

    char line[1024];
    while (!g_stop && fgets(line, sizeof(line), stdin) != NULL) {
        int values[LED_COUNT * 3];
        int n = 0;
        char *tok = strtok(line, ",\n");
        while (tok != NULL && n < LED_COUNT * 3) {
            values[n++] = atoi(tok);
            tok = strtok(NULL, ",\n");
        }
        if (n != LED_COUNT * 3) {
            /* 한 프레임이 깨졌으면 무시하고 다음 줄을 기다린다 */
            continue;
        }

        for (int i = 0; i < LED_COUNT; i++) {
            int r = clamp_byte(values[i * 3 + 0]);
            int g = clamp_byte(values[i * 3 + 1]);
            int b = clamp_byte(values[i * 3 + 2]);
            ledstring.channel[0].leds[i] = ((ws2811_led_t)r << 16)
                                          | ((ws2811_led_t)g << 8)
                                          | (ws2811_led_t)b;
        }

        ret = ws2811_render(&ledstring);
        if (ret != WS2811_SUCCESS) {
            fprintf(stderr, "led_bridge: ws2811_render 실패 (code %d)\n", ret);
            break;
        }
    }

    blackout();
    ws2811_fini(&ledstring);
    fprintf(stderr, "led_bridge: 종료\n");
    return 0;
}
