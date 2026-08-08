"""
蜂鸣器驱动模块

使用 ESP32 的 PWM 驱动板载蜂鸣器 MLT-5020。
蜂鸣器连接在 GPIO25，经 NPN 晶体管 MMSS8050 驱动，高电平使能。
"""

from machine import Pin, PWM
import time
from hardware_config import BUZZER_PIN, NOTE_FREQS, DEFAULT_NOTE_DURATION


class Buzzer:
    """蜂鸣器驱动类"""

    def __init__(self, pin: int = BUZZER_PIN):
        self._pin = Pin(pin, Pin.OUT)
        self._pwm = None

    def _start_pwm(self, freq: int, duty: int = 205):
        """
        启动指定频率的 PWM。
        duty 范围 0~1023，默认 205 约等于 20% 占空比，
        用于降低蜂鸣器电流，避免 USB 供电电压跌落导致断连。
        """
        if self._pwm:
            self._pwm.deinit()
        self._pwm = PWM(self._pin, freq=freq, duty=duty)

    def stop(self):
        """停止蜂鸣器发声"""
        if self._pwm:
            self._pwm.deinit()
            self._pwm = None
        self._pin.value(0)

    def play_note(self, freq: int, duration: float = DEFAULT_NOTE_DURATION):
        """
        播放单个音符，带 PWM 软启动。

        启动时占空比从较低值逐步增加到目标值，
        减小蜂鸣器启动瞬间的电流尖峰，缓解 USB 供电压力。

        Args:
            freq: 频率（Hz）
            duration: 持续时间（秒）
        """
        if freq <= 0:
            return

        target_duty = 205  # 约 20% 占空比
        start_duty = 50    # 约 5% 占空比
        steps = 10
        step_time = 0.005  # 每步 5ms

        self._start_pwm(freq, duty=start_duty)
        for i in range(1, steps + 1):
            duty = start_duty + (target_duty - start_duty) * i // steps
            self._pwm.duty(duty)
            time.sleep(step_time)

        remaining = duration - steps * step_time
        if remaining > 0:
            time.sleep(remaining)

        self.stop()

    def play_tone(self, name: str, duration: float = DEFAULT_NOTE_DURATION):
        """
        按名称播放音符

        Args:
            name: 音符名称，如 'do', 're', 'mi' 等
            duration: 持续时间（秒）
        """
        freq = NOTE_FREQS.get(name)
        if freq:
            self.play_note(freq, duration)

    def play_melody(self, notes: list, duration: float = DEFAULT_NOTE_DURATION):
        """
        播放旋律

        Args:
            notes: 音符名称列表，例如 ['do', 're', 'mi']
            duration: 每个音符持续时间（秒）
        """
        for note in notes:
            self.play_tone(note, duration)
            time.sleep(0.05)  # 音符间短暂停顿


# 模块级便捷函数
def play_note(freq: int, duration: float = DEFAULT_NOTE_DURATION):
    """播放单个音符"""
    b = Buzzer()
    b.play_note(freq, duration)


def play_tone(name: str, duration: float = DEFAULT_NOTE_DURATION):
    """按名称播放音符"""
    b = Buzzer()
    b.play_tone(name, duration)
