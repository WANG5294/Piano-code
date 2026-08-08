"""
buttons.py - 10 键数字钢琴按键扫描模块（W3 边沿触发优化版）

硬件上下文：
- 开发板：ESP32-D0WD-V3 + MicroPython v1.23.0
- 音阶键：GPIO23/22/21/19/18/14/12 → do/re/mi/fa/sol/la/si
- 功能键：GPIO34(八度+), GPIO35(八度-)
- 控制键：GPIO5(录制/播放)
- 电平特性：按下 = 低电平(0)，释放 = 高电平(1)

⚠️ 重要说明：
GPIO34、GPIO35 是 ESP32 的 INPUT-ONLY 引脚，不支持内部上拉/下拉。
因此八度键必须在硬件上外接上拉电阻（建议 10kΩ 到 3.3V），
否则引脚浮空会导致误触发或检测不到。

去抖策略：
- 非阻塞式软件去抖，稳定 20ms 后才更新按键状态。
- is_pressed() 直接返回稳定状态，供主循环实时查询。
- scan_all() 保留给旧版测试用例使用。
"""

from machine import Pin
import time

# 音阶键 GPIO，顺序对应 do/re/mi/fa/sol/la/si
NOTE_GPIOS = (23, 22, 21, 19, 18, 14, 12)
NOTE_NAMES = ('do', 're', 'mi', 'fa', 'sol', 'la', 'si')

# 功能键 GPIO（34/35 为 input-only，需外接上拉）
FUNC_GPIOS = {
    'octave_up': 34,
    'octave_down': 35,
    'record_play': 5,
}

# 默认去抖时间（毫秒）
DEFAULT_DEBOUNCE_MS = 20


class ButtonMatrix:
    """按键矩阵扫描类：支持边沿事件和实时状态查询。"""

    def __init__(self, debounce_ms=DEFAULT_DEBOUNCE_MS):
        self.debounce_ms = debounce_ms

        self._note_pins = [Pin(gpio, Pin.IN, Pin.PULL_UP) for gpio in NOTE_GPIOS]
        self._func_pins = {
            name: Pin(gpio, Pin.IN, Pin.PULL_UP)
            for name, gpio in FUNC_GPIOS.items()
        }

        # 稳定状态：1=释放，0=按下
        self._note_stable = [1] * len(NOTE_GPIOS)
        self._func_stable = {name: 1 for name in FUNC_GPIOS}
        # 上一次读取的原始状态
        self._note_raw = [1] * len(NOTE_GPIOS)
        self._func_raw = {name: 1 for name in FUNC_GPIOS}
        # 状态变化时刻（毫秒）
        self._note_changed_at = [0] * len(NOTE_GPIOS)
        self._func_changed_at = {name: 0 for name in FUNC_GPIOS}

    def _read_all(self):
        """一次性读取所有按键原始状态。"""
        note_values = [pin.value() for pin in self._note_pins]
        func_values = {name: pin.value() for name, pin in self._func_pins.items()}
        return note_values, func_values

    def _update_states(self, now):
        """更新所有按键稳定状态。"""
        note_values, func_values = self._read_all()

        for idx, val in enumerate(note_values):
            if val != self._note_raw[idx]:
                self._note_raw[idx] = val
                self._note_changed_at[idx] = now

            if val != self._note_stable[idx]:
                if time.ticks_diff(now, self._note_changed_at[idx]) >= self.debounce_ms:
                    self._note_stable[idx] = val

        for name, val in func_values.items():
            if val != self._func_raw[name]:
                self._func_raw[name] = val
                self._func_changed_at[name] = now

            if val != self._func_stable[name]:
                if time.ticks_diff(now, self._func_changed_at[name]) >= self.debounce_ms:
                    self._func_stable[name] = val

    def scan_all(self):
        """
        扫描全部按键。
        返回：{'notes': [idx, ...], 'funcs': [name, ...]}
        只返回本次 newly pressed（按下沿）的键。
        """
        now = time.ticks_ms()
        note_values, func_values = self._read_all()

        note_events = []
        for idx, val in enumerate(note_values):
            if val != self._note_raw[idx]:
                self._note_raw[idx] = val
                self._note_changed_at[idx] = now

            if val != self._note_stable[idx]:
                if time.ticks_diff(now, self._note_changed_at[idx]) >= self.debounce_ms:
                    old_stable = self._note_stable[idx]
                    self._note_stable[idx] = val
                    if old_stable == 1 and val == 0:
                        note_events.append(idx)

        func_events = []
        for name, val in func_values.items():
            if val != self._func_raw[name]:
                self._func_raw[name] = val
                self._func_changed_at[name] = now

            if val != self._func_stable[name]:
                if time.ticks_diff(now, self._func_changed_at[name]) >= self.debounce_ms:
                    old_stable = self._func_stable[name]
                    self._func_stable[name] = val
                    if old_stable == 1 and val == 0:
                        func_events.append(name)

        return {'notes': note_events, 'funcs': func_events}

    def is_pressed(self, name: str) -> bool:
        """查询指定按键当前是否处于稳定按下状态。"""
        now = time.ticks_ms()

        if name in FUNC_GPIOS:
            # 八度键是按住生效的功能键，不需要去抖，直接返回实时电平。
            # GPIO34/35 是 INPUT-ONLY，必须外接上拉电阻。
            return self._func_pins[name].value() == 0
        elif name in NOTE_NAMES:
            idx = NOTE_NAMES.index(name)
            pin = self._note_pins[idx]
        else:
            return False

        val = pin.value()

        def _get(container, key):
            return container[key] if idx is None else container[idx]

        def _set(container, key, value):
            if idx is None:
                container[key] = value
            else:
                container[idx] = value

        key = name  # 仅用于 func（dict）时

        if val != _get(self._func_raw if idx is None else self._note_raw, key):
            _set(self._func_raw if idx is None else self._note_raw, key, val)
            _set(self._func_changed_at if idx is None else self._note_changed_at, key, now)

        if val != _get(self._func_stable if idx is None else self._note_stable, key):
            if time.ticks_diff(now, _get(self._func_changed_at if idx is None else self._note_changed_at, key)) >= self.debounce_ms:
                _set(self._func_stable if idx is None else self._note_stable, key, val)

        return _get(self._func_stable if idx is None else self._note_stable, key) == 0

    def get_pressed_keys(self):
        """
        返回当前所有被按下的键名列表。
        包含音符名(do/re/...)和功能键名(octave_up/octave_down)。
        """
        pressed = []
        for idx, pin in enumerate(self._note_pins):
            if pin.value() == 0:
                pressed.append(NOTE_NAMES[idx])
        for name, pin in self._func_pins.items():
            if pin.value() == 0:
                pressed.append(name)
        return pressed

    def get_octave_shift(self):
        """
        返回八度偏移：+1(八度+按下), -1(八度-按下), 0(均未按)。
        若同时按下，按相反方向抵消。
        """
        up = self._func_pins['octave_up'].value() == 0
        down = self._func_pins['octave_down'].value() == 0
        return (1 if up else 0) - (1 if down else 0)

    @property
    def key_names(self):
        """返回所有按键名称列表（7 音阶 + 2 八度键 + 1 控制键）。"""
        return list(NOTE_NAMES) + ['octave_up', 'octave_down', 'record_play']


# 兼容新接口的别名
ButtonController = ButtonMatrix
