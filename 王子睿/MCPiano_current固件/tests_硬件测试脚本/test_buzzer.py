"""
test_buzzer.py - 蜂鸣器发声模块测试
硬件上下文：ESP32-D0WD-V3 开发板（用户外接面包板）
GPIO 映射（以原理图为最终依据）：
  - 蜂鸣器 B1 -> GPIO25，PWM 输出
  - 驱动方式：NPN 晶体管 MMSS8050(Q3)，高电平使能
  - 限流电阻：R13 = 1k
电平特性：PWM duty=512（50% 占空比）时发声，duty=0 时静音
接线方式：GPIO25 -> R13 -> Q3 基极 -> Q3 集电极驱动蜂鸣器 -> GND
注意：本测试使用用户自购蜂鸣器外接在面包板上，非板载 MLT-5020
"""

from machine import PWM, Pin
import time

# ─── 硬件配置 ──────────────────────────────────────────
BUZZER_GPIO = 25          # 蜂鸣器 PWM 输出
PWM_DUTY_ON = 512         # 50% 占空比，发声
PWM_DUTY_OFF = 0          # 静音
NOTE_DURATION_MS = 300    # 每个音符持续时间（毫秒）
PAUSE_MS = 100            # 音符间隔（毫秒）

# ─── 音阶频率表（C4 大调）──────────────────────────────
NOTES = {
    'do':  ('C4',  262),  # 261.63 Hz
    're':  ('D4',  294),  # 293.66 Hz
    'mi':  ('E4',  330),  # 329.63 Hz
    'fa':  ('F4',  349),  # 349.23 Hz
    'sol': ('G4',  392),  # 392.00 Hz
    'la':  ('A4',  440),  # 440.00 Hz
    'si':  ('B4',  494),  # 493.88 Hz
    'do5': ('C5',  523),  # 523.25 Hz，高八度
}

# ─── 初始化 ────────────────────────────────────────────
buzzer = PWM(Pin(BUZZER_GPIO))

print("=" * 50)
print("蜂鸣器发声模块测试")
print(f"GPIO{BUZZER_GPIO} PWM 输出，高电平使能（duty=512 发声）")
print("=" * 50)


def play_tone(freq, duration_ms):
    """播放指定频率的音调"""
    buzzer.freq(freq)
    buzzer.duty(PWM_DUTY_ON)
    time.sleep_ms(duration_ms)
    buzzer.duty(PWM_DUTY_OFF)
    time.sleep_ms(PAUSE_MS)


def test_basic_beep():
    """测试 1：基本蜂鸣"""
    print("\n[测试 1] 基本蜂鸣测试")
    print("即将播放一个 440Hz (A4) 音，持续 0.5 秒...")
    time.sleep(1)
    
    buzzer.freq(440)
    buzzer.duty(PWM_DUTY_ON)
    time.sleep_ms(500)
    buzzer.duty(PWM_DUTY_OFF)
    
    print("  ✅ 如果听到蜂鸣声，说明基本驱动正常")
    time.sleep(0.5)
    return True


def test_seven_scale():
    """测试 2：七音阶 do-re-mi-fa-sol-la-si"""
    print("\n[测试 2] 七音阶测试（do-re-mi-fa-sol-la-si）")
    print("即将播放 7 个音符，每个 0.3 秒...")
    time.sleep(1)
    
    scale = ['do', 're', 'mi', 'fa', 'sol', 'la', 'si']
    for name in scale:
        note, freq = NOTES[name]
        print(f"  🎵 {name} ({note}, {freq}Hz)")
        play_tone(freq, NOTE_DURATION_MS)
    
    print("  ✅ 七音阶播放完成")
    return True


def test_octave():
    """测试 3：八度切换"""
    print("\n[测试 3] 八度切换测试")
    print("播放低八度 do -> 中音 do -> 高八度 do...")
    time.sleep(1)
    
    # 低八度 C3
    print("  🎵 do 低八度 (C3, ~131Hz)")
    play_tone(131, NOTE_DURATION_MS)
    
    # 中音 C4
    print("  🎵 do 中音 (C4, 262Hz)")
    play_tone(262, NOTE_DURATION_MS)
    
    # 高八度 C5
    print("  🎵 do 高八度 (C5, 523Hz)")
    play_tone(523, NOTE_DURATION_MS)
    
    print("  ✅ 八度切换测试完成")
    return True


def test_melody():
    """测试 4：简单旋律《小星星》"""
    print("\n[测试 4] 简单旋律《小星星》")
    print("1155665-4433221...")
    time.sleep(1)
    
    melody = [
        ('do', 262), ('do', 262), ('sol', 392), ('sol', 392),
        ('la', 440), ('la', 440), ('sol', 392), (None, 0),
        ('fa', 349), ('fa', 349), ('mi', 330), ('mi', 330),
        ('re', 294), ('re', 294), ('do', 262),
    ]
    
    for name, freq in melody:
        if name:
            print(f"  🎵 {name}")
            play_tone(freq, NOTE_DURATION_MS)
        else:
            time.sleep_ms(PAUSE_MS * 2)
    
    print("  ✅ 旋律播放完成")
    return True


def cleanup():
    """释放 PWM 资源"""
    buzzer.duty(PWM_DUTY_OFF)
    buzzer.deinit()
    print("\n蜂鸣器已静音，PWM 资源已释放")


def main():
    try:
        ok1 = test_basic_beep()
        ok2 = test_seven_scale()
        ok3 = test_octave()
        ok4 = test_melody()
        
        print("\n" + "=" * 50)
        if all([ok1, ok2, ok3, ok4]):
            print("蜂鸣器模块测试 ✅ 全部通过")
            print("\n听到所有音阶和旋律了吗？")
            print("- 如果没声音：检查 GPIO25 接线、蜂鸣器极性、NPN 驱动方向")
            print("- 如果声音沙哑：调整 PWM 频率范围（20Hz~20kHz）")
        else:
            print("蜂鸣器模块测试 ❌ 存在异常")
        print("=" * 50)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
