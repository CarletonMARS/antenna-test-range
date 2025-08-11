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
    """
    Soft front panel for an Agilent 8722ES-like VNA.

    Layout (grouped like a real instrument):
    - Measurement: S-parameter selection (S11/S12/S21/S22)
    - Stimulus: frequency start/stop/center/span and power
    - Display/Format: LOGM/PHAS/SMIC/... and "Auto Scale"
    - Utility: display trace, export CSV, reset, close

    A live plot area occupies the bottom; toolbar appears when a trace is shown.
    """

    def __init__(self, parent, vna_ctrl: VNAController):
        """
        Initialize the VNA front panel window.

        Args:
            parent (tk.Widget): Parent widget.
            vna_ctrl (VNAController): Controller used to interact with the VNA.
        """
        super().__init__(parent)
        self.vna_ctrl = vna_ctrl

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("AGILENT 8722ES — Soft Front Panel")
        self.geometry("1200x800")
        self.resizable(True, True)

        # containers
        self.measure_frame = None
        self.stimulus_frame = None
        self.display_frame = None
        self.utility_frame = None
        self.plot_frame = None

        # plot handles
        self.canvas = None
        self.toolbar = None

        self._build_layout()

        # initial geometry after layout
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    # ---------------------- LAYOUT ----------------------

    def _build_layout(self):
        """
        Build the grouped layout: four top frames + bottom plot area.
        """
        # grid config for window
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # Measurement (S-parameters)
        self.measure_frame = ctk.CTkFrame(self)
        self.measure_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew")
        ctk.CTkLabel(self.measure_frame, text="Measurement", font=("Helvetica", 14, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 4)
        )
        self._create_sparam_buttons(self.measure_frame)

        # Stimulus (freq/power)
        self.stimulus_frame = ctk.CTkFrame(self)
        self.stimulus_frame.grid(row=0, column=1, padx=10, pady=(10, 5), sticky="nsew")
        ctk.CTkLabel(self.stimulus_frame, text="Stimulus", font=("Helvetica", 14, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 4)
        )
        self._create_stimulus_buttons(self.stimulus_frame)

        # Display/Format
        self.display_frame = ctk.CTkFrame(self)
        self.display_frame.grid(row=0, column=2, padx=10, pady=(10, 5), sticky="nsew")
        ctk.CTkLabel(self.display_frame, text="Display / Format", font=("Helvetica", 14, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 4)
        )
        self._create_format_buttons(self.display_frame)

        # Utility
        self.utility_frame = ctk.CTkFrame(self)
        self.utility_frame.grid(row=0, column=3, padx=10, pady=(10, 5), sticky="nsew")
        ctk.CTkLabel(self.utility_frame, text="Utility", font=("Helvetica", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4)
        )
        self._create_utility_buttons(self.utility_frame)

        # Plot area
        self.plot_frame = ctk.CTkFrame(self)
        self.plot_frame.grid(row=4, column=0, columnspan=4, padx=10, pady=(5, 10), sticky="nsew")
        self.plot_frame.grid_rowconfigure(0, weight=1)
        self.plot_frame.grid_columnconfigure(0, weight=1)

    # ---------------------- GROUP BUILDERS ----------------------

    def _btn(self, parent, row, col, text, cmd, colspan=1):
        """
        Create a button in a grid cell with consistent padding/expansion.

        Args:
            parent (ctk.CTkFrame): Parent frame.
            row (int): Grid row.
            col (int): Grid column.
            text (str): Label text.
            cmd (Callable): Click callback.
            colspan (int): Number of columns to span.
        """
        b = ctk.CTkButton(parent, text=text, command=cmd)
        b.grid(row=row, column=col, columnspan=colspan, padx=6, pady=6, sticky="ew")
        parent.grid_columnconfigure(col, weight=1)
        return b

    def _create_sparam_buttons(self, frame):
        """
        Add S-parameter selection buttons to the 'Measurement' frame.
        """
        params = ("S11", "S12", "S21", "S22")
        for i, name in enumerate(params, start=0):
            self._btn(frame, row=1, col=i % 4, text=name, cmd=lambda n=name: self.select_sparam(n))

    def _create_stimulus_buttons(self, frame):
        """
        Add frequency and power controls to the 'Stimulus' frame.
        """
        self._btn(frame, 1, 0, "START", self.set_start)
        self._btn(frame, 1, 1, "STOP", self.set_stop)
        self._btn(frame, 1, 2, "CENTRE", self.set_centre)
        self._btn(frame, 1, 3, "SPAN", self.set_span)
        self._btn(frame, 2, 0, "POWER", self.set_power)

    def _create_format_buttons(self, frame):
        """
        Add format controls and auto-scale to the 'Display/Format' frame.
        """
        formats = ["LOGM", "PHAS", "SMIC", "POLA", "LINM", "SWR", "REAL", "IMAG"]
        # two rows of four for neatness
        for idx, fmt in enumerate(formats):
            r = 1 + (idx // 4)
            c = idx % 4
            self._btn(frame, r, c, fmt, lambda f=fmt: self.vna_ctrl.write(f"{f};"))
        # auto-scale spans full width
        self._btn(frame, 3, 0, "AUTO SCALE", lambda: self.vna_ctrl.write("AUTO"), colspan=4)

    def _create_utility_buttons(self, frame):
        """
        Add trace display/export, reset, and close controls to the 'Utility' frame.
        """
        self._btn(frame, 1, 0, "DISPLAY TRACE", self.display_trace, colspan=2)
        self._btn(frame, 2, 0, "EXPORT CSV", self.export_trace_csv, colspan=2)
        self._btn(frame, 3, 0, "RESET VNA", lambda: self.vna_ctrl.write("*RST"), colspan=2)
        self._btn(frame, 4, 0, "CLOSE", self.handle_close, colspan=2)

    # ---------------------- TRACE DISPLAY ----------------------

    def _reset_plot_area(self):
        """
        Remove any existing canvas/toolbar from the plot frame.
        """
        if self.canvas:
            try:
                self.canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.canvas = None
        if self.toolbar:
            try:
                self.toolbar.destroy()
            except Exception:
                pass
            self.toolbar = None

    def _create_plot_figure(self, freqs, mags):
        """
        Create a Matplotlib figure for a frequency/magnitude trace.

        Args:
            freqs (np.ndarray): Frequency values (GHz).
            mags (np.ndarray): Magnitude values (dB).

        Returns:
            Figure: Matplotlib Figure ready for embedding.
        """
        fig = Figure(figsize=(8, 4.8))
        ax = fig.add_subplot(111)
        ax.plot(freqs, mags)
        ax.set_xlabel("Freq (GHz)")
        ax.set_ylabel("Mag (dB)")
        ax.grid(True)
        if isinstance(freqs, (list, tuple, np.ndarray)) and len(freqs) > 1:
            ticks = np.linspace(float(freqs[0]), float(freqs[-1]), 10)
            ax.set_xticks(ticks)
            ax.set_xticklabels([f"{t:.2f}" for t in ticks])
        return fig

    def display_trace(self):
        """
        Read a trace from the VNA and render it in the plot area with a toolbar.
        """
        try:
            freqs, mags = self.vna_ctrl.read_trace(channel="CHAN1")
            self._reset_plot_area()
            fig = self._create_plot_figure(freqs, mags)
            self.canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
            self.canvas.draw()
            self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

            self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
            self.toolbar.update()
            self.toolbar.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        except Exception as e:
            print(f"Error displaying trace: {e}")

    # ---------------------- CSV EXPORT ----------------------

    def _get_export_path(self):
        """
        Ask for an output CSV path under ./csv/<YYYY-MM-DD>/.

        Returns:
            str: Chosen path or empty string if cancelled.
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
        """
        Read a fresh trace and save it to CSV as two columns (freq_ghz, mag_db).
        """
        try:
            freqs, mags = self.vna_ctrl.read_trace(channel="CHAN1")
            file_path = self._get_export_path()
            if not file_path:
                return
            with open(file_path, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(["Frequency (GHz)", "Magnitude (dB)"])
                w.writerows(zip(freqs, mags))
        except Exception as e:
            print(f"Export failed: {e}")

    # ---------------------- POPUPS & INPUTS ----------------------

    def _popup_entry(self, prompt: str, callback):
        """
        Show an input popup and pass the entered value to `callback`.

        Args:
            prompt (str): Prompt to display on the popup.
            callback (Callable[[str], None]): Handler for the entered string.
        """
        popup = ctk.CTkToplevel(self)
        popup.title(prompt)
        popup.geometry("360x140")
        popup.resizable(False, False)

        label = ctk.CTkLabel(popup, text=prompt, wraplength=320)
        label.pack(pady=(14, 8))

        entry = ctk.CTkEntry(popup)
        entry.pack(padx=14, fill="x")

        def submit():
            val = entry.get()
            try:
                callback(val)
            finally:
                popup.destroy()

        submit_btn = ctk.CTkButton(popup, text="Submit", command=submit)
        submit_btn.pack(pady=12)

        # focus for quick typing
        popup.after(50, entry.focus_set)

    # ---------------------- COMMAND HANDLERS ----------------------

    def select_sparam(self, sparam: str):
        """
        Select the active S-parameter.

        Args:
            sparam (str): One of 'S11', 'S12', 'S21', 'S22'.
        """
        try:
            self.vna_ctrl.select_sparam(sparam)
        except Exception as e:
            print(f"Failed to select {sparam}: {e}")

    def set_start(self):
        """
        Prompt for start frequency (GHz) and send STAR command.
        """
        self._popup_entry("Enter START (GHz):", lambda v: self.vna_ctrl.write(f"STAR {float(v)}GHz"))

    def set_stop(self):
        """
        Prompt for stop frequency (GHz) and send STOP command.
        """
        self._popup_entry("Enter STOP (GHz):", lambda v: self.vna_ctrl.write(f"STOP {float(v)}GHz"))

    def set_centre(self):
        """
        Prompt for center frequency (GHz) and send CENT command.
        """
        self._popup_entry("Enter CENTRE (GHz):", lambda v: self.vna_ctrl.write(f"CENT {float(v)}GHz"))

    def set_span(self):
        """
        Prompt for frequency span (GHz) and send SPAN command.
        """
        self._popup_entry("Enter SPAN (GHz):", lambda v: self.vna_ctrl.write(f"SPAN {float(v)}GHz"))

    def set_power(self):
        """
        Prompt for output power (dBm) in [-70, +5] and send POWE command.
        """
        def callback(v):
            try:
                power = float(v)
                if power < -70 or power > 5:
                    raise ValueError("Power must be between -70 and +5 dBm.")
                self.vna_ctrl.write(f"POWE {power}")
            except Exception as e:
                self._show_error_popup(f"Invalid power value: {e}")
        self._popup_entry("Enter POWER (dBm):", callback)

    # ---------------------- MISC ----------------------

    def _show_error_popup(self, message: str):
        """
        Display an error popup dialog with a single OK button.

        Args:
            message (str): Error text to show.
        """
        popup = ctk.CTkToplevel(self)
        popup.title("Input Error")
        popup.geometry("360x140")
        popup.resizable(False, False)

        label = ctk.CTkLabel(popup, text=message, wraplength=320)
        label.pack(pady=14, padx=12)

        ok_btn = ctk.CTkButton(popup, text="OK", command=popup.destroy)
        ok_btn.pack(pady=(0, 12))

    def handle_close(self):
        """
        Close the window safely.
        """
        try:
            self.destroy()
        except Exception:
            pass