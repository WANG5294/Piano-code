"""
test_max98357a.py - MAX98357A I2S 功放模块独立测试

硬件上下文：
- 开发板：ESP32-D0WD-V3 + MicroPython v1.23.0
- 功放模块：MAX98357A
- I2S 接线：
    GPIO16 -> BCLK
    GPIO17 -> LRCK
    GPIO25 -> DIN
    5V -> VIN
    GND -> GND
    5V -> SD_MODE（使能功放，不可悬空）
    5V -> GAIN（本模块 VIN=正常增益；GND=高增益）
- 喇叭：红线接 MAX98357A OUT+，黑线接 OUT-

运行方式：
    mpremote connect /dev/ttyACM0 run tests/test_max98357a.py
"""

import math
import time
from machine import I2S, Pin

SAMPLE_RATE = 16000
BITS = 16
CHANNELS = I2S.MONO
BUFFER_SIZE = 40000

BCLK_GPIO = 16
LRCK_GPIO = 17
DIN_GPIO = 25

NOTES = {
    'C4': 262,
    'D4': 294,
    'E4': 330,
    'F4': 349,
    'G4': 392,
    'A4': 440,
    'B4': 494,
    'C5': 523,
}


def _init_i2s():
    """初始化 I2S 接口。"""
    return I2S(
        0,
        sck=Pin(BCLK_GPIO),
        ws=Pin(LRCK_GPIO),
        sd=Pin(DIN_GPIO),
        mode=I2S.TX,
        bits=BITS,
        format=CHANNELS,
        rate=SAMPLE_RATE,
        ibuf=BUFFER_SIZE,
    )


def _generate_sine(freq, duration_ms, volume):
    """生成 16-bit 单声道正弦波 PCM 数据。"""
    num_samples = SAMPLE_RATE * duration_ms // 1000
    buf = bytearray(num_samples * 2)

    for i in range(num_samples):
        value = int(
            32767 * volume * math.sin(2 * math.pi * freq * i / SAMPLE_RATE)
        )
        if value > 32767:
            value = 32767
        elif value < -32768:
            value = -32768
        buf[i * 2] = value & 0xFF
        buf[i * 2 + 1] = (value >> 8) & 0xFF

    return buf


def _play_tone(audio, freq, duration_ms, volume=0.5, pause_ms=200):
    """播放单个音调，音符间留短暂静音。"""
    samples = _generate_sine(freq, duration_ms, volume)
    audio.write(samples)
    time.sleep_ms(pause_ms)


def test_basic_tone(audio):
    """测试 1：基本正弦波 440Hz，持续 0.5s。"""
    print("\n[测试 1] 基本正弦波 440Hz / 0.5s / volume=0.5")
    try:
        _play_tone(audio, 440, 500, 0.5)
        print("  ✅ 基本音调播放完成")
        return True
    except Exception as e:
        print(f"  ❌ 失败：{e}")
        return False


def test_seven_scale(audio):
    """测试 2：七音阶 do-re-mi-fa-sol-la-si，每个 0.3s。"""
    print("\n[测试 2] 七音阶 do-re-mi-fa-sol-la-si")
    scale = ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4']
    try:
        for note in scale:
            print(f"  🎵 {note} ({NOTES[note]}Hz)")
            _play_tone(audio, NOTES[note], 300, 0.5)
        print("  ✅ 七音阶播放完成")
        return True
    except Exception as e:
        print(f"  ❌ 失败：{e}")
        return False


def test_volume_range(audio):
    """测试 3：音量从 0.1 到 0.9 多档变化，验证动态范围。"""
    print("\n[测试 3] 音量动态范围：0.1 -> 0.3 -> 0.5 -> 0.7 -> 0.9")
    volumes = [0.1, 0.3, 0.5, 0.7, 0.9]
    try:
        for vol in volumes:
            print(f"  🔊 volume={vol}")
            _play_tone(audio, 262, 400, vol, pause_ms=500)
        print("  ✅ 音量动态范围测试完成")
        return True
    except Exception as e:
        print(f"  ❌ 失败：{e}")
        return False


def test_octave_switch(audio):
    """测试 4：八度切换 C3/C4/C5。"""
    print("\n[测试 4] 八度切换 C3(131Hz) -> C4(262Hz) -> C5(523Hz)")
    try:
        for freq in [131, 262, 523]:
            print(f"  🎵 {freq}Hz")
            _play_tone(audio, freq, 400, 0.5)
        print("  ✅ 八度切换测试完成")
        return True
    except Exception as e:
        print(f"  ❌ 失败：{e}")
        return False


def main():
    print("=" * 50)
    print("MAX98357A I2S 功放模块独立测试")
    print(f"BCLK=GPIO{BCLK_GPIO}, LRCK=GPIO{LRCK_GPIO}, DIN=GPIO{DIN_GPIO}")
    print("=" * 50)

    audio = None
    results = {}

    try:
        audio = _init_i2s()
        print("\nI2S 初始化成功")

        results['basic_tone'] = test_basic_tone(audio)
        time.sleep_ms(1000)
        results['seven_scale'] = test_seven_scale(audio)
        time.sleep_ms(1000)
        results['volume_range'] = test_volume_range(audio)
        time.sleep_ms(1000)
        results['octave_switch'] = test_octave_switch(audio)

    except Exception as e:
        print(f"\n❌ I2S 初始化失败：{e}")
        results = {k: False for k in ['basic_tone', 'seven_scale',
                                       'volume_range', 'octave_switch']}
    finally:
        if audio is not None:
            try:
                audio.deinit()
                print("\nI2S 资源已释放")
            except Exception:
                pass

    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    for name, ok in results.items():
        status = "✅ 通过" if ok else "❌ 失败"
        print(f"  {name}: {status}")

    all_passed = all(results.values())
    print("\n" + ("🎉 全部测试通过" if all_passed else "⚠️ 部分测试失败，请检查接线"))
    print("=" * 50)

    return all_passed


if __name__ == "__main__":
    main()
