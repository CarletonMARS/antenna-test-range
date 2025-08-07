from interfaces.vna_interface import VNAController
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from datetime import datetime
from tkinter import filedialog
import numpy as np
import csv
import os


class VNAFrontPanel(ctk.CTkToplevel):
    def __init__(self, parent, vna_ctrl: VNAController):
        """
        Initialize the VNA front panel window.

        Args:
            parent (tk.Widget): The parent widget.
            vna_ctrl (VNAController): The controller used to interact with the VNA.
        """
        super().__init__(parent)
        self.vna_ctrl = vna_ctrl

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.geometry("1200x800")
        self.resizable(True, True)
        self.title("AGILENT 8722ES SOFT FRONT PANEL")

        self.canvas = None
        self.toolbar = None

        self._create_sparam_buttons()
        self._create_control_buttons()
        self._create_format_buttons()
        self._create_utility_buttons()

        self.plot_frame = ctk.CTkFrame(self)
        self.plot_frame.grid(row=4, column=0, columnspan=10, padx=10, pady=10, sticky="nsew")

        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    # ---------------------- UI BUTTON SETUP ----------------------

    def _add_button(self, row, column, text, command):
        """
        Add a button to the window grid.

        Args:
            row (int): Grid row.
            column (int): Grid column.
            text (str): Button label.
            command (Callable): Function to call on click.
        """
        btn = ctk.CTkButton(self, text=text, command=command)
        btn.grid(row=row, column=column, padx=5, pady=5, sticky="ew")

    def _create_sparam_buttons(self):
        """Create buttons for selecting S-parameters."""
        sparams = ("S11", "S12", "S21", "S22")
        for i, name in enumerate(sparams):
            self._add_button(row=0, column=i, text=name, command=lambda n=name: self.select_sparam(n))

    def _create_control_buttons(self):
        """Create frequency and power control buttons."""
        controls = [
            ("START", self.set_start),
            ("STOP", self.set_stop),
            ("CENTRE", self.set_centre),
            ("SPAN", self.set_span),
            ("POWER", self.set_power),
            ("AUTO SCALE", lambda: self.vna_ctrl.write("AUTO")),
            ("RESET VNA", lambda: self.vna_ctrl.write("*RST"))
        ]
        for i, (label, cmd) in enumerate(controls):
            self._add_button(row=1, column=i, text=label, command=cmd)

    def _create_format_buttons(self):
        """Create display format selection buttons."""
        formats = ["LOGM", "PHAS", "SMIC", "POLA", "LINM", "SWR", "REAL", "IMAG"]
        for i, fmt in enumerate(formats):
            self._add_button(row=2, column=i, text=fmt, command=lambda f=fmt: self.vna_ctrl.write(f"{f};"))

    def _create_utility_buttons(self):
        """Create utility buttons for displaying and exporting data."""
        self._add_button(row=3, column=0, text="DISPLAY TRACE", command=self.display_trace)
        self._add_button(row=3, column=1, text="EXPORT CSV", command=self.export_trace_csv)
        self._add_button(row=5, column=0, text="CLOSE", command=self.handle_close)

    # ---------------------- TRACE DISPLAY ----------------------

    def _reset_plot_area(self):
        """Clear the current plot and toolbar if present."""
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
            self.canvas = None
        if self.toolbar:
            self.toolbar.destroy()
            self.toolbar = None

    def _create_plot_figure(self, freqs, mags):
        """
        Create a Matplotlib figure with frequency and magnitude data.

        Args:
            freqs (np.ndarray): Frequency values (GHz).
            mags (np.ndarray): Magnitude values (dB).

        Returns:
            Figure: A Matplotlib Figure object.
        """
        fig = Figure(figsize=(6, 4))
        ax = fig.add_subplot(111)
        ax.plot(freqs, mags)
        ax.set_xlabel("Freq (GHz)")
        ax.set_ylabel("Mag (dB)")
        ax.grid(True)

        if len(freqs) > 1:
            ticks = np.linspace(freqs[0], freqs[-1], 10)
            ax.set_xticks(ticks)
            ax.set_xticklabels([f"{t:.2f}" for t in ticks])

        return fig

    def display_trace(self):
        """Read and display a VNA trace as a plot."""
        try:
            freqs, mags = self.vna_ctrl.read_trace(channel="CHAN1")
            self._reset_plot_area()

            fig = self._create_plot_figure(freqs, mags)
            self.canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill="both", expand=True)

            self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
            self.toolbar.update()
            self.toolbar.pack(fill="x")
        except Exception as e:
            print(f"Error displaying trace: {e}")

    # ---------------------- CSV EXPORT ----------------------

    def _get_export_path(self):
        """
        Open a file dialog and return the chosen CSV file path.

        Returns:
            str: Path to the CSV file, or empty string if cancelled.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        base_dir = os.path.join(os.getcwd(), "csv", today)
        os.makedirs(base_dir, exist_ok=True)

        return filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialdir=base_dir,
            title="Save CSV",
            filetypes=[("CSV files", "*.csv")]
        )

    def export_trace_csv(self):
        """Export the current VNA trace to a CSV file."""
        try:
            freqs, mags = self.vna_ctrl.read_trace(channel="CHAN1")
            file_path = self._get_export_path()
            if not file_path:
                return
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(zip(freqs, mags))
        except Exception as e:
            print(f"Export failed: {e}")

    def handle_close(self):
        try:
            self.destroy()
        except Exception:
            pass

    def set_start(self):
        self._popup_entry("Enter Start (GHz):", lambda  val: self.vna_ctrl(f"STAR {val}GHz"))
    def set_centre(self):
        self._popup_entry("Enter Centre (GHz):", lambda  val: self.vna_ctrl(f"CENT {val}GHz"))
    def set_stop(self):
        self._popup_entry("Enter Stop (GHz):", lambda  val: self.vna_ctrl(f"STOP {val}GHz"))
    def set_span(self):
        """Prompt for frequency span and set it on the VNA."""
        self._popup_entry("Enter SPAN (GHz):", lambda val: self.vna_ctrl.write(f"SPAN {val}GHz"))

    def set_power(self, ovr: bool):
        """Prompt for output power and set it on the VNA with range validation."""
        def callback(val):
            try:
                power = float(val)
                if power < -10 or power > 5:
                    raise ValueError("Power must be between -70 and 5 dBm.")
                self.vna_ctrl.write(f"POWE {power}")
            except ValueError as e:
                self._show_error_popup(f"Invalid power value: {e}")

        self._popup_entry("Enter POWER (dBm):", callback)

    def _popup_entry(self, prompt: str, callback):
        """
        Show an input popup for user entry and pass the result to a callback.

        Args:
            prompt (str): The prompt text to display.
            callback (Callable[[str], None]): Function to call with the input value.
        """
        popup = ctk.CTkToplevel(self)
        popup.title(prompt)
        popup.geometry("300x120")

        label = ctk.CTkLabel(popup, text=prompt)
        label.pack(pady=10)

        entry = ctk.CTkEntry(popup)
        entry.pack()

        def submit():
            val = entry.get()
            callback(val)
            popup.destroy()

        submit_btn = ctk.CTkButton(popup, text="Submit", command=submit)
        submit_btn.pack(pady=10)

    # ---------------------- MISC ----------------------

    def select_sparam(self, sparam: str):
        """
        Select the active S-parameter for measurement.

        Args:
            sparam (str): One of 'S11', 'S12', 'S21', or 'S22'.
        """
        self.vna_ctrl.select_sparam(sparam)

    def _show_error_popup(self, message: str):
        popup = ctk.CTkToplevel(self)
        popup.title("Input Error")
        popup.geometry("300x100")

        label = ctk.CTkLabel(popup, text=message, wraplength=280)
        label.pack(pady=10)

        ok_btn = ctk.CTkButton(popup, text="OK", command=popup.destroy)
        ok_btn.pack()

    def handle_close(self):
        """Close the GUI window."""
        try:
            self.destroy()
        except Exception:
            pass
