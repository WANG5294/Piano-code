"""
test_octave_with_led.py - 用板载 LED 直观测试八度键

硬件上下文：
- 八度键：GPIO34(升八), GPIO35(降八)，INPUT-ONLY，需外接上拉
- 板载 LED：GPIO32(绿), GPIO33(红)，低电平点亮

接线：
- GPIO34/35 各通过 330Ω/10kΩ 上拉电阻接 3.3V
- 按键一端接 GPIO34/35，另一端接 GND
- LED 负极接 GPIO32/33，正极经限流电阻接 3.3V

运行方式：
    mpremote connect /dev/ttyACM0 cp tests/test_octave_with_led.py :
    mpremote connect /dev/ttyACM0 run tests/test_octave_with_led.py
"""

from machine import Pin
import time

UP_GPIO = 34
DOWN_GPIO = 35
LED_UP_GPIO = 32   # 绿 LED 指示升八度
LED_DOWN_GPIO = 33 # 红 LED 指示降八度

# GPIO34/35 是 INPUT-ONLY，内部上拉无效，必须外部上拉
up = Pin(UP_GPIO, Pin.IN)
down = Pin(DOWN_GPIO, Pin.IN)

# LED 低电平点亮
led_up = Pin(LED_UP_GPIO, Pin.OUT, value=1)
led_down = Pin(LED_DOWN_GPIO, Pin.OUT, value=1)

print("八度键 LED 测试")
print(f"GPIO{UP_GPIO} 按下 -> 绿灯(GPIO{LED_UP_GPIO})亮")
print(f"GPIO{DOWN_GPIO} 按下 -> 红灯(GPIO{LED_DOWN_GPIO})亮")
print("按 Ctrl+C 退出\n")

try:
    while True:
        up_pressed = up.value() == 0
        down_pressed = down.value() == 0

        led_up.value(0 if up_pressed else 1)
        led_down.value(0 if down_pressed else 1)

        print("GPIO34(升八): {} | GPIO35(降八): {}".format(
            "按下 " if up_pressed else "释放",
            "按下 " if down_pressed else "释放"
        ))

        time.sleep_ms(100)
except KeyboardInterrupt:
    led_up.value(1)
    led_down.value(1)
    print("\n测试结束")
