"""
火车鸣笛音效模拟（远处靠近再远去）
- KEY1 (GPIO35) 短按触发
- 蜂鸣器 B1 (GPIO25) PWM 输出
- 10 秒音效，频率 400→480→400 Hz，占空比 0→50%→0
- 步长 0.01 秒（1000 步）
"""

from machine import Pin, PWM
import time

# --- 硬件定义 ---
BUZZER_PIN = 25
KEY1_PIN = 35

# --- 音效参数 ---
DURATION = 10.0          # 总时长 (秒)
STEP = 0.01              # 步长 (秒)
STEPS = int(DURATION / STEP)  # 1000 步
DUTY_MAX = 1023          # 10-bit 分辨率
MID_T = 5.0              # 中点时刻

# --- 初始化 ---
key1 = Pin(KEY1_PIN, Pin.IN)   # GPIO35 仅输入，板上已有 R12 上拉
buzzer = PWM(Pin(BUZZER_PIN), freq=400, duty=0)


def play_train_horn():
    """播放一次完整的火车鸣笛音效（10 秒）。
       可在主循环中按键触发，也可 REPL 直接调用用于闭环验证。"""
    for i in range(STEPS):
        t = i * STEP  # 当前时刻 (秒)

        # -- 频率: 前半段 400→480, 后半段 480→400 --
        if t < MID_T:
            f = 400.0 + 16.0 * t
        else:
            f = 560.0 - 16.0 * t

        freq = round(f)
        buzzer.freq(freq)

        # -- 占空比: 前半段 0→0.5, 后半段 0.5→0 --
        if t < MID_T:
            d = 0.1 * t
        else:
            d = 1.0 - 0.1 * t

        # 限幅
        if d < 0.0:
            d = 0.0
        elif d > 1.0:
            d = 1.0

        duty_val = int(d * DUTY_MAX)
        buzzer.duty(duty_val)

        time.sleep(STEP)

    # 音效结束，静音
    buzzer.duty(0)


def main():
    """主循环：等待 KEY1 下降沿触发，播放 10 秒音效，期间忽略按键。"""
    print("火车鸣笛音效就绪。短按 KEY1 触发。")

    while True:
        # 等待按键按下（下降沿）
        if key1.value() == 0:
            # 软件消抖
            time.sleep_ms(20)
            if key1.value() == 0:
                print("触发！播放火车鸣笛音效...")
                play_train_horn()
                print("音效结束，等待下一次按键。")
            # 等待按键释放，避免一次按触发多次
            while key1.value() == 0:
                time.sleep_ms(10)

        time.sleep_ms(10)


# 主入口
if __name__ == "__main__":
    main()
