"""
呼吸灯 - 按键控制
KEY1 (GPIO35): 按下释放 → 红色LED1 呼吸，周期 2s
KEY2 (GPIO34): 按下释放 → 绿色LED1 呼吸，周期 3s
KEY1+KEY2 同时: 按下释放 → 红绿双灯呼吸，周期 5s，相位差 π

LED: 共阳低电平点亮
红色LED1 = GPIO33, 绿色LED1 = GPIO32
PWM: 1kHz, 10-bit (0-1023), duty=1023 灭, duty=0 最亮
"""

import math
import time
from machine import Pin, PWM

# ── 硬件初始化 ──
KEY1 = Pin(35, Pin.IN)   # 外部上拉，按下=0
KEY2 = Pin(34, Pin.IN)

RED = PWM(Pin(33), freq=1000, duty=1023)    # 初始全灭（共阳）
GREEN = PWM(Pin(32), freq=1000, duty=1023)

# ── 模式定义 ──
MODE_NONE = 0
MODE_RED = 1      # 仅红色，周期2s
MODE_GREEN = 2    # 仅绿色，周期3s
MODE_BOTH = 3     # 红绿双灯，周期5s，相位差π

# ── 常量 ──
DEBOUNCE_MS = 30               # 消抖时间
CO_PRESS_WINDOW_MS = 300       # 同时按下判定窗口

# ── 工具函数 ──
def breathing_brightness(t_ms, period_s, phase_rad=0.0):
    """亮度 0.0~1.0"""
    angle = 2 * math.pi * (t_ms / 1000.0) / period_s + phase_rad
    return 0.5 * (1 - math.cos(angle))

def brightness_to_duty(brightness):
    """共阳反转: brightness 0=灭->duty 1023, 1=最亮->duty 0"""
    return int(1023 * (1.0 - brightness))

# ── 按键状态 ──
# 消抖状态机: 每个键追踪最后稳定电平和稳定时间
k1_stable = 1      # 当前稳定值
k2_stable = 1
k1_last_change = 0  # 上次电平变化时刻
k2_last_change = 0

# 按键释放事件队列 (up_time_ms, key_id)
# key_id: 1=KEY1, 2=KEY2
release_events = []

def debounce_read(pin, stable_val, last_change):
    """读取带消抖的按键状态。返回 (new_stable_val, new_last_change, edge_event)。
    edge_event: None 无事件, 'down' 下降沿, 'up' 上升沿"""
    raw = pin.value()
    now = time.ticks_ms()

    if raw != stable_val:
        # 电平变化了
        if last_change == 0:
            # 第一次检测到变化，记录时间
            return (stable_val, now, None)
        elif time.ticks_diff(now, last_change) >= DEBOUNCE_MS:
            # 消抖时间已过，确认变化
            edge = 'down' if raw == 0 else 'up'
            return (raw, 0, edge)
        else:
            # 消抖中，保持原值
            return (stable_val, last_change, None)
    else:
        # 没变化，重置计时
        return (stable_val, 0, None)


# ── 主循环 ──
current_mode = MODE_NONE
prev_mode = MODE_NONE
mode_start_ms = time.ticks_ms()

print("Breathing LED ready.")
print("KEY1(GPIO35) -> Red LED(GPIO33) 2s period")
print("KEY2(GPIO34) -> Green LED(GPIO32) 3s period")
print("Both -> Red+Green 5s period, phase pi")

while True:
    now = time.ticks_ms()

    # ── 按键消抖 ──
    k1_stable, k1_last_change, k1_edge = debounce_read(KEY1, k1_stable, k1_last_change)
    k2_stable, k2_last_change, k2_edge = debounce_read(KEY2, k2_stable, k2_last_change)

    if k1_edge == 'up':
        release_events.append((now, 1))
    if k2_edge == 'up':
        release_events.append((now, 2))

    # ── 处理释放事件 ──
    if len(release_events) >= 2:
        t1, id1 = release_events.pop(0)
        t2, id2 = release_events.pop(0)
        if id1 != id2 and abs(time.ticks_diff(t1, t2)) <= CO_PRESS_WINDOW_MS:
            # 两键在窗口内都释放了 → 同时按下
            current_mode = MODE_BOTH
        else:
            # 不满足同时条件，把两个都当单独事件（以更晚的为准）
            later = id1 if time.ticks_diff(t1, t2) > 0 else id2
            current_mode = MODE_RED if later == 1 else MODE_GREEN
    elif len(release_events) == 1:
        # 只有一个事件，等一小段时间看有没有第二个
        t_ev, id_ev = release_events[0]
        if time.ticks_diff(now, t_ev) > CO_PRESS_WINDOW_MS:
            # 超时了，没有第二个事件
            release_events.pop(0)
            current_mode = MODE_RED if id_ev == 1 else MODE_GREEN

    # ── 模式切换 ──
    if current_mode != prev_mode:
        mode_start_ms = now
        prev_mode = current_mode
        # 关掉不相关的灯
        if current_mode == MODE_RED:
            GREEN.duty(1023)
        elif current_mode == MODE_GREEN:
            RED.duty(1023)

    # ── 呼吸灯更新 ──
    elapsed = time.ticks_diff(now, mode_start_ms)

    if current_mode == MODE_RED:
        b = breathing_brightness(elapsed, 2.0)
        RED.duty(brightness_to_duty(b))

    elif current_mode == MODE_GREEN:
        b = breathing_brightness(elapsed, 3.0)
        GREEN.duty(brightness_to_duty(b))

    elif current_mode == MODE_BOTH:
        b_red = breathing_brightness(elapsed, 5.0, 0.0)
        b_green = breathing_brightness(elapsed, 5.0, math.pi)
        RED.duty(brightness_to_duty(b_red))
        GREEN.duty(brightness_to_duty(b_green))

    # else MODE_NONE: 保持原状态不变

    time.sleep_ms(10)  # 100Hz 刷新
