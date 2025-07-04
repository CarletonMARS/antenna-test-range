import serial
import time


class SerialController:
    def __init__(self, port, baud):
        """
        Initializes the serial connection to the positioner.

        Args:
            port (str): Serial port (e.g., 'COM3', '/dev/ttyUSB0').
            baud (int): Baud rate (e.g., 115200).
        """

        self.conn = serial.Serial(port, baud, timeout=2)
        time.sleep(0.5)
    def save0(self):
        """
        Sends a command to save the current position as the new origin (0,0,0,0).
        """
        self.conn.write("G10 L20 P1 X0 Y0 A0\n".encode('utf-8'))

    def query_position(self):
        """
        Queries the current position of the stage.

        Sends a '?' command and parses the GRBL response.

        Returns:
            tuple: (x, y, z, a, b, c) as floats.

        Raises:
            RuntimeError: If the response is malformed or incomplete.
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

    def move_to(self, x, y, z=0, a=0 ):
        """
        Sends a G-code move command to the specified coordinates.

        Args:
            x (float): Target X position.
            y (float): Target Y position.
            z (float): Target Z position (default 0).
            a (float): Target A position (default 0).
        """
        cmd = f"G0 X{x} Y{y} Z{z} A{a}\n"
        self.conn.write(cmd.encode('utf-8'))

    def wait_for_idle(self, timeout=5, poll_interval=0.05):
        """
        Waits until the positioner reports an <Idle> state.

        Args:
            timeout (float): Maximum wait time in seconds.
            poll_interval (float): Time between polling attempts in seconds.

        Raises:
            RuntimeError: If the positioner does not become idle within the timeout.
        """
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
        """
        Sends a command to home the X-axis.
        """
        self.conn.write(('$HX\n').encode('utf-8'))

    def home_y(self):
        """
        Sends a command to home the Y-axis.
        """
        self.conn.write(('$HY\n').encode('utf-8'))

    def home_a(self):
        """
        Sends a command to home the A-axis (mapped to $HZ).
        """
        self.conn.write(('$HZ\n').encode('utf-8'))  # Assuming homing A is triggered by $HZ

    def home_xya(self):
        """
        Sends a command to home all axes (X, Y, A).
        """
        self.conn.write(('$H\n').encode('utf-8'))

    def handle_close(self):
        """
        Closes the serial connection.
        """
        self.conn.close()


