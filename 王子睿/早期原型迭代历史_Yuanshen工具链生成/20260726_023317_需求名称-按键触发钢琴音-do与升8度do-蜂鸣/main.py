"""
main.py — 按键触发钢琴音（do与升8度do）蜂鸣器播放
KEY1(GPIO35): C4=262Hz, KEY2(GPIO34): C5=523Hz
GPIO25 PWM → 蜂鸣器, 300子区间×10ms=3s 钢琴衰减包络
"""

from machine import Pin, PWM
import time

# ---------- 常量 ----------
BUZZER_PIN = 25
KEY1_PIN = 35
KEY2_PIN = 34

C4_FREQ = 262       # Hz, do
C5_FREQ = 523       # Hz, 升8度do

STEPS = 300          # 子区间个数
STEP_MS = 10         # 每子区间时长 ms
TOTAL_S = STEPS * STEP_MS / 1000  # =3.0s

# ---------- 钢琴衰减包络 ----------
# 快速起振 + 逐渐衰减，模拟真实钢琴单音
# attack: 前 3 个子区间快速上升到峰值
# decay/sustain/release: 剩余子区间指数衰减
def piano_envelope():
    n = STEPS
    env = []
    attack_steps = max(1, n // 100)  # 3 steps
    peak = 1023  # 10-bit PWM 最大值

    for i in range(n):
        if i < attack_steps:
            # 线性起振 0 → peak
            val = int(peak * (i + 1) / attack_steps)
        else:
            # 指数衰减: peak * exp(-k*(i - attack_steps))
            # 衰减到约 peak*0.05 在末尾
            t = (i - attack_steps) / (n - attack_steps)
            val = int(peak * (0.05 ** t))
        env.append(val)
    return env

# ---------- 预计算包络 ----------
ENVELOPE = piano_envelope()

# ---------- 外设初始化 ----------
buzzer = None       # 惰性初始化
key1 = Pin(KEY1_PIN, Pin.IN)
key2 = Pin(KEY2_PIN, Pin.IN)

# ---------- 播放函数 ----------
def _ensure_buzzer():
    global buzzer
    if buzzer is None:
        buzzer = PWM(Pin(BUZZER_PIN), freq=C4_FREQ, duty=0)

def _play_tone(freq):
    """播放单个音，阻塞主循环约3秒"""
    global buzzer
    if buzzer is None:
        buzzer = PWM(Pin(BUZZER_PIN), freq=freq, duty=0)
    else:
        buzzer.freq(freq)
        buzzer.duty(0)

    for duty_val in ENVELOPE:
        buzzer.duty(duty_val)
        time.sleep_ms(STEP_MS)

    # 静音收尾，避免爆音
    buzzer.duty(0)

def play_c4():
    """C4=262Hz — 供软件触发调用"""
    _play_tone(C4_FREQ)

def play_c5():
    """C5=523Hz — 供软件触发调用"""
    _play_tone(C5_FREQ)

# ---------- 按键消抖 ----------
def _wait_release(pin):
    """等待按键释放并消抖"""
    while pin.value() == 0:
        time.sleep_ms(10)

# ---------- 主循环 ----------
def main():
    print("Piano ready: KEY1=C4(262Hz) KEY2=C5(523Hz)")
    _ensure_buzzer()
    buzzer.duty(0)

    while True:
        if key1.value() == 0:
            time.sleep_ms(20)          # 消抖
            if key1.value() == 0:
                print("KEY1 -> C4")
                _play_tone(C4_FREQ)
                _wait_release(key1)

        if key2.value() == 0:
            time.sleep_ms(20)
            if key2.value() == 0:
                print("KEY2 -> C5")
                _play_tone(C5_FREQ)
                _wait_release(key2)

        time.sleep_ms(10)

# 开机自启入口
if __name__ == "__main__":
    main()
