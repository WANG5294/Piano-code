"""
LED 驱动模块

板载 LED：
- LED2（绿色） -> GPIO32，低电平点亮
- LED3（红色） -> GPIO33，低电平点亮
"""

import time

from machine import Pin
from hardware_config import GREEN_LED_PIN, RED_LED_PIN


class LED:
    """单个 LED 驱动类"""

    def __init__(self, pin: int, name: str = "led", active_low: bool = True):
        self.name = name
        self._pin = Pin(pin, Pin.OUT)
        self._active_low = active_low
        self.off()

    def on(self):
        """点亮 LED"""
        self._pin.value(0 if self._active_low else 1)

    def off(self):
        """熄灭 LED"""
        self._pin.value(1 if self._active_low else 0)

    def toggle(self):
        """翻转 LED 状态"""
        self._pin.value(not self._pin.value())

    def set(self, state: bool):
        """设置 LED 状态"""
        if state:
            self.on()
        else:
            self.off()


class LEDManager:
    """管理所有板载 LED"""

    def __init__(self):
        self.green = LED(GREEN_LED_PIN, "GREEN", active_low=True)
        self.red = LED(RED_LED_PIN, "RED", active_low=True)

    def all_on(self):
        self.green.on()
        self.red.on()

    def all_off(self):
        self.green.off()
        self.red.off()

    def blink(self, led_name: str, times: int = 3, interval: float = 0.2):
        """指定 LED 闪烁若干次"""
        led = self.green if led_name == "GREEN" else self.red
        for _ in range(times):
            led.on()
            time.sleep(interval)
            led.off()
            time.sleep(interval)
