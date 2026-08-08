"""
piano.py - 数字钢琴主调度模块（八度切换 + 旋律录制/回放）
========================================================
将按键检测（buttons）、蜂鸣器发声（buzzer）、LED反馈（leds）
三个独立模块组合成完整演奏流程，同时支持八度切换和旋律录制/回放。

主循环逻辑：
  1. 扫描录制切换键（GPIO16）：切换录制状态（开始/结束）
  2. 扫描回放键（GPIO17）：回放已录制旋律（录制中无效）
  3. 扫描八度切换键（KEY1升/KEY2降），更新八度偏移量
  4. 扫描音符按键，检测是否有新按下
  5. 有按下 → 以当前八度偏移量播放对应音符 + 触发LED闪烁反馈
  6. 录制中按下音符 → 自动记录（音符名+时间间隔+八度偏移）

LED颜色策略：
  - 音符键：偶数为绿，奇数为红（100ms闪烁）
  - 八度切换：升=绿，降=红（300ms闪烁）
  - 录制开始/结束：绿（200ms闪烁）

本模块只做"调度/编排"，不直接操作GPIO或PWM。
"""

import buttons
import buzzer
import leds
import time

# ============================================================
# 常量
# ============================================================

# 八度偏移范围
_OCTAVE_MIN = -2
_OCTAVE_MAX = 2

# LED闪烁时长（ms）
LED_FLASH_MS = 100

# 音符顺序（用于确定LED颜色：偶数为绿，奇数为红）
_NOTE_ORDER = ['do', 're', 'mi', 'fa', 'so', 'la', 'xi']

# 每个音符对应的LED颜色
_NOTE_LED_COLOR = {
    note: 'green' if idx % 2 == 0 else 'red'
    for idx, note in enumerate(_NOTE_ORDER)
}

# ============================================================
# 模块级状态变量
# ============================================================

# 当前八度偏移量
_octave_offset = 0

# 录制状态
_recording = False           # 是否处于录制中状态
_recorded_notes = []         # 录制数据：[(note_name, interval_ms, octave_offset), ...]
_last_note_ticks = 0         # 上一个音符被检测到的时刻（ticks_ms），用于计算间隔
_is_first_note = True        # 标记本次录制是否还没有记录过音符


# ============================================================
# 初始化
# ============================================================

def init():
    """
    初始化所有子模块。
    必须在 run() 之前调用一次。
    """
    buttons.init()


# ============================================================
# 回放逻辑（阻塞式）
# ============================================================

def _playback():
    """
    按录制顺序、时间间隔、原始八度偏移回放已录制的旋律。
    回放期间阻塞主循环（不检测按键），简化处理。
    """
    print("开始回放 (共 {} 个音符)".format(len(_recorded_notes)))

    for i, (note, interval, octave) in enumerate(_recorded_notes):
        color = _NOTE_LED_COLOR.get(note, 'green')

        # 发声（非阻塞，300ms 自动停止）+ LED闪烁（阻塞100ms）
        buzzer.play_note(note, duration_ms=300, octave_offset=octave)
        leds.flash(color, duration_ms=100)

        print("回放 [{}/{}]: {} (间隔 {}ms, 八度{:+d}, {}LED)".format(
            i + 1, len(_recorded_notes), note, interval, octave, color))

        # 等待录制时的间隔时间，再播放下一个音符
        # interval 已包含录制时 100ms LED 闪烁的自然耗时，
        # 回放也做了 100ms 闪烁，需从等待中扣除，避免双重叠加导致变慢
        if i < len(_recorded_notes) - 1:
            wait_time = max(0, interval - LED_FLASH_MS)
            time.sleep_ms(wait_time)

    print("回放完成")


# ============================================================
# 主循环
# ============================================================

def run():
    """
    启动数字钢琴主循环（八度切换 + 录制/回放 + 音符演奏）。
    循环扫描各按键，检测到按下时执行对应操作。
    循环间隔约 10ms，保证按键响应灵敏。
    """
    global _octave_offset, _recording, _last_note_ticks, _recorded_notes, _is_first_note

    print("数字钢琴已启动，按下按键演奏...")
    print("音符: do(5) re(12) mi(14) fa(18) so(19) la(21) xi(22)")
    print("八度: KEY1(+1) KEY2(-1)，范围 {:+d} ~ {:+d}".format(_OCTAVE_MIN, _OCTAVE_MAX))
    print("录制: GPIO16(切换)  回放: GPIO17")
    print("当前八度: {:+d}".format(_octave_offset))
    print("Ctrl+C 停止")

    while True:
        try:
            # ---- 录制切换检测 (GPIO16) ----
            record_event = buttons.get_record_key_event()
            if record_event == 'record':
                if not _recording:
                    # 开始录制：清空旧数据，记录起始时刻
                    _recording = True
                    _recorded_notes = []
                    _is_first_note = True
                    _last_note_ticks = time.ticks_ms()
                    leds.flash('green', duration_ms=200)
                    print("开始录制")
                else:
                    # 结束录制
                    _recording = False
                    leds.flash('green', duration_ms=200)
                    print("录制结束，共录制 {} 个音符".format(len(_recorded_notes)))

            # ---- 回放检测 (GPIO17) ----
            playback_event = buttons.get_playback_key_event()
            if playback_event == 'playback':
                if _recording:
                    print("录制中，请先结束录制")
                elif not _recorded_notes:
                    print("暂无录制内容")
                else:
                    _playback()

            # ---- 八度切换检测 (KEY1/KEY2) ----
            octave_event = buttons.get_octave_key_event()
            if octave_event == 'up':
                if _octave_offset < _OCTAVE_MAX:
                    _octave_offset += 1
                    leds.flash('green', duration_ms=300)
                    print("八度切换: +1 (当前八度: {:+d})".format(_octave_offset))
                else:
                    print("八度已达上限 ({:+d})，无法继续升高".format(_OCTAVE_MAX))

            elif octave_event == 'down':
                if _octave_offset > _OCTAVE_MIN:
                    _octave_offset -= 1
                    leds.flash('red', duration_ms=300)
                    print("八度切换: -1 (当前八度: {:+d})".format(_octave_offset))
                else:
                    print("八度已达下限 ({:+d})，无法继续降低".format(_OCTAVE_MIN))

            # ---- 音符按键检测 ----
            note = buttons.get_pressed_key()

            if note is not None:
                color = _NOTE_LED_COLOR.get(note, 'green')

                # 录制模式下记录音符（在发声前记录时间戳，保证间隔测量准确）
                if _recording:
                    now = time.ticks_ms()
                    if _is_first_note:
                        # 首音符间隔折半，避免回放开头长等待
                        interval = time.ticks_diff(now, _last_note_ticks) // 2
                        _is_first_note = False
                    else:
                        interval = time.ticks_diff(now, _last_note_ticks)
                    _last_note_ticks = now
                    _recorded_notes.append((note, interval, _octave_offset))

                # 正常发声 + LED反馈（录制和纯演奏都触发）
                buzzer.play_note(note, duration_ms=300, octave_offset=_octave_offset)
                leds.flash(color, duration_ms=100)

                if _recording:
                    print("录制: {} (间隔 {}ms, 八度{:+d}, {}LED)".format(
                        note, interval, _octave_offset, color))
                else:
                    print("演奏: {} ({}LED, 八度{:+d})".format(note, color, _octave_offset))

            # 主循环间隔，保证CPU不过载同时按键响应及时
            time.sleep_ms(10)

        except KeyboardInterrupt:
            print("\n数字钢琴已停止")
            buzzer.stop()
            break
