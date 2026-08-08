"""
钢琴主逻辑 — 采样回放版（录制/回放 + 八度 toggle + LED 指示）
"""

import time
from machine import Pin
from buttons import ButtonController
from i2s_audio import I2SAudio

NOTE_LIST = ['do', 're', 'mi', 'fa', 'sol', 'la', 'si']

# 运行状态
STATE_IDLE = 0
STATE_RECORDING = 1
STATE_PLAYING = 2

# 长按阈值（毫秒）
RECORD_LONG_PRESS_MS = 800

# 板载 LED（低电平点亮）
LED_UP_GPIO = 32    # 绿灯：高八度 / 录制中
LED_DOWN_GPIO = 33  # 红灯：低八度 / 播放中


class Piano:
    def __init__(self):
        self.buttons = ButtonController()
        self.audio = I2SAudio()
        self.octave_shift = 0
        self.prev = {k: False for k in self.buttons.key_names}

        # 八度键边沿检测
        self._prev_up = False
        self._prev_down = False

        # 板载 LED
        self._led_up = Pin(LED_UP_GPIO, Pin.OUT, value=1)
        self._led_down = Pin(LED_DOWN_GPIO, Pin.OUT, value=1)

        # 录制/播放状态
        self._state = STATE_IDLE
        self._recording = []
        self._record_start_ms = 0
        self._record_press_start = 0
        self._record_long_triggered = False

        # 播放状态
        self._playback_events = []
        self._playback_index = 0
        self._playback_start_ms = 0

    def tick(self):
        """主循环 5ms"""
        # ─── 八度检测（按一下切换，再按归零） ───
        up = self.buttons.is_pressed('octave_up')
        down = self.buttons.is_pressed('octave_down')

        if up and not self._prev_up:
            self.octave_shift = 1 if self.octave_shift != 1 else 0
        if down and not self._prev_down:
            self.octave_shift = -1 if self.octave_shift != -1 else 0

        self._prev_up = up
        self._prev_down = down

        # ─── GPIO5 录制/播放键 ───
        self._handle_record_play_key()

        # ─── 更新 LED ───
        self._update_leds()

        # ─── 琴键检测 + 采样播放 ───
        for note in NOTE_LIST:
            curr = self.buttons.is_pressed(note)
            prev = self.prev[note]

            if curr and not prev:
                self._record_event('note_on', note)
                self.audio.play_note(note, self.octave_shift)

            self.prev[note] = curr

        # ─── 播放进度 ───
        if self._state == STATE_PLAYING:
            self._update_playback()

    def _handle_record_play_key(self):
        """GPIO5：短按切换录制，长按播放"""
        now = time.ticks_ms()
        curr = self.buttons.is_pressed('record_play')
        prev = self.prev.get('record_play', False)

        if curr and not prev:
            self._record_press_start = now
            self._record_long_triggered = False
        elif curr and prev:
            if (not self._record_long_triggered and
                    time.ticks_diff(now, self._record_press_start) >= RECORD_LONG_PRESS_MS):
                self._record_long_triggered = True
                self._start_playback()
        elif not curr and prev:
            if not self._record_long_triggered:
                self._toggle_recording()

        self.prev['record_play'] = curr

    def _toggle_recording(self):
        if self._state == STATE_RECORDING:
            self._stop_recording()
        elif self._state == STATE_IDLE:
            self._start_recording()

    def _start_recording(self):
        self._state = STATE_RECORDING
        self._recording = []
        self._record_start_ms = time.ticks_ms()
        print("开始录制...")

    def _stop_recording(self):
        self._state = STATE_IDLE
        print("停止录制，共 {} 个事件".format(len(self._recording)))

    def _record_event(self, event_type, note):
        if self._state != STATE_RECORDING:
            return
        now = time.ticks_ms()
        rel_time = time.ticks_diff(now, self._record_start_ms)
        self._recording.append({
            'type': event_type,
            'note': note,
            'octave': self.octave_shift,
            'time': rel_time,
        })

    def _start_playback(self):
        if not self._recording:
            print("没有录制内容")
            return
        if self._state == STATE_PLAYING:
            return
        self._state = STATE_PLAYING
        self._playback_events = list(self._recording)
        self._playback_index = 0
        self._playback_start_ms = time.ticks_ms()
        print("开始播放")

    def _update_playback(self):
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self._playback_start_ms)

        while self._playback_index < len(self._playback_events):
            ev = self._playback_events[self._playback_index]
            if ev['time'] <= elapsed:
                self._playback_index += 1
                if ev['type'] == 'note_on':
                    self.audio.play_note(ev['note'], ev.get('octave', 0))
            else:
                break

        if self._playback_index >= len(self._playback_events):
            self._state = STATE_IDLE
            print("播放结束")

    def _update_leds(self):
        if self._state == STATE_RECORDING:
            self._led_up.value(0)   # 绿灯亮
            self._led_down.value(1)
        elif self._state == STATE_PLAYING:
            self._led_up.value(1)
            self._led_down.value(0)  # 红灯亮
        else:
            self._led_up.value(0 if self.octave_shift == 1 else 1)
            self._led_down.value(0 if self.octave_shift == -1 else 1)

    def close(self):
        self.audio.stop()
