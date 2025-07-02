import threading
import csv
import os
import tkinter as tk
import customtkinter as ctk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import ui.session


class PatternWizard(ctk.CTkToplevel):
    def __init__(self, parent, vna_ctrl, serial_ctrl):
        super().__init__(parent)
        self.title("3D Pattern Wizard")
        self.attributes("-topmost", True)
        self.geometry("1000x700")
        self.resizable(True, True)

        # Silence any stray Tcl bgerror popups
        try:
            self.tk.call("rename", "bgerror", "orig_bgerror")
        except tk.TclError:
            pass
        self.tk.createcommand("bgerror", lambda *args: None)

        self.vna = vna_ctrl
        self.serial = serial_ctrl

        self.abort_flag = threading.Event()
        self.data = []
        self.alive = True

        self.theta_step = None
        self.phi_step = None
        self.freq_stop = None
        self.freq_points = None
        self.freq_start = None
        self.csv_path = None

        # for tracking pending after() callbacks
        self._after_ids = []
        self._orig_after = super().after
        self.after = self._schedule  # monkey-patch instance .after

        # to plot in batches
        self._plot_buffer = []
        self._plot_counter = 0

        # keep handle on our scan thread
        self.scan_thread = None

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.handle_close)

    def _schedule(self, delay_ms, callback=None, *args):
        """Wraps after(): only schedules if widget still exists, records IDs."""
        if not self.winfo_exists():
            return None
        if callback:
            aid = self._orig_after(delay_ms, callback, *args)
        else:
            aid = self._orig_after(delay_ms)
        self._after_ids.append(aid)
        return aid

    def create_widgets(self):
        # Instruction label
        self.label = ctk.CTkLabel(self, text="Select scan type to begin")
        self.label.pack(pady=5)

        # Scan mode buttons
        self.abort_btn = ctk.CTkButton(self, text="Abort", command=self.abort_scan)
        self.abort_btn.configure(state="disabled")
        self.full_scan_btn = ctk.CTkButton(self, text="Full 3D Scan", command=lambda: self.show_param_form("full"))
        self.xy_slice_btn = ctk.CTkButton(self, text="XY Slice (θ=90)", command=lambda: self.show_param_form("xy"))
        self.phi0_btn = ctk.CTkButton(self, text="Phi = 0 Slice", command=lambda: self.show_param_form("phi0"))
        self.phi90_btn = ctk.CTkButton(self, text="Phi = 90 Slice", command=lambda: self.show_param_form("phi90"))
        self.custom_slice_btn = ctk.CTkButton(self, text="Custom 2D Slice",
                                              command=lambda: self.show_param_form("custom"))

        for w in (
                self.full_scan_btn,
                self.xy_slice_btn,
                self.phi0_btn,
                self.phi90_btn,
                self.custom_slice_btn
        ):
            w.pack(pady=5)

        # Close button only on
        # first screen
        self.close_btn = ctk.CTkButton(self, text="Close", command=self.handle_close)
        self.close_btn.pack(pady=5)

        self.update_idletasks()  # Calculate layout
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    def abort_scan(self):
        self.abort_flag.set()
        self.label.configure(text="Abort requested...")
        self.safe_gui_update(self.abort_btn, state="disabled")

    def handle_close(self):
        # 1) signal scan to stop
        self.alive = False
        self.abort_flag.set()
        self.safe_gui_update(self.abort_btn, state="disabled")
        # 2) cancel all pending callbacks
        for aid in self._after_ids:
            try:
                super().after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()

        # 3) wait briefly for the scan thread to exit
        if self.scan_thread and self.scan_thread.is_alive():
            self.scan_thread.join(timeout=1)

        # 4) destroy only this Toplevel
        try:
            self.destroy()
        except Exception:
            pass

    def run_scan(self, mode="full"):
        self.serial.move_to(0, 0)

        if mode == "full":
            theta_range = np.arange(0, 181, self.theta_step)
            phi_range = np.arange(0, 360, self.phi_step)
        elif mode == "xy":  # theta = 90, sweep phi
            theta_range = [90]
            phi_range = np.arange(0, 360, self.phi_step)
        elif mode == "phi0":  # phi = 0, sweep theta
            phi_range = [0]
            theta_range = np.arange(0, 360, self.theta_step)
        elif mode == "phi90":  # phi = 90, sweep theta
            phi_range = [90]
            theta_range = np.arange(0, 360, self.theta_step)
        elif mode == "custom":
            if self.custom_fixed_axis == "phi":
                phi_range = [self.custom_fixed_angle]
                theta_range = np.arange(0, 360, self.custom_step_size)
            else:
                theta_range = [self.custom_fixed_angle]
                phi_range = np.arange(0, 360, self.custom_step_size)
        else:
            self.safe_gui_update(self.label, text="Invalid scan mode.")
            return

        self.data.clear()
        for phi in phi_range:
            if self.abort_flag.is_set(): break
            for theta in theta_range:
                if self.abort_flag.is_set(): break
                try:
                    self.serial.move_to(phi, theta)
                    self.serial.wait_for_idle(60)
                except Exception as e:
                    return self.safe_gui_update(self.label, text=f"Positioner error: {e}")

                try:
                    freqs, mags = self.vna.read_trace()
                    dir_path = os.path.dirname(self.csv_path)
                    if not os.path.exists(dir_path):
                        os.makedirs(dir_path, exist_ok=True)
                    self.init_csv(self.csv_path)

                    for f, m in zip(freqs, mags):
                        row = (phi, theta, f, m)
                        self.data.append(row)
                        self.append_csv_row(self.csv_path, row)
                    if mode == "full":
                        mid_idx = len(freqs) // 2
                        m = mags[mid_idx]
                        self.update_3d_plot(phi, theta, m)
                except Exception as e:
                    return self.safe_gui_update(self.label, text=f"VNA error: {e}")

        if not self.abort_flag.is_set():
            self.serial.move_to(0, 0)
            self.safe_gui_update(self.label, text="Scan complete. Results saved.")
        else:
            self.serial.move_to(0, 0)
            self.safe_gui_update(self.label, text="Scan aborted.")

        self.safe_gui_update(self.full_scan_btn, state="normal")
        self.safe_gui_update(self.xy_slice_btn, state="normal")
        self.safe_gui_update(self.phi0_btn, state="normal")
        self.safe_gui_update(self.phi90_btn, state="normal")

    def init_csv(self, filename):
        """Create CSV with header if not already present."""
        if not os.path.exists(filename):
            with open(filename, mode="w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Phi (deg)", "Theta (deg)", "Frequency (GHz)", "Magnitude (dB)"])

    def append_csv_row(self, filename, row):
        """Append one row of data to the CSV."""
        with open(filename, mode="a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def update_3d_plot(self, phi, theta, db_val):
        if not hasattr(self, 'ax') or not hasattr(self, 'canvas'):
            return  # Don't plot if not set up
        r = 10 ** (db_val / 20)
        theta_rad = np.radians(theta)
        phi_rad = np.radians(phi)

        x = r * np.sin(phi_rad) * np.cos(theta_rad)
        y = r * np.sin(phi_rad) * np.sin(theta_rad)
        z = r * np.cos(phi_rad)

        self._plot_buffer.append((x, y, z))
        self._plot_counter += 1

        if self._plot_counter % 10 != 0:
            return

        def draw():
            if not self.winfo_exists():
                return
            xs, ys, zs = zip(*self._plot_buffer)
            self.ax.scatter(xs, ys, zs, s=10)
            self.ax.set_title("Live 3D Pattern")
            self.canvas.draw()
            self._plot_buffer.clear()

        if self.alive:
            self.after(0, draw)

    def safe_gui_update(self, widget, **kwargs):
        def upd():
            if not self.winfo_exists(): return
            try:
                widget.configure(**kwargs)
            except Exception:
                pass

        if self.alive:
            self.after(0, upd)

    def freq_setup(self):
        num_points = int(self.freq_points)
        try:
            self.vna.write("ABORT 7")
            self.vna.write("CLEAR 716")
            self.vna.write("PRES")
            self.vna.write("S21")
            self.vna.write(f"STAR {self.freq_start}GHZ")
            self.vna.write(f"STOP {self.freq_stop}GHZ")
            self.vna.write(f"POIN {num_points}")
            self.vna.write("CONT")
            # don't trigger a sweep here!
        except Exception as e:
            raise RuntimeError(f"VNA config error: {e}")

    def start_scan(self, mode):
        try:
            # Validate step entries by mode
            if "theta_step" in self.entries:
                self.theta_step = float(self.entries["theta_step"].get())
                if self.theta_step <= 0:
                    raise ValueError("Theta step must be > 0")
            if "phi_step" in self.entries:
                self.phi_step = float(self.entries["phi_step"].get())
                if self.phi_step <= 0:
                    raise ValueError("Phi step must be > 0")
            if mode == "custom":
                fixed_axis = self.entries["fixed_axis"].get().strip().lower()
                fixed_angle = float(self.entries["fixed_angle"].get())
                step_size = float(self.entries["step_size"].get())
                if fixed_axis not in ["phi", "theta"]:
                    self.label.configure(text="Fixed axis must be 'phi' or 'theta'")
                    return
                self.custom_fixed_axis = fixed_axis
                self.custom_fixed_angle = fixed_angle
                self.custom_step_size = step_size

            # Frequency settings
            self.freq_start = float(self.entries["freq_start"].get())
            self.freq_stop = float(self.entries["freq_stop"].get())
            self.freq_points = float(self.entries["freq_step"].get())

            # CSV path formatting
            filename = self.entries["csv_path"].get().strip()
            if not filename.endswith(".csv"):
                filename += ".csv"
            self.csv_path = os.path.join("csv", filename)
            ui.session.last_test_csv = self.csv_path
        except ValueError as e:
            self.label.configure(text=f"Invalid input: {e}")
            return

        try:
            self.freq_setup()
        except RuntimeError as e:
            self.label.configure(text=str(e))
            return

        self.abort_flag.clear()
        self.abort_btn.configure(state="normal")
        self.label.configure(text="Scanning...")
        self.data.clear()

        if mode == "full":
            self.setup_plot_area()

        self.full_scan_btn.configure(state="disabled")
        self.xy_slice_btn.configure(state="disabled")
        self.phi0_btn.configure(state="disabled")
        self.phi90_btn.configure(state="disabled")

        self.scan_thread = threading.Thread(target=self.run_scan, args=(mode,), daemon=True)
        self.scan_thread.start()

    def show_param_form(self, mode):
        self.selected_mode = mode

        # Hide mode buttons and Close button
        for w in (
                self.full_scan_btn,
                self.xy_slice_btn,
                self.phi0_btn,
                self.phi90_btn,
                self.close_btn,
        ):
            w.pack_forget()

        if hasattr(self, "param_frame"):
            self.param_frame.destroy()

        self.param_frame = ctk.CTkFrame(self)
        self.param_frame.pack(pady=10)

        self.entries = {}
        fields = [
            ("Freq Start (GHz)", "freq_start"),
            ("Freq Stop (GHz)", "freq_stop"),
            ("Freq Points", "freq_step"),
            ("CSV Path", "csv_path")
        ]
        if mode in ["full", "phi0", "phi90"]:
            fields.insert(0, ("Theta Step (°)", "theta_step"))
        if mode in ["full", "xy"]:
            fields.insert(0, ("Phi Step (°)", "phi_step"))
        if mode == "custom":
            fields.insert(0, ("Fixed Axis (phi/theta)", "fixed_axis"))
            fields.insert(1, ("Fixed Angle (°)", "fixed_angle"))
            fields.insert(2, ("Step Size", "step_size"))

        for label_text, key in fields:
            row = ctk.CTkFrame(self.param_frame)
            row.pack(pady=3)
            label = ctk.CTkLabel(row, text=label_text, width=140, anchor="w")
            label.pack(side="left", padx=5)
            entry = ctk.CTkEntry(row, width=100)
            entry.pack(side="left")
            self.entries[key] = entry

        # Pack buttons on param screen (No Close)
        self.start_btn = ctk.CTkButton(self, text="Start Scan", command=lambda: self.start_scan(mode))
        self.start_btn.pack(pady=5)

        # Now pack abort_btn (which was already created)
        self.abort_btn.pack(pady=5)
        self.abort_btn.configure(state="disabled")

        self.cancel_btn = ctk.CTkButton(self, text="Back", command=self.show_mode_selection)
        self.cancel_btn.pack(pady=5)

        self.label.configure(text=f"Selected: {mode.upper()} — enter parameters below")
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    def show_mode_selection(self):
        if hasattr(self, "param_frame"):
            self.param_frame.destroy()
        if hasattr(self, "start_btn"):
            self.start_btn.destroy()
        if hasattr(self, "cancel_btn"):
            self.cancel_btn.destroy()
        # Hide 3D canvas if it exists
        if hasattr(self, "canvas_widget") and self.canvas_widget.winfo_exists():
            self.canvas_widget.pack_forget()

        self.abort_btn.pack_forget()
        for w in (
                self.full_scan_btn,
                self.xy_slice_btn,
                self.phi0_btn,
                self.phi90_btn,
                self.close_btn,  # show close again here
        ):
            w.pack(pady=5)

        self.abort_btn.configure(state="disabled")
        self.abort_btn.pack_forget()  # hide abort on first screen

        self.label.configure(text="Select scan type to begin")
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    def setup_plot_area(self):
        if hasattr(self, "canvas_widget") and self.canvas_widget.winfo_exists():
            return  # already created

        self.fig = plt.figure(figsize=(5, 4))
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)
