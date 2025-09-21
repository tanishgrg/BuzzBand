# pip install pyserial
import time
import serial
import serial.tools.list_ports

def list_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return []
    print("Available serial ports:")
    for idx, p in enumerate(ports):
        print(f"[{idx}] {p.device}  ({p.description})")
    return ports

def open_serial():
    ports = list_ports()
    if not ports:
        return None
    sel = input("Select COM index for Arduino: ").strip()
    try:
        sel = int(sel)
        port_name = ports[sel].device
    except Exception:
        # allow direct typing like "COM7"
        port_name = sel
    print(f"Opening {port_name} at 115200...")
    ser = serial.Serial(port=port_name, baudrate=115200, timeout=1)
    # Give the Arduino time to reset after opening the port
    time.sleep(2)
    return ser

def send_line(ser, line):
    ser.write((line.strip() + "\n").encode("utf-8"))

def beep(ser, duration_ms=200, freq_hz=2000):
    # Use the more general TONE command
    send_line(ser, f"TONE {freq_hz} {duration_ms}")

if __name__ == "__main__":
    ser = open_serial()
    if ser is None:
        raise SystemExit

    print("Testing three beeps...")
    for i in range(3):
        beep(ser, duration_ms=200, freq_hz=2000)  # 2 kHz for 200 ms
        time.sleep(0.3)

    # interactive loop (Ctrl+C to quit)
    print("\nType commands like:")
    print("  tone 1000 500   -> 1 kHz for 500 ms")
    print("  beep 250        -> 2 kHz for 250 ms")
    print("  stop            -> stop tone\n")

    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd.startswith("tone"):
                # tone f d
                _, f, d = cmd.split()
                send_line(ser, f"TONE {int(f)} {int(d)}")
            elif cmd.startswith("beep"):
                # beep d   (fixed 2 kHz)
                _, d = cmd.split()
                send_line(ser, f"BEEP {int(d)}")
            elif cmd in ("stop", "notone"):
                send_line(ser, "NOTONE")
            elif cmd in ("quit", "exit"):
                break
            else:
                print("Unknown. Try: tone <freqHz> <ms> | beep <ms> | stop | quit")
    finally:
        ser.close()
