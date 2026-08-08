"""
数字钢琴核心逻辑

- 7 个音符键对应 do-re-mi-fa-sol-la-si
- 2 个八度键控制低/中/高八度
- LED 反馈当前八度：低八度绿灯、高八度红灯、中八度熄灭
"""

from buzzer import Buzzer
from buttons import ButtonManager
from leds import LEDManager
from hardware_config import NOTE_FREQS, OCTAVE_MULTIPLIERS, DEFAULT_NOTE_DURATION


class Piano:
    """数字钢琴类"""

    def __init__(self):
        self.buzzer = Buzzer()
        self.buttons = ButtonManager()
        self.leds = LEDManager()

        # 当前八度：-1=低八度，0=中八度，1=高八度
        self._octave = 0

    def _update_octave_led(self):
        """根据当前八度更新 LED"""
        if self._octave < 0:
            # 低八度：红灯亮
            self.leds.green.off()
            self.leds.red.on()
        elif self._octave > 0:
            # 高八度：绿灯亮
            self.leds.green.on()
            self.leds.red.off()
        else:
            # 中八度：全灭
            self.leds.all_off()

    def _shift_octave(self, direction: str):
        """
        切换八度。
        direction: 'down' 或 'up'
        按下低八度键状态 -1，按下高八度键状态 +1，限制在 [-1, 1]。
        """
        if direction == 'down':
            self._octave = max(self._octave - 1, -1)
        elif direction == 'up':
            self._octave = min(self._octave + 1, 1)

        self._update_octave_led()
        print(f"八度切换: {self._octave_to_name()}")

    def _octave_to_name(self) -> str:
        if self._octave == -1:
            return "低八度"
        elif self._octave == 1:
            return "高八度"
        return "中八度"

    def _play_note(self, note: str):
        """播放指定音符（根据当前八度）"""
        base_freq = NOTE_FREQS.get(note)
        if base_freq is None:
            return

        freq = int(base_freq * OCTAVE_MULTIPLIERS[self._octave])
        print(f"播放 {note} ({freq} Hz) - {self._octave_to_name()}")
        self.buzzer.play_note(freq, DEFAULT_NOTE_DURATION)

    def run(self):
        """主循环：持续扫描按键并播放音符"""
        print("数字钢琴已启动")
        print("7 个音符键: do re mi fa sol la si")
        print("八度键：低八度/高八度")
        self._update_octave_led()

        # 启动提示：绿色 LED 闪烁 1 次
        self.leds.green.on()
        import time
        time.sleep(0.2)
        self.leds.green.off()

        while True:
            # 扫描音符键
            pressed_notes = self.buttons.scan_notes()
            for note in pressed_notes:
                self._play_note(note)

            # 扫描八度键
            octave_cmd = self.buttons.scan_octave()
            if octave_cmd:
                self._shift_octave(octave_cmd)

            # 短暂延时，降低 CPU 占用和按键抖动
            import time
            time.sleep(0.05)
