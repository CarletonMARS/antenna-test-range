import serial, time
from dataclasses import dataclass

@dataclass
class ArduinoStageConfig:
    port: str = "COM7"        # set to Arduino port
    baud: int = 115200
    timeout: float = 0.3
    steps_per_deg: float = 800.0  # matches the CTrack Setting

class ArduinoRotationStage:
    """Driver for the Arduino sketch that accepts: '<steps>', 'a<steps>', 'r'."""
    def __init__(self, cfg: ArduinoStageConfig):
        self.cfg = cfg
        self.ser = serial.Serial(cfg.port, cfg.baud, timeout=cfg.timeout)
        time.sleep(1.0)  # some boards reset on open

    def close(self):
        try: self.ser.close()
        except: pass

    def _send(self, s: str):
        if not s.endswith("\n"):
            s += "\n"
        self.ser.write(s.encode("utf-8"))

    def _readline(self, t=1.0):
        t0 = time.time()
        while time.time() - t0 < t:
            line = self.ser.readline()
            if line:
                return line.decode("utf-8", errors="ignore").strip()
        return None

    # ---- degree-space API ----
    def reset_origin(self):
        self._send("r")
        return self._readline()

    def move_rel_deg(self, deg: float):
        steps = int(round(deg * self.cfg.steps_per_deg))
        self._send(str(steps))           # Arduino echoes the integer
        return self._readline()

    def move_abs_deg(self, deg: float):
        steps = int(round(deg * self.cfg.steps_per_deg))
        self._send(f"a{steps}")

    # simple blocking wait; time-based; firmware doesn’t signal done;
    # should add in future for safety
    def wait_estimate(self, deg: float):
        time.sleep(max(0.5, abs(deg) * 0.05))
