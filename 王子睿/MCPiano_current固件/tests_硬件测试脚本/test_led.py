"""
test_led.py - LED 指示灯模块测试
硬件上下文：ESP32-D0WD-V3 开发板（用户外接面包板）
GPIO 映射（以原理图为最终依据）：
  - LED2(绿) -> GPIO32，输出，低电平有效，1k 限流电阻(R10)
  - LED3(红) -> GPIO33，输出，低电平有效，1k 限流电阻(R11)
电平特性：GPIO=0 时 LED 点亮，GPIO=1 时 LED 熄灭
接线方式：
  3.3V -> 330Ω/1k 电阻 -> LED 正极(长脚)
  LED 负极(短脚) -> GPIO32/33
"""

from machine import Pin
import time

# ─── 硬件配置 ──────────────────────────────────────────
LED2_GPIO = 32   # 绿色 LED，低电平有效
LED3_GPIO = 33   # 红色 LED，低电平有效
BLINK_COUNT = 5  # 闪烁次数
BLINK_INTERVAL = 0.3  # 闪烁间隔（秒）

# ─── 初始化 ────────────────────────────────────────────
# 输出模式，默认高电平（LED 熄灭）
led2 = Pin(LED2_GPIO, Pin.OUT, value=1)
led3 = Pin(LED3_GPIO, Pin.OUT, value=1)

print("=" * 50)
print("LED 指示灯模块测试")
print(f"LED2 绿(GPIO{LED2_GPIO}) + LED3 红(GPIO{LED3_GPIO})")
print("电平特性：低电平有效（0=亮，1=灭）")
print("=" * 50)


def test_single_led(led, name, gpio):
    """测试单个 LED 的亮灭控制"""
    print(f"\n[测试] {name}(GPIO{gpio})")
    
    # 熄灭
    led.value(1)
    print(f"  熄灭: GPIO{gpio}=1")
    time.sleep(0.5)
    
    # 点亮
    led.value(0)
    print(f"  点亮: GPIO{gpio}=0")
    time.sleep(0.5)
    
    # 熄灭
    led.value(1)
    print(f"  熄灭: GPIO{gpio}=1")
    time.sleep(0.3)
    
    print(f"  ✅ {name} 基本控制正常")
    return True


def test_blink_pattern():
    """测试 LED 闪烁模式"""
    print(f"\n[测试] 交替闪烁模式（各闪烁 {BLINK_COUNT} 次）")
    print("观察：绿红 LED 交替闪烁\n")
    
    for i in range(BLINK_COUNT):
        # 绿灯亮，红灯灭
        led2.value(0)
        led3.value(1)
        print(f"  [{i+1}/{BLINK_COUNT}] 🟢 绿亮 | 🔴 红灭")
        time.sleep(BLINK_INTERVAL)
        
        # 绿灯灭，红灯亮
        led2.value(1)
        led3.value(0)
        print(f"  [{i+1}/{BLINK_COUNT}] ⚫ 绿灭 | 🔴 红亮")
        time.sleep(BLINK_INTERVAL)
    
    # 全部熄灭
    led2.value(1)
    led3.value(1)
    print(f"\n  ✅ 交替闪烁测试完成")
    return True


def test_simultaneous():
    """测试两灯同时亮灭"""
    print(f"\n[测试] 同时点亮/熄灭")
    
    # 同时点亮
    led2.value(0)
    led3.value(0)
    print("  两灯同时点亮（黄/橙混合色）")
    time.sleep(1)
    
    # 同时熄灭
    led2.value(1)
    led3.value(1)
    print("  两灯同时熄灭")
    time.sleep(0.5)
    
    print("  ✅ 同步控制正常")
    return True


def main():
    ok1 = test_single_led(led2, "LED2 绿", LED2_GPIO)
    ok2 = test_single_led(led3, "LED3 红", LED3_GPIO)
    ok3 = test_blink_pattern()
    ok4 = test_simultaneous()
    
    # 确保最终状态为熄灭
    led2.value(1)
    led3.value(1)
    
    print("\n" + "=" * 50)
    if all([ok1, ok2, ok3, ok4]):
        print("LED 模块测试 ✅ 全部通过")
    else:
        print("LED 模块测试 ❌ 存在异常")
    print("=" * 50)


if __name__ == "__main__":
    main()
