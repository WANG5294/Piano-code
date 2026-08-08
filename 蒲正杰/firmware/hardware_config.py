"""
ESP32 数字钢琴 - 硬件配置

本文件集中管理所有 GPIO 和外设配置。
硬件映射以 hardware_mapping.txt 为准。
"""

# 9 个按键（内部上拉，按下为低电平）
# 7 个音符键 + 2 个八度切换键
NOTE_PINS = [
    5,    # do
    12,   # re
    14,   # mi
    18,   # fa
    19,   # sol
    21,   # la
    22,   # si
]

# 八度切换键（GPIO34/GPIO35 为输入-only 引脚，无内部上拉，需要外部上拉）
OCTAVE_DOWN_PIN = 35   # 低八度
OCTAVE_UP_PIN = 34     # 高八度

# LED（低电平点亮）
GREEN_LED_PIN = 32   # LED2，高八度时亮
RED_LED_PIN = 33     # LED3，低八度时亮

# 蜂鸣器（PWM，高电平使能）
BUZZER_PIN = 25      # B1，经 MMSS8050 驱动

# 中八度音符频率（单位：Hz）
NOTE_FREQS = {
    'do': 262,
    're': 294,
    'mi': 330,
    'fa': 349,
    'sol': 392,
    'la': 440,
    'si': 494,
}

# 八度倍数：低八度 0.5，中八度 1.0，高八度 2.0
OCTAVE_MULTIPLIERS = {
    -1: 0.5,
    0: 1.0,
    1: 2.0,
}

# 默认音符持续时间（秒）
DEFAULT_NOTE_DURATION = 0.3
