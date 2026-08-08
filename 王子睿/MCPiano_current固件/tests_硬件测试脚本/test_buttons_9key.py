"""
test_buttons_9key.py - 9 键手动按压测试

硬件上下文：
- 音阶键：GPIO23/22/21/19/18/14/12 → do/re/mi/fa/sol/la/si
- 功能键：GPIO34(八度+), GPIO35(八度-)
- 电平特性：内部上拉，按下 = 低电平(0)

运行方式：
    mpremote connect /dev/ttyACM0 cp piano/buttons.py :buttons.py
    mpremote connect /dev/ttyACM0 run tests/test_buttons_9key.py

按 Ctrl+C 退出。
"""

import time
from buttons import ButtonMatrix, NOTE_GPIOS, FUNC_GPIOS

NOTE_NAMES = ['do', 're', 'mi', 'fa', 'sol', 'la', 'si']


def main():
    print("=" * 50)
    print("9 键手动按压测试")
    print("请逐个按下按键，观察终端输出")
    print("按 Ctrl+C 退出")
    print("=" * 50)

    print("\n按键映射：")
    for idx, gpio in enumerate(NOTE_GPIOS):
        print(f"  GPIO{gpio:2d} -> {NOTE_NAMES[idx]}")
    for name, gpio in FUNC_GPIOS.items():
        print(f"  GPIO{gpio:2d} -> {name}")
    print()

    buttons = ButtonMatrix(debounce_ms=20)

    try:
        while True:
            events = buttons.scan_all()

            for idx in events.get('notes', []):
                print(f"  ✅ GPIO{NOTE_GPIOS[idx]} 按下 -> {NOTE_NAMES[idx]}")

            for name in events.get('funcs', []):
                print(f"  ✅ GPIO{FUNC_GPIOS[name]} 按下 -> {name}")

            time.sleep_ms(10)

    except KeyboardInterrupt:
        print("\n👋 测试结束")


if __name__ == "__main__":
    main()
