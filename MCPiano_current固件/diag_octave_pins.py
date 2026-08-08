from machine import Pin
import time

# GPIO34/35 是 input-only，不支持内部上拉
up = Pin(34, Pin.IN)
down = Pin(35, Pin.IN)

print("读取 GPIO34/35 原始电平（100 次采样）")
print("按 Ctrl+C 退出\n")

try:
    while True:
        up_samples = []
        down_samples = []
        for _ in range(100):
            up_samples.append(up.value())
            down_samples.append(down.value())
            time.sleep_us(100)

        print("GPIO34(升八): 低={} 高={} | GPIO35(降八): 低={} 高={}".format(
            up_samples.count(0), up_samples.count(1),
            down_samples.count(0), down_samples.count(1)))
        time.sleep_ms(500)
except KeyboardInterrupt:
    print("停止")
