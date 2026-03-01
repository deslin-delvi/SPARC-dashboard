#!/usr/bin/env python3
"""
test_hardware.py — Hardware Diagnostic Suite
Substation PPE Safety Monitoring System
Raspberry Pi 4 · YOLOv11 · SG90 Servo · ADIY Relay Module

Usage:
    python test_hardware.py              # Safe mode  (no movement)
    python test_hardware.py --full       # Full mode  (servo moves, relay toggles)
    python test_hardware.py --relay      # Relay/LED test only
    python test_hardware.py --servo      # Servo test only
    python test_hardware.py --camera     # Camera test only
"""

import sys
import time
import os

SERVO_PIN  = 18
RELAY_PIN  = 23
ACTIVE_LOW = True
CLOSED_PW  = 1500
OPEN_PW    = 2200
MODEL_PATH = "models/best.pt"
CAMERA_INDEX = 0

PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⏭️  SKIP"
WARN = "⚠️  WARN"

def banner(title):
    print(f"\n{'─'*56}")
    print(f"  {title}")
    print(f"{'─'*56}")

def result(label, status, detail=""):
    pad = 28
    line = f"  {label:<{pad}} {status}"
    if detail:
        line += f"\n  {'':>{pad}}   → {detail}"
    print(line)

def test_packages():
    banner("TEST 1 · Python Packages")
    packages = {
        "flask":             "Flask",
        "flask_login":       "Flask-Login",
        "flask_bcrypt":      "Flask-Bcrypt",
        "flask_sqlalchemy":  "Flask-SQLAlchemy",
        "cv2":               "OpenCV (cv2)",
        "ultralytics":       "Ultralytics (YOLO)",
        "numpy":             "NumPy",
        "RPi.GPIO":          "RPi.GPIO",
        "pigpio":            "pigpio",
    }
    all_ok = True
    for pkg, label in packages.items():
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "")
            result(label, PASS, ver)
        except ImportError:
            detail = f"pip install {pkg.replace('_', '-').lower()}"
            if pkg == "pigpio":
                detail = "pip install pigpio  (and ensure pigpiod is running)"
            result(label, FAIL, detail)
            all_ok = False
    return all_ok

def test_pigpiod():
    banner("TEST 2 · pigpiod Daemon (DMA PWM)")
    try:
        import pigpio
        pi = pigpio.pi()
        if not pi.connected:
            result("pigpiod connection", FAIL, "sudo systemctl start pigpiod")
            return False
        ver = pi.get_pigpio_version()
        result("pigpiod connection", PASS, f"version {ver}")
        result("DMA PWM available",  PASS, "servo will use hardware timing")
        pi.stop()
        return True
    except ImportError:
        result("pigpio import", FAIL, "pip install pigpio")
        return False
    except Exception as e:
        result("pigpiod connection", FAIL, str(e))
        return False

def test_model():
    banner("TEST 3 · YOLO Model File")
    if not os.path.exists(MODEL_PATH):
        result("Model file", FAIL, f"{MODEL_PATH} not found")
        return False
    size_mb = os.path.getsize(MODEL_PATH) / (1024 * 1024)
    result("Model file", PASS, f"{MODEL_PATH}  ({size_mb:.1f} MB)")
    try:
        from ultralytics import YOLO
        model = YOLO(MODEL_PATH)
        names = list(model.names.values())
        result("Model loads OK", PASS, f"{len(names)} classes: {', '.join(names)}")
        expected = {"helmet", "gloves", "boots", "no-helmet", "no-gloves", "no-boots"}
        missing  = expected - set(names)
        if missing:
            result("Expected classes", WARN, f"Missing: {', '.join(missing)}")
        else:
            result("Expected classes", PASS, "All 6 PPE classes present")
        return True
    except Exception as e:
        result("Model loads OK", FAIL, str(e))
        return False

