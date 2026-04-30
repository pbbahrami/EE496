import argparse
import threading

import serial
import serial.tools.list_ports


def pick_port() -> str:
    ports = [p.device for p in serial.tools.list_ports.comports()]
    if not ports:
        raise RuntimeError("No serial ports found.")
    print("Available ports:")
    for i, p in enumerate(ports):
        print(f"  [{i}] {p}")
    idx = input("Select port index: ").strip()
    return ports[int(idx)]


def reader_loop(ser: serial.Serial) -> None:
    while True:
        try:
            line = ser.readline()
            if line:
                print(f"\n< {line.decode('utf-8', errors='ignore').strip()}")
                print("> ", end="", flush=True)
        except Exception:
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Teensy serial control CLI")
    parser.add_argument("--port", default="", help="Serial port (e.g. /dev/cu.usbmodem123)")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    port = args.port.strip() or pick_port()
    ser = serial.Serial(port, args.baud, timeout=0.1)
    print(f"Connected to {port} @ {args.baud}")

    t = threading.Thread(target=reader_loop, args=(ser,), daemon=True)
    t.start()

    print("Commands: PLAY, PAUSE, TOGGLE, STOP, BPM 120, BRI 80, MODE fixed|pitch|rainbow|alternate, BASE 30 120 240, STATUS, HELP")
    try:
        while True:
            cmd = input("> ").strip()
            if not cmd:
                continue
            if cmd.lower() in ("q", "quit", "exit"):
                break
            ser.write((cmd + "\n").encode("utf-8"))
    finally:
        ser.close()


if __name__ == "__main__":
    main()
