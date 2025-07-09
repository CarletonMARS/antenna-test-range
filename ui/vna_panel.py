from docutils.parsers.rst.directives.images import Figure
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
        super().__init__(parent)
        self.vna_ctrl = vna_ctrl

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.attributes("-topmost", True)
        self.geometry("1200x800")
        self.resizable(True, True)
        self.title("AGILENT 8722ES SOFT FRONT PANEL")

        # Measurement Selection
        for i, name in enumerate(("S11", "S12", "S21", "S22")):
            btn = ctk.CTkButton(self, text=name, command=lambda n=name: self.select_sparam(n))
            btn.grid(row=0, column=i, padx=5, pady=5)

        # Frequency / Power Control
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
            btn = ctk.CTkButton(self, text=label, command=cmd)
            btn.grid(row=1, column=i, padx=5, pady=5)

        # Format Buttons
        formats = ["LOGM", "PHAS", "SMIC", "POLA", "LINM", "SWR", "REAL", "IMAG"]
        for i, fmt in enumerate(formats):
            btn = ctk.CTkButton(self, text=fmt, command=lambda f=fmt: self.vna_ctrl.write(f"{f};"))
            btn.grid(row=2, column=i, padx=3, pady=3)

        # Trace + Export
        self.trace_btn = ctk.CTkButton(self, text="DISPLAY TRACE", command=self.display_trace)
        self.trace_btn.grid(row=3, column=0, padx=10, pady=10)

        self.export_btn = ctk.CTkButton(self, text="EXPORT CSV", command=self.export_trace_csv)
        self.export_btn.grid(row=3, column=1, padx=10, pady=10)

        # Plot Area
        self.plot_frame = ctk.CTkFrame(self)
        self.plot_frame.grid(row=4, column=0, columnspan=10, padx=10, pady=10, sticky="nsew")
        self.canvas = None
        self.toolbar = None

        # Close button
        self.close_btn = ctk.CTkButton(self, text="close", command=self.handle_close)
        self.close_btn.grid(row=5, column=0, padx=10, pady=10)

        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    def select_sparam(self, sparam: str):
        self.vna_ctrl.select_sparam(sparam)

    def display_trace(self):
        try:
            freqs, mags = self.vna_ctrl.read_trace(channel="CHAN1")
            if self.canvas:
                self.canvas.get_tk_widget().destroy()
                self.toolbar.destroy()

            fig = Figure(figsize=(6, 4))
            ax = fig.add_subplot(111)
            ax.plot(freqs, mags)
            ax.set_xlabel("Freq (GHz)")
            ax.set_ylabel("Mag (dB)")
            ax.grid(True)

            # Optional custom ticks
            if len(freqs) > 1:
                ticks = np.linspace(freqs[0], freqs[-1], 10)
                ax.set_xticks(ticks)
                ax.set_xticklabels([f"{t:.2f}" for t in ticks])

            self.canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill="both", expand=True)

            self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
            self.toolbar.update()
            self.toolbar.pack(fill="x")
        except Exception as e:
            print(f"Error displaying trace: {e}")

    def export_trace_csv(self):
        try:
            freqs, mags = self.vna_ctrl.read_trace(channel="CHAN1")
            today = datetime.now().strftime("%Y-%m-%d")
            base_dir = f"C:/Users/alexszabo/Desktop/NEW POSITIONER FEB 2025/CSV EXPORTS/{today}"
            os.makedirs(base_dir, exist_ok=True)

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialdir=base_dir,
                title="Save CSV",
                filetypes=[("CSV files", "*.csv")]
            )
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

    # --- Frequency / Power popup handlers ---
    def set_start(self): self._popup_entry("Enter START freq (GHz):", lambda val: self.vna_ctrl.write(f"STAR {val}GHz"))
    def set_stop(self): self._popup_entry("Enter STOP freq (GHz):", lambda val: self.vna_ctrl.write(f"STOP {val}GHz"))
    def set_centre(self): self._popup_entry("Enter CENTRE freq (GHz):", lambda val: self.vna_ctrl.write(f"CENT {val}GHz"))
    def set_span(self): self._popup_entry("Enter SPAN (GHz):", lambda val: self.vna_ctrl.write(f"SPAN {val}GHz"))
    def set_power(self): self._popup_entry("Enter POWER (dBm):", lambda val: self.vna_ctrl.write(f"POWE {val}"))

    def _popup_entry(self, prompt: str, callback):
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
