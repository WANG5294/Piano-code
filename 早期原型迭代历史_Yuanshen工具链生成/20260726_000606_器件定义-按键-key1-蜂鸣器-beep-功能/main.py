# main.py - key1 触发 beep 440Hz，占空比随时间变化
# y = 10t (0≤t≤0.5), y = 0.6-0.2t (t>0.5), t>3 停止
# KEY1=GPIO35（按下=0，板载上拉），Beep=GPIO25 PWM

from machine import Pin, PWM
import time

KEY1_PIN = 35
BEEP_PIN = 25
FREQ = 440
DEBOUNCE_MS = 20
DUTY_MAX = 1023       # 10-bit
UPDATE_INTERVAL_S = 0.02  # 20ms 更新间隔

pressed = False

def on_key(pin):
    global pressed
    pressed = True

def duty_from_t(t):
    """根据时间 t(秒) 返回占空比 y (0~1)，超出范围返回 None 表示停止"""
    if t < 0:
        return 0.0
    if t <= 0.5:
        y = 10.0 * t
    else:
        y = 0.6 - 0.2 * t
    # y 上限截断为 1.0，负值时停止
    if y > 1.0:
        y = 1.0
    if y <= 0.0:
        return None
    return y

def beep_run():
    global pressed
    buzzer = PWM(Pin(BEEP_PIN), freq=FREQ, duty=0)
    start = time.ticks_ms()
    t = 0.0
    try:
        while True:
            y = duty_from_t(t)
            if y is None:
                break
            duty_val = int(y * DUTY_MAX)
            buzzer.duty(duty_val)
            time.sleep(UPDATE_INTERVAL_S)
            t += UPDATE_INTERVAL_S
    finally:
        buzzer.duty(0)
        buzzer.deinit()
        Pin(BEEP_PIN, Pin.OUT, value=0)

# 初始化按键
key1 = Pin(KEY1_PIN, Pin.IN)
key1.irq(trigger=Pin.IRQ_FALLING, handler=on_key)

print("main.py loaded. Press KEY1 to trigger beep.")

# 主循环：轮询按键标志
if __name__ == '__main__':
    while True:
        if pressed:
            pressed = False
            # 消抖确认
            time.sleep_ms(DEBOUNCE_MS)
            if key1.value() == 0:
                now = time.ticks_ms()
                # 等待按键释放（避免一直触发）
                while key1.value() == 0:
                    time.sleep_ms(10)
                print("KEY1 pressed, starting beep...")
                beep_run()
                print("Beep done.")
        time.sleep_ms(50)
