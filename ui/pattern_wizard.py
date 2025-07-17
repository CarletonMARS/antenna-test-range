import threading
import csv
import os
import time
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
        self.power_level = None
        self.selected_format = None
        self.csv_path = None
        self.test_label = "Unknown Test"
        # Format label mapping
        self.format_labels = {
            "LOGM": "Magnitude (dB)",
            "PHAS": "Phase (deg)",
            "SMIC": "Smith Chart (complex)",
            "POLA": "Polar (complex)",
            "LINM": "Magnitude (linear)",
            "SWR": "SWR",
            "REAL": "Real Part",
            "IMAG": "Imaginary Part"
        }
        self.custom_fixed_axis = None

        self.custom_step_size = None
        self.custom_fixed_angle = None
        # for tracking pending after() callback
        self._after_ids = []
        self._orig_after = super().after
        self.after = self._schedule

        # to plot in batches
        self._plot_buffer = []
        self._plot_counter = 0

        # keep handle on scan thread
        self.scan_thread = None
        self.pause_flag = threading.Event()

        self.freq_data = {}
        self.selected_freq = None

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.handle_close)

    def _schedule(self, delay_ms, callback=None, *args):
        """
        Custom wrapper for `after()` that safely schedules GUI callbacks only if the widget exists.
        Also tracks scheduled IDs for cleanup on exit.

        Args:
            delay_ms (int): Delay in milliseconds.
            callback (function, optional): Function to call after delay.
            *args: Arguments to pass to the callback.

        Returns:
            ID of the scheduled `after()` callback or None if widget doesn't exist.
        """
        if not self.winfo_exists():
            return None
        if callback:
            aid = self._orig_after(delay_ms, callback, *args)
        else:
            aid = self._orig_after(delay_ms)
        self._after_ids.append(aid)
        return aid

    def create_widgets(self):
        """
        Initializes the UI controls shown on the main scan mode selection screen.
        Includes scan type buttons, abort and close options.
        """
        # Instruction label
        self.label = ctk.CTkLabel(self, text="Select scan type to begin")
        self.label.pack(pady=5)

        # Scan mode buttons
        self.abort_btn = ctk.CTkButton(self, text="Abort", command=self.abort_scan)
        self.abort_btn.configure(state="disabled")
        self.pause_btn = ctk.CTkButton(self, text="Pause", command=self.toggle_pause)

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
        """
        Signals the scan loop to abort as soon as possible.
        Updates the label and disables the Abort button.
        """
        self.abort_flag.set()
        self.label.configure(text="Abort requested...")
        self.safe_gui_update(self.abort_btn, state="disabled")

    def handle_close(self):
        """
        Closes the wizard window:
        - Sets abort flags
        - Cancels all scheduled `after()` callbacks
        - Waits for scan thread if running
        - Destroys the window
        """
        # 1) signal scan thread to stop
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

        self.safe_gui_update(self.pause_btn, state="disabled")

        # 4) destroy only this Toplevel
        try:
            self.destroy()
        except Exception:
            pass

    def start_scan(self, mode):
        """
        Parses UI entries, validates inputs, configures the VNA, and starts the scan thread.

        Args:
            mode (str): Selected scan type ("full", "xy", "phi0", "phi90", "custom").
        """
        try:
            # Validate angle steps
            if "theta_step" in self.entries:
                self.theta_step = float(self.entries["theta_step"].get())
                if self.theta_step <= 0:
                    raise ValueError("Theta step must be > 0")
            if "phi_step" in self.entries:
                self.phi_step = float(self.entries["phi_step"].get())
                if self.phi_step <= 0:
                    raise ValueError("Phi step must be > 0")
            if mode == "custom":
                fixed_axis = self.entries["fixed_axis"].get()
                fixed_angle = float(self.entries["fixed_angle"].get())
                step_size = float(self.entries["step_size"].get())
                if fixed_axis not in ["phi", "theta"]:
                    self.label.configure(text="Fixed axis must be 'phi' or 'theta'")
                    return
                self.custom_fixed_axis = fixed_axis
                self.custom_fixed_angle = fixed_angle
                self.custom_step_size = step_size

            self.freq_start = float(self.entries["freq_start"].get())
            self.freq_stop = float(self.entries["freq_stop"].get())
            self.freq_points = float(self.entries["freq_step"].get())
            self.power_level = float(self.entries["power"].get())
            if self.power_level < -70 or self.power_level > 5:
                raise ValueError("Power must be between -70 and 5 dBm.")
            self.selected_format = self.entries["format"].get()

            filename = self.entries["csv_path"].get().strip()
            if not filename.endswith(".csv"):
                filename += ".csv"
            self.csv_path = os.path.join("csv", filename)
            ui.session.last_test_csv = self.csv_path
        except ValueError as e:
            self.label.configure(text=f"Invalid input: {e}")
            return

        try:
            self.vna_setup()
        except RuntimeError as e:
            self.label.configure(text=str(e))
            return

        # Reset flags and prepare UI
        self.abort_flag.clear()
        self.pause_flag.clear()
        self.abort_btn.configure(state="normal")
        self.back_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.label.configure(text="Scanning...")
        self.data.clear()

        # Clear and reinit plots
        if mode == "full":
            if hasattr(self, "ax"):
                self.ax.cla()
            self._plot_buffer = []
            self._plot_counter = 0
        else:
            if hasattr(self, "ax2d"):
                self.ax2d.cla()
                self.ax2d.set_xlabel("Angle (deg)")
                self.ax2d.set_ylabel(self.get_y_axis_label())
                self.ax2d.set_title("Live 2D Pattern")
                self._xvals = []
                self._yvals = []
                self._line2d, = self.ax2d.plot([], [], 'bo-')  # Reinitialize line handle
                self.freq_data = {}
                self.selected_freq = None
                if hasattr(self, "freq_dropdown"):
                    self.freq_dropdown.configure(values=[], variable=self.freq_dropdown_var)

        if hasattr(self, "canvas"):
            self.canvas.draw()

        self.setup_plot_area(mode)
        self.pause_btn.configure(state="normal", text="Pause")
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

        self.scan_thread = threading.Thread(target=self.run_scan, args=(mode,), daemon=True)
        self.scan_thread.start()

    def run_scan(self, mode="full"):
        self.serial.move_to(0, 0)

        # Determine angle ranges
        if mode == "full":
            theta_range = np.arange(0, 181, self.theta_step)
            phi_range = np.arange(0, 360, self.phi_step)
        elif mode == "xy":
            theta_range = [90]
            phi_range = np.arange(0, 360, self.phi_step)
        elif mode == "phi0":
            phi_range = [0]
            theta_range = np.arange(0, 360, self.theta_step)
        elif mode == "phi90":
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

        total_steps = len(theta_range) * len(phi_range)
        done_steps = 0
        self.safe_gui_update(self.progress_bar, set=0, pack=True)
        self.data.clear()

        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        self.init_csv(self.csv_path)

        # Track frequencies found this scan iteration
        all_freqs = set()

        for phi in phi_range:
            if self.abort_flag.is_set():
                break
            for theta in theta_range:
                if self.abort_flag.is_set():
                    break
                while self.pause_flag.is_set():
                    if self.abort_flag.is_set():
                        self.serial.move_to(0, 0)
                        self.safe_gui_update(self.label, text="Scan aborted.")
                        self._scan_cleanup()
                        return
                    time.sleep(0.1)

                try:
                    self.serial.move_to(phi, theta)
                    self.serial.wait_for_idle(60)
                except Exception as e:
                    self.safe_gui_update(self.label, text=f"Positioner error: {e}")
                    self._scan_cleanup()
                    return

                try:
                    freqs, mags = self.vna.read_trace()

                    for f, m in zip(freqs, mags):
                        row = (phi, theta, f, round(m, 2))
                        self.data.append(row)
                        self.append_csv_row(self.csv_path, row)

                        angle = {
                            "xy": phi,
                            "phi0": theta,
                            "phi90": theta,
                            "custom": theta if self.custom_fixed_axis == "phi" else phi
                        }.get(mode, 0)

                        self.update_live_2d_plot(f, angle, m)

                        all_freqs.add(f)

                    mid_idx = len(freqs) // 2
                    m = mags[mid_idx]

                    if mode == "full":
                        self.update_3d_plot(phi, theta, m)
                    else:
                        sweep_angle = {
                            "xy": phi,
                            "phi0": theta,
                            "phi90": theta,
                            "custom": theta if self.custom_fixed_axis == "phi" else phi
                        }.get(mode, 0)
                        self.update_2d_plot(sweep_angle, m)

                except Exception as e:
                    self.safe_gui_update(self.label, text=f"VNA error: {e}")
                    self._scan_cleanup()
                    return

                done_steps += 1
                self.safe_gui_update(self.progress_bar, set=done_steps / total_steps)

            # Update frequency dropdown **once per phi iteration** in main thread safely
            if mode != "full" and all_freqs:
                sorted_vals = sorted(all_freqs)
                display_vals = [f"{val:.3f}" for val in sorted_vals]
                # Use after to update dropdown in main thread, not via safe_gui_update with lambda
                self.after(0, lambda vals=display_vals: self.update_frequency_dropdown(vals))

        # Flush 3D buffer if needed
        if mode == "full" and self._plot_buffer:
            self.safe_gui_update(self.flush_3d_plot_buffer)

        if not self.abort_flag.is_set():
            self.serial.move_to(0, 0)
            self.safe_gui_update(self.label, text="Scan complete. Results saved.")
        else:
            self.serial.move_to(0, 0)
            self.safe_gui_update(self.label, text="Scan aborted.")

        self._scan_cleanup()

    def init_csv(self, filename):
        """
        Appends a new test header and column labels to the existing CSV file,
        or creates a new CSV file with column headers if it doesn't already exist.

        Args:
            filename (str): Path to the CSV file to create.
        """
        import datetime
        is_new_file = not os.path.exists(filename)

        with open(filename, mode="a", newline="") as f:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n# Test Type: {self.test_label}\n")
            f.write(f"# Date: {now}\n")
            f.write("#\n")
            writer = csv.writer(f)
            label = self.format_labels.get(self.selected_format, "Measurement")
            writer.writerow(["Phi (deg)", "Theta (deg)", "Frequency (GHz)", label])
        self._is_first_write = is_new_file

    def append_csv_row(self, filename, row):
        """
        Appends a single row of scan data to the CSV file.

        Args:
            filename (str): CSV file path.
            row (tuple): A tuple of (phi, theta, frequency, magnitude).
        """
        with open(filename, mode="a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def on_freq_selected(self, freq_str):
        try:
            freq = float(freq_str)
            if freq in self.freq_data:
                self.selected_freq = freq
                self.update_2d_plot_from_data()
        except ValueError:
            pass

    def update_2d_plot_from_data(self):
        if not hasattr(self, "ax2d") or not self.selected_freq:
            return
        x_vals, y_vals = self.freq_data.get(self.selected_freq, ([], []))
        if not x_vals: return

        self.ax2d.clear()
        self.ax2d.plot(x_vals, y_vals, 'bo-')
        self.ax2d.set_xlabel("Angle (deg)")
        self.ax2d.set_ylabel(self.get_y_axis_label())
        self.ax2d.set_title(f"{self.get_y_axis_label()} @ {self.selected_freq:.3f} GHz")
        self.canvas.draw()

    def get_y_axis_label(self):
        label_map = {
            "LOGM": "Magnitude (dB)",
            "PHAS": "Phase (deg)",
            "SMIC": "Smith Chart (complex)",
            "POLA": "Polar (complex)",
            "LINM": "Magnitude (linear)",
            "SWR": "SWR",
            "REAL": "Real Part",
            "IMAG": "Imaginary Part"
        }
        return label_map.get(self.selected_format, "Measurement")

    def update_2d_plot(self, angle, db_val):
        """
        Updates the 2D live plot (for slice scans).

        Args:
            angle (float): Either theta or phi, depending on mode.
            db_val (float): Magnitude in dB.
        """
        if not hasattr(self, "ax2d"):
            return

        self._xvals.append(angle)
        self._yvals.append(db_val)

        def draw():
            if not self.winfo_exists():
                return
            self._line2d.set_data(self._xvals, self._yvals)
            self.ax2d.relim()
            self.ax2d.autoscale_view()
            self.canvas.draw()

        if self.alive:
            self.after(0, draw)

    def update_3d_plot(self, phi, theta, db_val):
        """
        Buffers and periodically renders 3D scatter plot points during a live scan.

        Args:
            phi (float): Phi angle in degrees.
            theta (float): Theta angle in degrees.
            db_val (float): Magnitude in dB.
        """
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



    def safe_gui_update(self, widget, set=None, **kwargs):
        """
        Safely updates a widget’s attributes from any thread by using `after()`.

        Args:
            widget (tk.Widget): The widget to update.
            **kwargs: Configuration options to apply.
        """
        def upd():
            if not self.winfo_exists(): return
            try:
                if set is not None and hasattr(widget, "set"):
                    widget.set(set)
                if "pack" in kwargs and callable(widget.pack):
                    widget.pack()
                widget.configure(**kwargs)
            except Exception:
                pass

        if self.alive:
            self.after(0, upd)

    def vna_setup(self):
        """
        Configures the VNA with user-specified frequency sweep settings.
        Raises RuntimeError if communication fails.
        """
        num_points = int(self.freq_points)
        try:
            self.vna.write("ABORT 7")
            self.vna.write("CLEAR 716")
            self.vna.write("PRES")
            self.vna.write("S21")
            self.vna.write(f"STAR {self.freq_start}GHZ")
            self.vna.write(f"STOP {self.freq_stop}GHZ")
            self.vna.write(f"POWE {self.power_level}")
            self.vna.write(f"POIN {num_points}")
            self.vna.write(f"{self.selected_format};")
            self.vna.write("CONT")
        except Exception as e:
            raise RuntimeError(f"VNA config error: {e}")

    def show_param_form(self, mode):
        """
        Displays a parameter form based on the selected scan type.
        Dynamically creates required input fields.

        Args:
            mode (str): Selected scan type.
        """
        self.selected_mode = mode
        mode_labels = {
            "full": "Full Spherical Scan",
            "xy": "XY Slice (theta = 90)",
            "phi0": "Phi = 0 Slice",
            "phi90": "Phi = 90 slice",
            "custom": "Custom 2D Slice",
        }
        self.test_label = mode_labels.get(mode, "Unknown Test")
        # Hide mode buttons and Close button
        for w in (
                self.full_scan_btn,
                self.xy_slice_btn,
                self.phi0_btn,
                self.phi90_btn,
                self.custom_slice_btn,
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
            ("Power (dBm)", "power"),
            ("CSV Path", "csv_path")
        ]
        if mode in ["full", "phi0", "phi90"]:
            fields.insert(0, ("Theta Step (°)", "theta_step"))
        if mode in ["full", "xy"]:
            fields.insert(0, ("Phi Step (°)", "phi_step"))
        if mode == "custom":
            fields.insert(0, ("Fixed Angle (°)", "fixed_angle"))
            fields.insert(1, ("Step Size", "step_size"))

        if mode == "custom":
            # dropdown for slice option in the case of custom test
            axis_row = ctk.CTkFrame(self.param_frame)
            axis_row.pack(pady=3)
            axis_label = ctk.CTkLabel(axis_row, text="Fixed Axis", width=140, anchor="w")
            axis_label.pack(side="left", padx=5)
            axis_dropdown = ctk.CTkOptionMenu(axis_row, values=["phi", "theta"])
            axis_dropdown.set("phi")  # default
            axis_dropdown.pack(side="left")
            self.entries["fixed_axis"] = axis_dropdown
        # Dropdown for measurement format
        format_row = ctk.CTkFrame(self.param_frame)
        format_row.pack(pady=3)

        format_label = ctk.CTkLabel(format_row, text="Measurement Format", width=140, anchor="w")
        format_label.pack(side="left", padx=5)

        self.entries["format"] = ctk.CTkOptionMenu(format_row, values=[
            "LOGM", "PHAS", "SMIC", "POLA", "LINM", "SWR", "REAL", "IMAG"
        ])
        self.entries["format"].set("LOGM")  # Default
        self.entries["format"].pack(side="left")
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

        # Now pack pause_btn and abort_btn (which was already created)
        self.abort_btn.pack(pady=5)
        self.abort_btn.configure(state="disabled")
        self.pause_btn.pack(pady=5)
        self.pause_btn.configure(state="disabled")

        self.back_btn = ctk.CTkButton(self, text="Back", command=self.show_mode_selection)
        self.back_btn.pack(pady=5)

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=5)
        self.progress_bar.configure(width=300, height=50)
        self.progress_bar.pack_forget()

        self.label.configure(text=f"Selected: {mode.upper()} — enter parameters below")
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    def show_mode_selection(self):
        """
        Returns to the scan mode selection screen from the parameter entry screen.
        Resets UI layout, removes any active widgets, and clears plotting state.
        """
        # Destroy parameter entry frame and buttons
        for attr in ["param_frame", "start_btn", "back_btn"]:
            if hasattr(self, attr):
                widget = getattr(self, attr)
                if widget.winfo_exists():
                    widget.destroy()

        # Destroy canvas and plot elements if they exist
        if hasattr(self, "canvas_widget") and self.canvas_widget.winfo_exists():
            self.canvas_widget.destroy()
        for attr in ["canvas", "fig", "ax", "ax2d", "_line2d"]:
            if hasattr(self, attr):
                delattr(self, attr)

        # Remove frequency dropdown if present
        if hasattr(self, "freq_dropdown") and self.freq_dropdown.winfo_exists():
            self.freq_dropdown.pack_forget()
            self.freq_dropdown.destroy()
        for attr in ["freq_dropdown", "freq_dropdown_var"]:
            if hasattr(self, attr):
                delattr(self, attr)

        # Clear plotting data
        for attr in ["_xvals", "_yvals", "_plot_buffer", "_plot_counter", "freq_data", "selected_freq"]:
            if hasattr(self, attr):
                delattr(self, attr)

        # Reset progress bar
        if hasattr(self, "progress_bar") and self.progress_bar.winfo_exists():
            self.progress_bar.pack_forget()

        # Reset scan state
        self.abort_flag.clear()
        self.pause_flag.clear()

        # Re-enable mode selection buttons and close button
        for w in (
                self.full_scan_btn,
                self.xy_slice_btn,
                self.phi0_btn,
                self.phi90_btn,
                self.custom_slice_btn,
                self.close_btn,
        ):
            w.pack(pady=5)

        # Disable and hide scan control buttons
        self.abort_btn.configure(state="disabled")
        self.abort_btn.pack_forget()
        self.pause_btn.configure(state="disabled")
        self.pause_btn.pack_forget()

        self.label.configure(text="Select scan type to begin")
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    def setup_plot_area(self, mode="full"):
        """
        Initializes the Matplotlib canvas for live plotting.
        If 'full' mode: creates 3D plot, otherwise creates 2D plot.
        """
        if hasattr(self, "canvas_widget") and self.canvas_widget.winfo_exists():
            return  # already created

        self.fig = plt.figure(figsize=(5, 4))
        if mode == "full":
            self.ax = self.fig.add_subplot(111, projection='3d')
        else:
            # Frequency selection dropdown
            self.freq_dropdown_var = ctk.StringVar()
            self.freq_dropdown = ctk.CTkOptionMenu(
                self,
                variable=self.freq_dropdown_var,
                values=[],
                command=self.on_freq_selected
            )
            self.freq_dropdown.pack(pady=5)

            self.selected_freq = None  # Tracks current frequency to display
            self.freq_data = {}  # Dict to hold data per frequency
            self.ax2d = self.fig.add_subplot(111)
            self.ax2d.set_xlabel("Angle (deg)")
            self.ax2d.set_ylabel("Magnitude (dB)")
            self.ax2d.set_title("Live 2D Pattern")
            self._xvals, self._yvals = [], []
            self._line2d, = self.ax2d.plot([], [], 'bo-')  # blue dots

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)

    def toggle_pause(self):
        """
        Toggles the pause state of the scan. When paused, the scan thread will wait.
        """
        if self.pause_flag.is_set():
            self.pause_flag.clear()
            self.pause_btn.configure(text="Pause")
            self.label.configure(text="Scan resumed.")
        else:
            self.pause_flag.set()
            self.pause_btn.configure(text="Resume")
            self.label.configure(text="Scan paused.")
    def _scan_cleanup(self):
        self.safe_gui_update(self.progress_bar.pack_forget)
        self.safe_gui_update(self.back_btn, state="normal")
        self.safe_gui_update(self.start_btn, state="normal")
        self.safe_gui_update(self.abort_btn, state="disabled")
        self.safe_gui_update(self.pause_btn, state="disabled")

    def update_frequency_dropdown(self, new_values):
        if hasattr(self, "freq_dropdown") and self.freq_dropdown.winfo_exists():
            current_selection = self.freq_dropdown_var.get()
            self.freq_dropdown.configure(values=new_values)

            # Keep selection if still available, else fallback to first
            if current_selection in new_values:
                self.freq_dropdown_var.set(current_selection)
                new_selected_freq = float(current_selection)
            elif new_values:
                self.freq_dropdown_var.set(new_values[0])
                new_selected_freq = float(new_values[0])
            else:
                new_selected_freq = None

            # Only update plot if selected_freq changed
            if new_selected_freq != self.selected_freq:
                self.selected_freq = new_selected_freq
                if self.selected_freq is not None:
                    self.update_2d_plot_from_data()
        else:
            # Create dropdown if it does not exist yet
            self.freq_dropdown_var = ctk.StringVar()
            self.freq_dropdown = ctk.CTkOptionMenu(
                self,
                variable=self.freq_dropdown_var,
                values=new_values,
                command=self.on_freq_selected
            )
            self.freq_dropdown.pack(pady=5)
            if new_values:
                self.freq_dropdown_var.set(new_values[0])
                self.selected_freq = float(new_values[0])
                self.update_2d_plot_from_data()
    def update_live_2d_plot(self, freq, angle, mag):
        """
        Add new data point to freq_data and update plot if freq == selected_freq.
        """
        if freq not in self.freq_data:
            self.freq_data[freq] = ([], [])
        self.freq_data[freq][0].append(angle)
        self.freq_data[freq][1].append(mag)

        if self.selected_freq == freq:
            self.update_2d_plot_from_data()
