"""
test_piano_v1.py - 9 键数字钢琴系统综合测试

测试内容：按键扫描 → 状态机 → I2S 功放发声完整链路

运行前需上传：
    mpremote connect /dev/ttyACM0 cp piano/i2s_audio.py :
    mpremote connect /dev/ttyACM0 cp piano/buttons.py :
    mpremote connect /dev/ttyACM0 cp piano/piano.py :

运行方式：
    mpremote connect /dev/ttyACM0 run tests/test_piano_v1.py
"""

import time
import random
from i2s_audio import I2SAudio
from buttons import ButtonMatrix
from piano import Piano, NOTES, OCTAVES


def test_seven_scale(piano):
    """测试 1：7 个音阶键都能发声。"""
    print("\n[测试 1] 七音阶发声")
    try:
        for idx, name in enumerate(NOTES):
            freq = piano._freq_for(idx)
            print(f"  🎵 {name} ({freq}Hz)")
            piano.play_note(idx)
            time.sleep_ms(500)
        print("  ✅ 七音阶测试通过")
        return True
    except Exception as e:
        print(f"  ❌ 失败：{e}")
        return False


def test_octave_shift(piano):
    """测试 2：八度+/- 切换有效。"""
    print("\n[测试 2] 八度切换")
    try:
        print("  中音 do：")
        piano.play_note(0)
        time.sleep_ms(500)

        print("  八度+（高八度 do）：")
        piano.handle_events({'funcs': ['octave_up']})
        piano.play_note(0)
        time.sleep_ms(500)

        print("  八度- 两次（低八度 do）：")
        piano.handle_events({'funcs': ['octave_down', 'octave_down']})
        piano.play_note(0)
        time.sleep_ms(500)

        # 恢复到默认中音
        piano.handle_events({'funcs': ['octave_up']})

        print("  ✅ 八度切换测试通过")
        return True
    except Exception as e:
        print(f"  ❌ 失败：{e}")
        return False


def test_multiple_keys(piano):
    """测试 3：同时按多个键不崩溃（顺序响应）。"""
    print("\n[测试 3] 多键同时按下")
    try:
        print("  同时触发 do + mi + sol")
        piano.handle_events({'notes': [0, 2, 4]})
        time.sleep_ms(800)
        print("  ✅ 多键测试通过")
        return True
    except Exception as e:
        print(f"  ❌ 失败：{e}")
        return False


def test_continuous_run(piano):
    """测试 4：持续运行 10 秒，随机按键，验证不卡死。"""
    print("\n[测试 4] 持续运行 10 秒随机按键")
    try:
        start = time.ticks_ms()
        count = 0
        while time.ticks_diff(time.ticks_ms(), start) < 10000:
            # 每 200ms 左右模拟一次随机按键
            if random.getrandbits(4) == 0:
                idx = random.randint(0, 6)
                piano.handle_events({'notes': [idx]})
                count += 1
            piano.tick()
            time.sleep_ms(10)
        print(f"  ✅ 10 秒内处理 {count} 个随机音符")
        return True
    except Exception as e:
        print(f"  ❌ 失败：{e}")
        return False


def main():
    print("=" * 50)
    print("MCPiano v1 系统综合测试")
    print("按键 + I2S 功放 + 八度切换")
    print("=" * 50)

    audio = None
    results = {}

    try:
        audio = I2SAudio()
        buttons = ButtonMatrix()
        piano = Piano(audio, buttons, enable_led=False)

        results['seven_scale'] = test_seven_scale(piano)
        results['octave_shift'] = test_octave_shift(piano)
        results['multiple_keys'] = test_multiple_keys(piano)
        results['continuous_run'] = test_continuous_run(piano)

    except Exception as e:
        print(f"\n❌ 初始化失败：{e}")
        results = {
            'seven_scale': False,
            'octave_shift': False,
            'multiple_keys': False,
            'continuous_run': False,
        }
    finally:
        if audio is not None:
            audio.stop()
            print("\nI2S 资源已释放")

    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    for name, ok in results.items():
        status = "✅ 通过" if ok else "❌ 失败"
        print(f"  {name}: {status}")

    all_passed = all(results.values())
    print("\n" + ("🎉 全部测试通过" if all_passed else "⚠️ 部分测试失败"))
    print("=" * 50)

    return all_passed


if __name__ == "__main__":
    main()