def test_camera():
    banner("TEST 4 · USB Camera")
    try:
        import cv2, platform
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_V4L2
        cap = cv2.VideoCapture(CAMERA_INDEX, backend)
        if not cap.isOpened():
            result("Camera open", FAIL, f"Index {CAMERA_INDEX} not available")
            print("  Run:  ls /dev/video*  to list connected cameras")
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        ok, frame = cap.read()
        if not ok or frame is None:
            result("Camera read", FAIL, "cap.read() returned no frame")
            cap.release()
            return False
        h, w = frame.shape[:2]
        fps  = cap.get(cv2.CAP_PROP_FPS)
        result("Camera open", PASS, f"Index {CAMERA_INDEX}")
        result("Frame read",  PASS, f"{w}x{h}  @  {fps:.0f} FPS reported")
        cap.release()
        return True
    except Exception as e:
        result("Camera test", FAIL, str(e))
        return False

def test_relay():
    banner("TEST 5 · Relay Module + LEDs  (GPIO 23)")
    print(f"  Relay pin  : GPIO{RELAY_PIN}  (Physical Pin 16)")
    print(f"  Active-LOW : {ACTIVE_LOW}  (ADIY no-opto, VCC on 3.3V)")
    print(f"  Expected   : RED = de-energised (NC)   GREEN = energised (NO)\n")
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        print("  [1/4]  GPIO HIGH -> relay OFF -> NC -> RED should be ON")
        time.sleep(2)
        GPIO.output(RELAY_PIN, GPIO.LOW)
        print("  [2/4]  GPIO LOW  -> relay ON  -> NO -> GREEN should be ON")
        time.sleep(2)
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        print("  [3/4]  GPIO HIGH -> relay OFF -> NC -> RED should be ON")
        time.sleep(2)
        GPIO.output(RELAY_PIN, GPIO.LOW)
        print("  [4/4]  GPIO LOW  -> relay ON  -> NO -> GREEN should be ON")
        time.sleep(2)
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        print("\n  Relay left in OFF state (RED - gate closed)")
        GPIO.cleanup()
        passed = input("\n  Did the LEDs switch correctly? (y/n): ").strip().lower()
        if passed == 'y':
            result("Relay + LED toggle", PASS)
            return True
        else:
            result("Relay + LED toggle", FAIL, "Check NC/NO wiring or relay VCC is on 3.3V pin")
            return False
    except Exception as e:
        result("Relay test", FAIL, str(e))
        try: GPIO.cleanup()
        except Exception: pass
        return False

def test_servo():
    banner("TEST 6 · SG90 Servo - pigpio DMA PWM  (GPIO 18)")
    print(f"  Servo pin  : GPIO{SERVO_PIN}  (Physical Pin 12, BCM)")
    print(f"  Closed     : {CLOSED_PW} us")
    print(f"  Open       : {OPEN_PW} us")
    print(f"  PWM type   : pigpio DMA (CPU-load independent)")
    print(f"  Power      : Separate 5V supply (NOT Pi 5V pin)\n")
    try:
        from hardware_controller import GateController
        print("  WARNING: Servo will move. Ensure area is clear.\n")
        gate = GateController(
            mode           = 'direct',
            servo_pin      = SERVO_PIN,
            relay_pin      = RELAY_PIN,
            led_active_low = ACTIVE_LOW,
        )
        print("  [1/4]  CLOSING gate  ->  servo -> closed pos  · RED LED")
        gate.close_gate()
        time.sleep(2)
        print("  [2/4]  OPENING gate  ->  servo -> open pos    · GREEN LED")
        gate.open_gate()
        time.sleep(2)
        print("  [3/4]  CLOSING gate  ->  servo -> closed pos  · RED LED")
        gate.close_gate()
        time.sleep(2)
        print("  [4/4]  OPENING gate  ->  servo -> open pos    · GREEN LED")
        gate.open_gate()
        time.sleep(2)
        print("  [5/5]  Returning to CLOSED (safe default)")
        gate.close_gate()
        time.sleep(1)
        gate.cleanup()
        passed = input("\n  Did servo move smoothly to correct positions? (y/n): ").strip().lower()
        if passed == 'y':
            result("Servo DMA PWM", PASS)
            return True
        else:
            result("Servo DMA PWM", FAIL,
                   f"Tune CLOSED_PW/OPEN_PW in hardware_controller.py "
                   f"(currently {CLOSED_PW}/{OPEN_PW} us)")
            return False
    except Exception as e:
        result("Servo test", FAIL, str(e))
        return False

