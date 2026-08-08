"""
按键驱动模块

9 个按键：
- 7 个音符键：GPIO5(do), GPIO12(re), GPIO14(mi), GPIO18(fa), GPIO19(sol), GPIO21(la), GPIO22(si)
- 低八度：GPIO35
- 高八度：GPIO34

音符键使用内部上拉，按下时为低电平。
八度键连接 GPIO34/GPIO35（输入-only，无内部上拉），需要外部上拉电阻，按下时为低电平。
"""

from machine import Pin
from hardware_config import NOTE_PINS, OCTAVE_DOWN_PIN, OCTAVE_UP_PIN


class Button:
    """单个按键驱动类"""

    def __init__(self, pin: int, name: str = "button", pull: bool = True):
        self.name = name
        # GPIO34/GPIO35 为输入-only 引脚，不支持内部上拉
        if pull:
            self._pin = Pin(pin, Pin.IN, Pin.PULL_UP)
        else:
            self._pin = Pin(pin, Pin.IN)
        self._last_state = self._pin.value()

    def is_pressed(self) -> bool:
        """返回当前是否被按下"""
        return self._pin.value() == 0

    def was_pressed(self) -> bool:
        """检测按键是否刚刚被按下（边沿检测）"""
        current = self._pin.value()
        pressed = (self._last_state == 1 and current == 0)
        self._last_state = current
        return pressed

    def read(self) -> int:
        """读取原始 GPIO 值"""
        return self._pin.value()


class ButtonManager:
    """管理所有板载按键"""

    NOTE_NAMES = ['do', 're', 'mi', 'fa', 'sol', 'la', 'si']

    def __init__(self):
        self.notes = [
            Button(pin, name)
            for pin, name in zip(NOTE_PINS, self.NOTE_NAMES)
        ]
        self.octave_down = Button(OCTAVE_DOWN_PIN, "OCT_DOWN", pull=False)
        self.octave_up = Button(OCTAVE_UP_PIN, "OCT_UP", pull=False)

    def scan_notes(self) -> list:
        """扫描音符键，返回刚刚被按下的音符名称列表"""
        pressed = []
        for btn in self.notes:
            if btn.was_pressed():
                pressed.append(btn.name)
        return pressed

    def scan_octave(self) -> str:
        """
        扫描八度切换键。
        返回 'down'、'up' 或 None。
        """
        if self.octave_down.was_pressed():
            return 'down'
        if self.octave_up.was_pressed():
            return 'up'
        return None
