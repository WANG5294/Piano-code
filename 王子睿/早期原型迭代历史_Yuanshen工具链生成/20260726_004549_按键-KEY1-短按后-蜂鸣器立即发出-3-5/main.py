"""
KEY1 (GPIO35) 短按后，蜂鸣器 (GPIO25) 发出 3.5 秒 440Hz 声音。
占空比随时间变化：
  t < 0.5:  y = t           (线性上升, 0 → 0.5)
  t >= 0.5: y = (3.5-t)/6   (线性下降, 0.5 → 0)
y ∈ [0, 1] 映射到 10-bit PWM duty: 0~1023
"""
from machine import Pin, PWM
import time

# 硬件初始化
KEY1 = Pin(35, Pin.IN)          # 板上 R12 上拉，按下=0
BUZZER_PIN = Pin(25)

# 去抖与消抖参数
DEBOUNCE_MS = 30
CYCLE_MS = 10                    # 主循环间隔
TOTAL_S = 3.5                    # 响铃总时长
FREQ = 440                       # 固定 440Hz
DUTY_MAX = 1023                  # 10-bit PWM

def duty_from_t(t):
    """占空比 y(t): 0 <= t <= 3.5, 返回 0.0 ~ 1.0"""
    if t < 0.5:
        return t                 # 线性上升
    else:
        return (TOTAL_S - t) / 6.0  # 线性下降

def ring():
    """播放 3.5 秒 440Hz 变占空比声音"""
    pwm = PWM(BUZZER_PIN, freq=FREQ, duty=0)
    start = time.ticks_ms()

    while True:
        elapsed_ms = time.ticks_diff(time.ticks_ms(), start)
        t = elapsed_ms / 1000.0

        if t >= TOTAL_S:
            break

        y = duty_from_t(t)
        d = int(y * DUTY_MAX)
        if d > DUTY_MAX:
            d = DUTY_MAX
        if d < 0:
            d = 0

        pwm.duty(d)
        time.sleep_ms(CYCLE_MS)

    pwm.duty(0)
    pwm.deinit()
    BUZZER_PIN.init(Pin.OUT, value=0)

# 主循环
print("等待 KEY1 按下...")
while True:
    if KEY1.value() == 0:
        time.sleep_ms(DEBOUNCE_MS)
        if KEY1.value() == 0:
            # 确认按下，开始响铃
            print("KEY1 按下，开始响铃 3.5s")
            ring()
            print("响铃结束，等待下一次按键...")
    time.sleep_ms(CYCLE_MS)
