import serial
import time


class SerialController:
    def __init__(self, port, baud):
        self.conn = serial.Serial(port, baud, timeout=2)
        time.sleep(0.5)
    def save0(self):
        self.conn.write("G10 L20 P1 X0 Y0 A0\n".encode('utf-8'))

    def query_position(self):
        """
        Sends '?' and parses <Idle|WPos:x,y,z,a,b,c|FS:...>
        Returns a 6-tuple of floats: (x, y, z, a, b, c)
        """
        self.conn.reset_input_buffer()
        self.conn.write(b'?')
        time.sleep(0.1)
        raw = self.conn.readline().decode('utf-8').strip()
        if raw.startswith('<') and raw.endswith('>'):
            raw = raw[1:-1]

        for field in raw.split('|'):
            if field.startswith('WPos:') or field.startswith('MPos:'):
                parts = field.split(':', 1)[1].split(',')
                if len(parts) < 6:
                    raise RuntimeError(f"Expected 6 coords, got {len(parts)} in {raw}")
                try:
                    # convert first six entries
                    vals = [float(p) for p in parts[:6]]
                    return tuple(vals)  # (x,y,z,a,b,c)
                except ValueError:
                    raise RuntimeError(f"Non-numeric coords in {raw}")

        raise RuntimeError(f"No position data in response: {raw}")

    def move_to(self, x, y, z=0, a=0, ):
        cmd = f"G0 X{x} Y{y} Z{z} A{a}\n"
        self.conn.write(cmd.encode('utf-8'))

    def wait_for_idle(self, timeout=5, poll_interval=0.05):
        start = time.time()

        while True:
            # flush any old data
            self.conn.reset_input_buffer()

            # ask for status
            self.conn.write(b'?')
            time.sleep(poll_interval)

            raw = self.conn.readline().decode('utf-8').strip()

            if raw.startswith('<Idle|'):
                return
            if time.time() - start > timeout:
                raise RuntimeError("Timeout waiting for Idle")

    def home_x(self):
        self.conn.write(('$HX\n').encode('utf-8'))

    def home_y(self):
        self.conn.write(('$HY\n').encode('utf-8'))

    def home_a(self):
        self.conn.write(('$HZ\n').encode('utf-8'))  # Assuming homing A is triggered by $HZ

    def home_xya(self):
        self.conn.write(('$H\n').encode('utf-8'))

    def close(self):
        self.conn.close()


