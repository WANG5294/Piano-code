"""
I2S 音频驱动 — 采样回放版
21 个真实钢琴采样，三八度支持
"""

from machine import I2S, Pin
import os

# 最大播放字节数（16kHz 16-bit 单声道）
# 24000 字节 ≈ 0.75 秒，避免采样太长拖尾
MAX_PLAY_BYTES = 24000


class I2SAudio:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self._stopped = False
        self.i2s = I2S(
            0, sck=Pin(16), ws=Pin(17), sd=Pin(25),
            mode=I2S.TX, bits=16, format=I2S.MONO,
            rate=sample_rate, ibuf=4000
        )
        self.sample_dir = 'samples'

        # 音符名 -> (低八度文件, 中音文件, 高八度文件)
        self.note_files = {
            'do':  ('C3.wav', 'C4.wav', 'C5.wav'),
            're':  ('D3.wav', 'D4.wav', 'D5.wav'),
            'mi':  ('E3.wav', 'E4.wav', 'E5.wav'),
            'fa':  ('F3.wav', 'F4.wav', 'F5.wav'),
            'sol': ('G3.wav', 'G4.wav', 'G5.wav'),
            'la':  ('A3.wav', 'A4.wav', 'A5.wav'),
            'si':  ('B3.wav', 'B4.wav', 'B5.wav'),
        }

    def _get_path(self, note: str, octave: int) -> str:
        """根据音符和八度返回采样文件路径"""
        if note not in self.note_files:
            return None
        idx = octave + 1  # -1->0, 0->1, 1->2
        filename = self.note_files[note][idx]
        return f'{self.sample_dir}/{filename}'

    def play_note(self, note: str, octave: int = 0):
        """播放采样，octave: -1=低八度, 0=中音, 1=高八度"""
        path = self._get_path(note, octave)
        if not path:
            return

        try:
            stat = os.stat(path)
        except OSError:
            return

        self._stopped = False

        try:
            with open(path, 'rb') as f:
                # 跳过 WAV 头（标准 44 字节）
                header = f.read(44)
                if len(header) < 44 or header[:4] != b'RIFF':
                    return

                # 流式播放，512 字节分块，限制最大播放长度
                total = 0
                while total < MAX_PLAY_BYTES:
                    if self._stopped:
                        break
                    chunk = f.read(512)
                    if not chunk:
                        break
                    if len(chunk) % 2 != 0:
                        chunk = chunk[:-1]
                    self.i2s.write(chunk)
                    total += len(chunk)
        except Exception as e:
            print(f"[音频] 错误: {e}")

    def stop(self):
        """停止播放并静音"""
        self._stopped = True
        self.i2s.write(b'\x00' * 400)
