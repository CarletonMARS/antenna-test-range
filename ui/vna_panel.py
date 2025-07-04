from docutils.parsers.rst.directives.images import Figure

from interfaces.vna_interface import VNAController
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


class VNAFrontPanel(ctk.CTkToplevel):
    """
      A GUI-based soft front panel for controlling and displaying measurements
      from an Agilent 8720ES VNA using a `VNAController` interface.

      This panel allows the user to:
      - Select S-parameters (S11, S12, S21, S22)
      - Change display format (e.g., LOGM, PHAS, SWR)
      - Fetch and plot the current VNA trace
      - View plots with interactive toolbar
      """
    def __init__(self, parent, vna_ctrl: VNAController):
        """
        Initialize the front panel window and its widgets.

        Args:
            parent: The parent tkinter window or frame.
            vna_ctrl (VNAController): A controller instance for communicating with the VNA.
        """
        super().__init__(parent)
        self.vna_ctrl = vna_ctrl

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.attributes("-topmost", True)
        self.geometry("1000x700")
        self.resizable(True, True)
        self.title("AGILENT 8722ES SOFT FRONT PANEL")

        # Measurement Selection
        for i, name in enumerate(("S11", "S12", "S21", "S22")):
            btn = ctk.CTkButton(self, text=name, command=lambda n=name: self.select_sparam(n))
            btn.grid(row=0, column=i, padx=5, pady=5)

        # Format Buttons
        formats = ["LOGM", "PHAS", "SMIC", "POLA", "LINM", "SWR", "REAL", "IMAG"]
        for i, fmt in enumerate(formats):
            btn = ctk.CTkButton(self, text=fmt, command=lambda f=fmt: self.vna_ctrl.write(f"{f};"))
            btn.grid(row=2, column=i, padx=3, pady=3)

        # display trace
        self.trace_btn = ctk.CTkButton(self, text="DISPLAY TRACE", command=self.display_trace)
        self.trace_btn.grid(row=3, column=0, padx=10, pady=0)

        # Plot Area
        self.plot_frame = ctk.CTkFrame(self)
        self.plot_frame.grid(row=3, column=1, columnspan=8, padx=10, pady=10)
        self.canvas = None
        self.toolbar = None

        # Close button
        self.close_btn = ctk.CTkButton(self, text="close", command=self.handle_close)
        self.close_btn.grid(row=4, column=0, padx=10, pady=10)
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    def select_sparam(self, sparam: str):
        """
        Selects the S-parameter to measure (e.g., S11, S21) on the VNA.

        Args:
            sparam (str): The S-parameter to select (e.g., 'S11').
        """
        self.vna_ctrl.select_sparam(sparam)

    def display_trace(self):
        """
        Reads the trace data from the VNA and plots it in the GUI.
        The trace is displayed as a frequency vs magnitude (dB) plot.
        Replaces any existing plot in the panel.
        """
        try:
            freqs, mags = self.vna_ctrl.read_trace(channel="CHAN1")
            if self.canvas:
                self.canvas.get_tk_widget().destroy()
                self.toolbar.destroy()
            fig = Figure(figsize=(5, 3))
            ax = fig.add_subplot(111)
            ax.plot(freqs, mags)
            ax.set_xlabel("Freq (GHz)")
            ax.set_ylabel("Mag (dB)")
            ax.grid(True)

            self.canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
            self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
            self.toolbar.update()
            self.toolbar.pack(fill="x")
        except Exception as e:
            print(f"Error displaying trace: {e}")

    def handle_close(self):
        """
        Closes the VNA front panel window.
        """
        try:
            self.destroy()
        except Exception:
            pass