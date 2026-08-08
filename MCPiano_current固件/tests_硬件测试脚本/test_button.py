"""
test_button.py - 按键输入模块测试
硬件上下文：ESP32-D0WD-V3 开发板（用户外接面包板）
GPIO 映射（以原理图为最终依据）：
  - KEY1 -> GPIO34，输入，内部上拉，1k 串联电阻(R9)
  - KEY2 -> GPIO35，输入，内部上拉，1k 串联电阻(R12)
电平特性：按下 = 低电平(0)，释放 = 高电平(1)
接线方式：GPIO34/35 -> 按键一端，按键另一端 -> GND
"""

from machine import Pin
import time

# ─── 硬件配置 ──────────────────────────────────────────
KEY1_GPIO = 34  # K3，钢琴键 1
KEY2_GPIO = 35  # K4，钢琴键 2
DEBOUNCE_MS = 20  # 软件去抖时间（毫秒）

# ─── 初始化 ────────────────────────────────────────────
# 内部上拉：未按下时引脚被拉到高电平(1)
key1 = Pin(KEY1_GPIO, Pin.IN, Pin.PULL_UP)
key2 = Pin(KEY2_GPIO, Pin.IN, Pin.PULL_UP)

print("=" * 50)
print("按键输入模块测试")
print(f"KEY1(GPIO{KEY1_GPIO}) + KEY2(GPIO{KEY2_GPIO})")
print("电平特性：内部上拉，按下=低电平(0)")
print("=" * 50)


def test_basic_read():
    """测试 1：基本电平读取"""
    print("\n[测试 1] 基本电平读取")
    print("请确保按键未按下，然后观察读数...")
    time.sleep(1)
    
    v1 = key1.value()
    v2 = key2.value()
    print(f"  KEY1 读数: {v1} (预期: 1 / 高电平)")
    print(f"  KEY2 读数: {v2} (预期: 1 / 高电平)")
    
    if v1 == 1 and v2 == 1:
        print("  ✅ 未按下时读数正确")
    else:
        print("  ❌ 未按下时读数异常，检查接线或上拉电阻")
        return False
    
    print("\n  现在请按住 KEY1（不要松开）...")
    time.sleep(2)
    v1 = key1.value()
    print(f"  KEY1 读数: {v1} (预期: 0 / 低电平)")
    
    if v1 == 0:
        print("  ✅ KEY1 按下检测正确")
    else:
        print("  ❌ KEY1 按下检测失败，检查接线")
        return False
    
    print("\n  现在请按住 KEY2（不要松开）...")
    time.sleep(2)
    v2 = key2.value()
    print(f"  KEY2 读数: {v2} (预期: 0 / 低电平)")
    
    if v2 == 0:
        print("  ✅ KEY2 按下检测正确")
    else:
        print("  ❌ KEY2 按下检测失败，检查接线")
        return False
    
    return True


def test_edge_detection():
    """测试 2：边沿检测（按下/释放事件）"""
    print("\n[测试 2] 边沿检测 + 软件去抖")
    print(f"去抖时间: {DEBOUNCE_MS}ms")
    print("请交替按下/释放 KEY1 和 KEY2，观察输出...")
    print("持续 10 秒，按 Ctrl+C 可提前结束\n")
    
    last_v1 = key1.value()
    last_v2 = key2.value()
    last_time = time.ticks_ms()
    
    start = time.ticks_ms()
    count1 = 0
    count2 = 0
    
    try:
        while time.ticks_diff(time.ticks_ms(), start) < 10000:
            now = time.ticks_ms()
            v1 = key1.value()
            v2 = key2.value()
            
            # KEY1 边沿检测（带去抖）
            if v1 != last_v1:
                if time.ticks_diff(now, last_time) > DEBOUNCE_MS:
                    if v1 == 0:
                        count1 += 1
                        print(f"  [KEY1] 按下 (计数: {count1})")
                    else:
                        print(f"  [KEY1] 释放")
                    last_v1 = v1
                    last_time = now
            
            # KEY2 边沿检测（带去抖）
            if v2 != last_v2:
                if time.ticks_diff(now, last_time) > DEBOUNCE_MS:
                    if v2 == 0:
                        count2 += 1
                        print(f"  [KEY2] 按下 (计数: {count2})")
                    else:
                        print(f"  [KEY2] 释放")
                    last_v2 = v2
                    last_time = now
            
            time.sleep_ms(5)
    except KeyboardInterrupt:
        pass
    
    print(f"\n  KEY1 按下次数: {count1}")
    print(f"  KEY2 按下次数: {count2}")
    
    if count1 > 0 and count2 > 0:
        print("  ✅ 两个按键均正常工作")
        return True
    else:
        print("  ⚠️ 部分按键无响应，检查接线")
        return False


def main():
    ok1 = test_basic_read()
    ok2 = test_edge_detection()
    
    print("\n" + "=" * 50)
    if ok1 and ok2:
        print("按键模块测试 ✅ 全部通过")
    else:
        print("按键模块测试 ❌ 存在异常，请排查后重试")
    print("=" * 50)


if __name__ == "__main__":
    main()
