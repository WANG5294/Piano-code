from piano import Piano
import time

def main():
    piano = Piano()
    print("MCPiano 采样版就绪")
    print("21个真实钢琴采样：C3-D3-E3-F3-G3-A3-B3 / C4-D4... / C5...")

    try:
        while True:
            piano.tick()
            time.sleep_ms(5)
    except KeyboardInterrupt:
        piano.close()
        print("已退出")

if __name__ == '__main__':
    main()
