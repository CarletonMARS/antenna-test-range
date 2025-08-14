import serial, time
from dataclasses import dataclass
from typing import Optional  # NEW: for type hints

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
        self._drain_serial(0.25)  # NEW: clear boot noise so we don't misread stale lines

    # ------------- connection helpers -------------

    @property
    def is_open(self) -> bool:  # NEW: soft connection check for UI chips
        try:
            return bool(self.ser and self.ser.is_open)
        except Exception:
            return False

    def close(self):
        try:
            self.ser.close()
        except:
            pass

    # ------------- low-level I/O -------------

    def _send(self, s: str):
        # send one line (firmware expects newline-terminated commands)
        if not s.endswith("\n"):
            s += "\n"
        self.ser.write(s.encode("utf-8"))

    def _readline(self, t: float = 1.0) -> Optional[str]:
        """
        Read exactly one line with a soft timeout 't' seconds.
        Returns decoded line (without newline) or None on timeout.
        """
        t0 = time.time()
        while time.time() - t0 < t:
            line = self.ser.readline()
            if line:
                return line.decode("utf-8", errors="ignore").strip()
        return None

    def _drain_serial(self, duration: float = 0.1):
        """
        Best-effort drain of any pending bytes for 'duration' seconds.
        Useful right after board reset to drop garbage/old tokens.
        """
        t0 = time.time()
        try:
            while time.time() - t0 < duration:
                if self.ser.in_waiting:
                    _ = self.ser.read(self.ser.in_waiting)
                else:
                    time.sleep(0.01)
        except Exception:
            pass

    # ------------- degree-space API -------------

    def reset_origin(self):
        # firmware: 'r' -> prints "r" and marks zero in EEPROM
        self._send("r")
        return self._readline()  # typically "r"

    def move_rel_deg(self, deg: float):
        # relative in degrees -> relative steps
        steps = int(round(deg * self.cfg.steps_per_deg))
        self._send(str(steps))           # firmware echoes the integer
        return self._readline()          # echo (optional for UI logging)

    def move_abs_deg(self, deg: float):
        # absolute in degrees -> absolute steps
        steps = int(round(deg * self.cfg.steps_per_deg))
        self._send(f"a{steps}")          # firmware may not echo here

    # ------------- status & deterministic waiting -------------

    def query_status(self) -> Optional[str]:
        """
        Ask firmware for motion state ('BUSY' or 'IDLE').
        Returns 'BUSY'/'IDLE' or None if no answer.
        """
        self._send("?")
        line = self._readline(t=0.3)
        if not line:
            return None
        u = line.strip().upper()
        if u in ("BUSY", "IDLE"):
            return u
        return None

    def wait_until_done(self, timeout: float = 60.0) -> bool:
        """
        Deterministic wait for motion completion.
        Strategy:
          1) Passively watch serial for 'DONE' (emitted at end of a move/stop).
          2) Also handle 'IDLE' responses to '?' polling.
          3) Timeout after 'timeout' seconds.
        Returns True on completion, False on timeout.
        """
        t0 = time.time()
        last_poll = 0.0

        # drop any stale lines so an old DONE doesn't trick us
        self._drain_serial(0.05)

        while time.time() - t0 < timeout:
            # passive: consume any spontaneous lines (BUSY/DONE/echo)
            line = self._readline(t=0.2)
            if line:
                u = line.strip().upper()
                if u == "DONE":
                    return True
                if u in ("BUSY", "IDLE"):
                    if u == "IDLE":
                        return True
                    # if BUSY, keep looping

            # proactive: poll status every ~0.5s
            now = time.time()
            if now - last_poll >= 0.5:
                last_poll = now
                st = self.query_status()
                if st == "IDLE":
                    return True
                # BUSY/None -> keep waiting

        return False  # timed out

    # ------------- convenience (non-breaking) -------------

    def move_abs_and_wait(self, deg: float, timeout: float = 60.0) -> bool:
        """
        Convenience helper: absolute move in degrees, then block until finished.
        Returns True if completed, False if timed out.
        """
        self.move_abs_deg(deg)
        ok = self.wait_until_done(timeout=timeout)
        if not ok:
            # last-resort fallback to legacy estimate, then return False
            self.wait_estimate(deg)
        return ok

    def move_rel_and_wait(self, deg: float, timeout: float = 60.0) -> bool:
        """
        Convenience helper: relative move in degrees, then block until finished.
        Returns True if completed, False if timed out.
        """
        _ = self.move_rel_deg(deg)  # echo ignored
        ok = self.wait_until_done(timeout=timeout)
        if not ok:
            self.wait_estimate(deg)
        return ok

    # ------------- legacy fallback (unchanged) -------------

    # simple blocking wait; time-based; firmware doesn’t signal done;
    # should add in future for safety
    def wait_estimate(self, deg: float):
        time.sleep(max(0.5, abs(deg) * 0.05))