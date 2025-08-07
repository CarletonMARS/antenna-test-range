import pyvisa
import time
import numpy as np


class VNAController:
    def __init__(self, resource_str: str):
        """
        Initializes the VNA controller with the given VISA resource string.

        Args:
            resource_str (str): The VISA resource identifier (e.g., "GPIB1::16::INSTR").
        """
        self.resource_str = resource_str
        self.rm = None
        self.VNA = None

    def connect(self):
        """
        Opens the VISA connection to the VNA and returns its identification string.

        Returns:
            str: The response from the VNA to the "*IDN?" query.
        """
        self.rm = pyvisa.ResourceManager()
        self.VNA = self.rm.open_resource(self.resource_str)
        idn = self.VNA.query("*IDN?")
        return idn.strip()

    def write(self, cmd: str):
        """
        Sends a SCPI command to the VNA without expecting a response.

        Args:
            cmd (str): The SCPI command string to send.

        Raises:
            RuntimeError: If the VNA is not connected.
        """
        if not self.VNA:
            raise RuntimeError("VNA not connected")
        self.VNA.write(cmd)
        time.sleep(0.1)

    def query(self, cmd: str) -> str:
        """
        Sends a SCPI query command and returns the response string.

        Args:
            cmd (str): The SCPI command string (e.g., "POIN?").

        Returns:
            str: The VNA's response to the query.

        Raises:
            RuntimeError: If the VNA is not connected.
        """
        if not self.VNA:
            raise RuntimeError("VNA not connected")
        return self.VNA.query(cmd)

    def select_sparam(self, sparam: str):
        """
        Selects the active S-parameter to measure (e.g., S11, S21).

        Args:
            sparam (str): The S-parameter to select.
        """
        self.write(sparam)

    def read_trace(self, channel: str = "CHAN1") -> (np.ndarray, np.ndarray):
        """
        Reads the active trace data from the VNA for the specified channel.

        Args:
            channel (str): The VNA measurement channel (default: "CHAN1").

        Returns:
            tuple:
                - freqs (np.ndarray): Frequency points in GHz.
                - mags (np.ndarray): Magnitude values (real part of complex trace).
        """
        self.write("FORM5")
        self.write(f"{channel};")
        self.write("OUTPFORM;")
        vals = self.VNA.query_binary_values("", container=list, header_fmt="hp")

        f_start = float(self.query("STAR?"))
        f_stop = float(self.query("STOP?"))
        num_points = int(float(self.query("POIN?")))
        freqs = np.linspace(f_start, f_stop, num_points)
        mags = np.array(vals[0::2])
        return freqs / 1e9, mags

    def reset(self):
        """
        Performs a full instrument reset (*RST) on the VNA.
        """
        self.write("*RST")
        time.sleep(0.1)

    def handle_close(self):
        """
        Closes the VISA session and releases the VNA resource.
        """
        if self.VNA:
            self.VNA.control_ren(0)
        if self.rm:
            self.rm.close()