def test_filesystem():
    banner("TEST 7 · File System & Paths")
    checks = {
        "models/":                  os.path.isdir("models"),
        "static/":                  os.path.isdir("static"),
        "templates/":               os.path.isdir("templates"),
        "app.py":                   os.path.isfile("app.py"),
        "hardware_controller.py":   os.path.isfile("hardware_controller.py"),
        "utils/yolo_detector.py":   os.path.isfile("utils/yolo_detector.py"),
        "utils/rtsp_processor.py":  os.path.isfile("utils/rtsp_processor.py"),
    }
    all_ok = True
    for path, exists in checks.items():
        if exists:
            result(path, PASS)
        else:
            result(path, FAIL, "not found")
            all_ok = False
    vdir = os.path.join("static", "violations")
    if os.path.isdir(vdir):
        count = len(os.listdir(vdir))
        result("static/violations/", PASS, f"{count} file(s) stored")
    else:
        result("static/violations/", WARN, "will be created on first violation")
    return all_ok

def main():
    args   = sys.argv[1:]
    full   = "--full"   in args
    relay  = "--relay"  in args
    servo  = "--servo"  in args
    camera = "--camera" in args

    print("\n" + "="*56)
    print("  HARDWARE DIAGNOSTIC SUITE")
    print("  Substation PPE Safety Monitoring System")
    print("="*56)
    print(f"  Servo  : GPIO{SERVO_PIN}  (Pin 12) · pigpio DMA PWM")
    print(f"  Relay  : GPIO{RELAY_PIN}  (Pin 16) · active-LOW · VCC 3.3V")
    print(f"  Camera : index {CAMERA_INDEX}")

    if full:
        print("\n  Mode: FULL  - servo will move, relay will toggle")
    elif relay:
        print("\n  Mode: RELAY only")
    elif servo:
        print("\n  Mode: SERVO only")
    elif camera:
        print("\n  Mode: CAMERA only")
    else:
        print("\n  Mode: SAFE  - no hardware movement")
        print("  Use --full to include servo + relay tests")

    results = {}

    if not (relay or servo or camera):
        results["Packages"]       = test_packages()
        results["pigpiod daemon"] = test_pigpiod()
        results["YOLO model"]     = test_model()
        results["USB camera"]     = test_camera()
        results["File system"]    = test_filesystem()

    if camera:
        results["USB camera"] = test_camera()
    if full or relay:
        results["Relay + LEDs"]    = test_relay()
    if full or servo:
        results["Servo (DMA PWM)"] = test_servo()

    banner("SUMMARY")
    for name, res in results.items():
        s = PASS if res is True else (FAIL if res is False else SKIP)
        result(name, s)

    print()
    failed  = [k for k, v in results.items() if v is False]
    skipped = [k for k, v in results.items() if v is None]

    if not failed:
        print("  All tests passed - system is ready.\n")
        print("  Next steps:")
        print("    1. python create_admin.py    <- create first user")
        print("    2. python app.py             <- start the server")
        print("    3. Open http://<pi-ip>:5000  <- open dashboard")
    else:
        print(f"  {len(failed)} test(s) failed: {', '.join(failed)}")
        print("  Fix the issues above before starting app.py")

    if skipped:
        print(f"\n  Skipped: {', '.join(skipped)}")
        print("  Run with --full to include hardware movement tests")

    print("\n" + "="*56 + "\n")

if __name__ == "__main__":
    main()