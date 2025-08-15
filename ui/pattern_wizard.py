import threading
import csv
import os
import time
import datetime
import json
import tkinter as tk
import customtkinter as ctk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import ui.session
import sys
from typing import Optional
from interfaces.arduino_interface import ArduinoRotationStage, ArduinoStageConfig  # Arduino rotation stage (same as Manual Mode)
import settings


class PatternWizard(ctk.CTkToplevel):
    """
    3D/2D pattern scan window for the anechoic range.

    Features
    -------
    - Full spherical and 2D slice scans (XY, φ=0, φ=90, custom).
    - Live plotting: 3D scatter for spherical scans, 2D line for slices.
    - Multi-test CSV logging with JSON metadata per block.
    - Thread-safe UI updates and graceful teardown (tracked `after()` calls).
    - Pause/Resume and Abort controls.

    Threading model
    ---------------
    - UI runs on the Tk main thread.
    - A single daemon worker thread (`ScanThread`) performs motion + VNA I/O.
    - All UI mutations from the worker must go through `safe_gui_update()`.

    Parameters
    ----------
    parent : tk.Misc
        Parent window.
    vna_ctrl : object
        VNA controller/driver with `.write(...)` and `.read_trace()` APIs.
    serial_ctrl : object
        Positioner controller with `.move_to(...)` and `.wait_for_idle(...)`.
    """

    # central place for VNA format labels
    FORMAT_LABELS = {
        "LOGM": "Magnitude (dB)",
        "PHAS": "Phase (deg)",
        "SMIC": "Smith Chart (complex)",
        "POLA": "Polar (complex)",
        "LINM": "Magnitude (linear)",
        "SWR": "SWR",
        "REAL": "Real Part",
        "IMAG": "Imaginary Part",
    }

    # Allowed VNA points when we ARE modifying the VNA
    ALLOWED_POINTS = ["201", "401", "801", "1601"]

    def __init__(self, parent, vna_ctrl, serial_ctrl,
                 rot_stage: Optional[ArduinoRotationStage] = None):
        """
        Initialize the Pattern Wizard window and default state.

        Notes
        -----
        - Installs a wrapper around `after()` to track all scheduled callbacks so
          they can be safely cancelled in `handle_close()`.
        - Does not start any scan—only builds the initial UI.
        """
        super().__init__(parent)

        self.title("3D Pattern Wizard")
        self.geometry("1100x750")
        self.resizable(True, True)
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.after(10, self.focus_force)

        # Silence any stray Tcl bgerror popups
        try:
            self.tk.call("rename", "bgerror", "orig_bgerror")
        except tk.TclError:
            pass
        self.tk.createcommand("bgerror", lambda *args: None)

        # HW handles
        self.vna = vna_ctrl
        self.serial = serial_ctrl

        # Rotation stage
        self.rot: Optional[ArduinoRotationStage] = rot_stage or ArduinoRotationStage(
            ArduinoStageConfig(port=getattr(settings, "ARDUINO_PORT", "COM7"))
        )
        self._rotation_connected = bool(self.rot is not None)  # soft flag
        self._last_rotation_deg = None  # cache optional
        self._active_polarization_label = None  # populated per polarization pass

        # state flags
        self.abort_flag = threading.Event()
        self.pause_flag = threading.Event()
        self.alive = True

        # runtime state
        self.data = []
        self.scan_thread = None
        self._after_ids = []         # all scheduled after() ids for cleanup
        self._orig_after = super().after
        self.after = self._schedule  # override to track IDs

        # polarization / rotation stage
        self.polarization_mode = "vertical"  # "vertical" | "horizontal" | "both"

        # user inputs
        self.theta_step = None
        self.phi_step = None
        self.freq_start = None
        self.freq_stop = None
        self.freq_points = None
        self.power_level = None
        self.selected_format = None
        self.csv_path = None
        self.test_label = "Unknown Test"
        self.selected_mode = None

        # custom slice inputs
        self.custom_fixed_axis = None
        self.custom_fixed_angle = None
        self.custom_step_size = None

        # plotting buffers
        self._plot_buffer = []
        self._plot_counter = 0
        self.freq_data = {}          # {freq: ([angles], [vals])}
        self.selected_freq = None

        # plot options state
        self.plot_title_var = tk.StringVar(value="Live Pattern")
        self.grid_var = tk.BooleanVar(value=False)
        self.y_axis_limits = None  # (ymin, ymax) or None (applies to 2D only)

        # VNA behavior
        self.no_vna_var = tk.BooleanVar(value=False)  # "Do not modify VNA"
        self.no_vna_note_label = None  # note label shown when checkbox is ON

        # placeholders created in show_param_form
        self.title_entry = None
        self.grid_check = None
        self.y_min_entry = None
        self.y_max_entry = None

        # CSV block tracking
        self._csv_block_open = False

        # UI
        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.handle_close)

    # ---------- infra / scheduling ----------

    def _set_rotation_deg(self, target_deg: float, timeout: float = 60.0):
        """
        Command the Arduino rotation stage to an absolute angle using the same API
        as Manual Mode. Best-effort; non-fatal on errors.
        """
        if not self.rot:
            return
        try:
            # skip redundant command if unchanged (within fp noise)
            if self._last_rotation_deg is not None and abs(self._last_rotation_deg - target_deg) < 1e-6:
                return

            self.rot.move_abs_deg(target_deg)

            # Prefer firmware handshake (BUSY/DONE) and fall back to time estimate if needed
            ok = False
            try:
                ok = self.rot.wait_until_done(timeout=timeout)
            except Exception:
                ok = False

            if not ok:
                # Fallback: conservative time wait (kept for robustness)
                delta = target_deg if self._last_rotation_deg is None else (target_deg - self._last_rotation_deg)
                self.rot.wait_estimate(delta)

            self._last_rotation_deg = target_deg
        except Exception as e:
            # Non-fatal: surface the issue but allow scans to proceed
            self.safe_gui_update(self.label, text=f"Rotation stage error: {e}")

    def _restore_vertical(self):
        """Best-effort return to 0° (vertical) using deterministic wait, then fallback."""
        if not self.rot:
            return
        try:
            self.rot.move_abs_deg(0.0)
            ok = False
            try:
                ok = self.rot.wait_until_done(timeout=30.0)
            except Exception:
                ok = False
            if not ok:
                self.rot.wait_estimate(0.0 if self._last_rotation_deg is None else -self._last_rotation_deg)
            self._last_rotation_deg = 0.0
        except Exception:
            # swallow—end-of-scan cleanup should never hard-fail UI
            pass

    def _schedule(self, delay_ms, callback=None, *args):
        """
        Schedule a Tk callback and record its `after()` id for later cancellation.

        Parameters
        ----------
        delay_ms : int
            Delay in milliseconds before the callback fires.
        callback : Callable, optional
            Function to invoke on the main thread. If `None`, schedules a no-op tick.
        *args :
            Positional arguments forwarded to `callback`.

        Returns
        -------
        str | None
            The Tk `after()` identifier, or `None` if the widget no longer exists.
        """
        if not self.winfo_exists():
            return None
        if callback:
            aid = self._orig_after(delay_ms, callback, *args)
        else:
            aid = self._orig_after(delay_ms)
        self._after_ids.append(aid)
        return aid

    def safe_gui_update(self, widget_or_callable, set=None, **kwargs):
        """
        Safely mutate Tk widgets from any thread.

        Usage
        -----
        - Pass a callable to execute it on the main thread.
        - Or pass a widget and keyword args to apply `.configure(**kwargs)`.
        - If `set` is provided and the widget has `.set()`, it will be called.
        - If `pack=True` is present, `.pack()` is invoked (and removed from kwargs).

        Parameters
        ----------
        widget_or_callable : tk.Widget | Callable
            Target widget to configure, or a callable to run.
        set : Any, optional
            Value passed to the widget's `.set()` if available.
        **kwargs :
            Keyword arguments for `.configure()`. Use `pack=True` to also call `.pack()`.

        Notes
        -----
        All work is posted to the Tk event loop via `after(0, ...)`.
        """
        def upd():
            if not self.winfo_exists():
                return
            try:
                if callable(widget_or_callable):
                    widget_or_callable()
                    return
                w = widget_or_callable
                if set is not None and hasattr(w, "set"):
                    w.set(set)
                if "pack" in kwargs and callable(getattr(w, "pack", None)):
                    w.pack()
                config_kwargs = {k: v for k, v in kwargs.items() if k != "pack"}
                if config_kwargs:
                    w.configure(**config_kwargs)
            except Exception:
                pass

        if self.alive:
            self.after(0, upd)

    # ---------- top-level UI ----------

    def create_widgets(self):
        """
        Build the initial mode-selection UI (no plotting area yet).

        Creates
        -------
        - Label prompt
        - Mode buttons (Full, XY, φ=0, φ=90, Custom)
        - Abort / Pause buttons (disabled initially)
        - Close button
        """
        self.label = ctk.CTkLabel(self, text="Select scan type to begin")
        self.label.pack(pady=5)

        self.abort_btn = ctk.CTkButton(self, text="Abort", command=self.abort_scan, state="disabled")
        self.pause_btn = ctk.CTkButton(self, text="Pause", command=self.toggle_pause, state="disabled")

        self.full_scan_btn = ctk.CTkButton(self, text="Full 3D Scan",
                                           command=lambda: self.show_param_form("full"))
        self.xy_slice_btn = ctk.CTkButton(self, text="XY Slice (θ=90)",
                                          command=lambda: self.show_param_form("xy"))
        self.phi0_btn = ctk.CTkButton(self, text="Phi = 0 Slice",
                                      command=lambda: self.show_param_form("phi0"))
        self.phi90_btn = ctk.CTkButton(self, text="Phi = 90 Slice",
                                       command=lambda: self.show_param_form("phi90"))
        self.custom_slice_btn = ctk.CTkButton(self, text="Custom 2D Slice",
                                              command=lambda: self.show_param_form("custom"))

        for w in (self.full_scan_btn, self.xy_slice_btn, self.phi0_btn, self.phi90_btn, self.custom_slice_btn):
            w.pack(pady=5)

        self.close_btn = ctk.CTkButton(self, text="Close", command=self.handle_close)
        self.close_btn.pack(pady=5)

        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 120}x{self.winfo_reqheight() + 120}")

    # ---------- lifecycle ----------

    def handle_close(self):
        """
        Gracefully close the window and clean up background activity.

        Steps
        -----
        1. Set `alive=False` and signal `abort_flag`.
        2. Cancel all pending `after()` callbacks tracked in `_after_ids`.
        3. Join the scan worker thread briefly, if running.
        4. Disable controls and destroy the Toplevel.
        5. Ensure any open CSV block is closed.
        """
        self.alive = False
        self.abort_flag.set()

        # cancel pending after() callbacks
        for aid in self._after_ids:
            try:
                super().after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()

        # wait briefly for scan thread to exit
        if self.scan_thread and self.scan_thread.is_alive():
            try:
                self.scan_thread.join(timeout=1.0)
            except Exception:
                pass

        # disable controls
        for b in (self.abort_btn, self.pause_btn):
            try:
                b.configure(state="disabled")
            except Exception:
                pass

        # close any open block
        try:
            self.close_csv_block()
        except Exception:
            pass

        try:
            if self.rot is not None:
                self.rot.close()
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass

    def abort_scan(self):
        """
        Request a cooperative cancellation of the current scan.
        Sets `abort_flag` and disables the Abort button.
        """
        self.abort_flag.set()
        self.label.configure(text="Abort requested…")
        self.safe_gui_update(self.abort_btn, state="disabled")

    # ---------- parameter entry ----------

    def show_param_form(self, mode):
        """
        Display the parameter form for the selected scan mode.

        Parameters
        ----------
        mode : {"full", "xy", "phi0", "phi90", "custom"}
            Determines which angle fields are required and how the scan iterates.

        Side Effects
        ------------
        Hides the mode-selection UI and shows parameter entries, format dropdown,
        and control buttons. Initializes `self.entries`.
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

        # hide mode buttons + close
        for w in (self.full_scan_btn, self.xy_slice_btn, self.phi0_btn, self.phi90_btn, self.custom_slice_btn, self.close_btn):
            w.pack_forget()

        # clear old frames if exist
        for name in ("param_frame", "options_frame", "content_frame"):
            if hasattr(self, name):
                try:
                    getattr(self, name).destroy()
                except Exception:
                    pass

        # Two-column container
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.pack(pady=10, fill="x")

        # Left: parameter form
        self.param_frame = ctk.CTkFrame(self.content_frame)
        self.param_frame.grid(row=0, column=0, padx=(0, 8), sticky="n")

        # Right: plot options
        self.options_frame = ctk.CTkFrame(self.content_frame)
        self.options_frame.grid(row=0, column=1, padx=(8, 0), sticky="n")

        self.entries = {}

        # --- VNA control row (checkbox) ---
        vna_row = ctk.CTkFrame(self.param_frame)
        vna_row.pack(pady=(0, 6), fill="x")
        vna_cb = ctk.CTkCheckBox(
            vna_row,
            text='Do not modify VNA',
            variable=self.no_vna_var,
            command=self._on_no_vna_toggle
        )
        vna_cb.pack(side="left", padx=5)

        # Note (only when checkbox is ON)
        self.no_vna_note_label = ctk.CTkLabel(
            self.param_frame,
            text="(VNA won’t be configured; please still enter fields for informational use)",
            text_color=("gray60", "gray60")
        )
        # Initially hidden if unchecked
        if self.no_vna_var.get():
            self.no_vna_note_label.pack(pady=(0, 6), anchor="w", padx=5)

        # scalar entries (build all EXCEPT Freq Points here; that one is dynamic)
        base_fields = [
            ("Freq Start (GHz)", "freq_start"),
            ("Freq Stop (GHz)", "freq_stop"),
            # ("Freq Points", "freq_step")  # handled separately
            ("Power (dBm)", "power"),
            ("CSV Name", "csv_path"),
        ]
        if mode in ["full", "phi0", "phi90"]:
            base_fields.insert(0, ("Theta Step (°)", "theta_step"))
        if mode in ["full", "xy"]:
            base_fields.insert(0, ("Phi Step (°)", "phi_step"))
        if mode == "custom":
            base_fields.insert(0, ("Fixed Angle (°)", "fixed_angle"))
            base_fields.insert(1, ("Step Size", "step_size"))

        # custom slice: choose fixed axis
        if mode == "custom":
            axis_row = ctk.CTkFrame(self.param_frame)
            axis_row.pack(pady=3)
            ctk.CTkLabel(axis_row, text="Fixed Axis", width=140, anchor="w").pack(side="left", padx=5)
            axis_dropdown = ctk.CTkOptionMenu(axis_row, values=["phi", "theta"])
            axis_dropdown.set("phi")
            axis_dropdown.pack(side="left")
            self.entries["fixed_axis"] = axis_dropdown

        # measurement format
        format_row = ctk.CTkFrame(self.param_frame)
        format_row.pack(pady=3)
        ctk.CTkLabel(format_row, text="Measurement Format", width=140, anchor="w").pack(side="left", padx=5)
        self.entries["format"] = ctk.CTkOptionMenu(format_row, values=list(self.FORMAT_LABELS.keys()))
        self.entries["format"].set("LOGM")
        self.entries["format"].pack(side="left")

        # polarization selection
        pol_row = ctk.CTkFrame(self.param_frame)
        pol_row.pack(pady=3)
        ctk.CTkLabel(pol_row, text="Polarization", width=140, anchor="w").pack(side="left", padx=5)
        self.entries["polarization"] = ctk.CTkOptionMenu(
            pol_row,
            values=["Vertical (0°)", "Horizontal (90°)", "Both"]
        )
        self.entries["polarization"].set("Vertical (0°)")
        self.entries["polarization"].pack(side="left")

        # static scalar entries
        for label_text, key in base_fields:
            row = ctk.CTkFrame(self.param_frame)
            row.pack(pady=3)
            ctk.CTkLabel(row, text=label_text, width=140, anchor="w").pack(side="left", padx=5)
            entry = ctk.CTkEntry(row, width=120)
            entry.pack(side="left")
            self.entries[key] = entry

        # dynamic "Freq Points" control (dropdown if modify VNA; entry if not)
        self._build_freq_points_control(parent_frame=self.param_frame)

        #apply defaul values
        self._apply_param_defaults(mode)


        # ---------------- Right column: plot options ----------------
        # Title
        title_row = ctk.CTkFrame(self.options_frame)
        title_row.pack(pady=(3, 8), fill="x")
        ctk.CTkLabel(title_row, text="Plot Title", width=120, anchor="w").pack(side="left", padx=5)
        self.title_entry = ctk.CTkEntry(title_row, width=200)
        self.title_entry.insert(0, self.plot_title_var.get())
        self.title_entry.pack(side="left")

        # Gridlines
        grid_row = ctk.CTkFrame(self.options_frame)
        grid_row.pack(pady=3, fill="x")
        self.grid_check = ctk.CTkCheckBox(grid_row, text="Show gridlines", variable=self.grid_var)
        self.grid_check.pack(side="left", padx=5)

        # Y-axis limits (2D only)
        if mode != "full":
            yscale_row = ctk.CTkFrame(self.options_frame)
            yscale_row.pack(pady=3, fill="x")
            ctk.CTkLabel(yscale_row, text="Y-axis (min, max)", width=120, anchor="w").pack(side="left", padx=5)
            self.y_min_entry = ctk.CTkEntry(yscale_row, width=80)
            self.y_max_entry = ctk.CTkEntry(yscale_row, width=80)
            self.y_min_entry.insert(0, "-60")
            self.y_max_entry.insert(0, "0")
            self.y_min_entry.pack(side="left", padx=(0, 6))
            self.y_max_entry.pack(side="left")

        # Apply plot options
        apply_btn = ctk.CTkButton(self.options_frame, text="Apply Plot Options",
                                  command=self.apply_plot_options_now)
        apply_btn.pack(pady=(8, 3), fill="x")

        # control buttons (no Close here)
        self.start_btn = ctk.CTkButton(self, text="Start Scan", command=lambda m=mode: self.start_scan(m))
        self.start_btn.pack(pady=5)

        self.abort_btn.pack(pady=5)
        self.abort_btn.configure(state="disabled")
        self.pause_btn.pack(pady=5)
        self.pause_btn.configure(state="disabled")

        self.back_btn = ctk.CTkButton(self, text="Back", command=self.show_mode_selection)
        self.back_btn.pack(pady=5)

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.configure(width=300, height=50)
        self.progress_bar.set(0)
        self.progress_bar.pack_forget()

        self.label.configure(text=f"Selected: {mode.upper()} — enter parameters below")
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 120}x{self.winfo_reqheight() + 120}")

    def _apply_param_defaults(self, mode: str):
        """
        Fill sane default values into the form entries after they've been created.
        Safe to call even if some widgets aren't present for a given mode.
        """
        # Base defaults (common to all modes)
        defaults = {
            "freq_start": "8",  # GHz
            "freq_stop": "12",  # GHz
            "power": "-10",  # dBm
            "csv_path": f"pattern_{datetime.datetime.now():%Y%m%d_%H%M%S}",
        }

        # Mode-specific angle defaults
        if mode in ("full", "xy"):
            defaults["phi_step"] = "5"
        if mode in ("full", "phi0", "phi90"):
            defaults["theta_step"] = "5"
        if mode == "custom":
            defaults["fixed_angle"] = "0"
            defaults["step_size"] = "5"

        # Push defaults into any CTkEntry that exists
        for key, val in defaults.items():
            w = self.entries.get(key)
            try:
                if isinstance(w, ctk.CTkEntry):
                    w.delete(0, "end")
                    w.insert(0, str(val))
            except Exception:
                pass

    def _build_freq_points_control(self, parent_frame):
        """
        Create (or recreate) the 'Freq Points' control:
        - Dropdown with ALLOWED_POINTS when we WILL modify VNA.
        - Free entry when 'Do not modify VNA' is checked.
        Stores the widget under self.entries['freq_step'].
        """
        # Remove prior row, if any
        if hasattr(self, "_freq_points_row") and self._freq_points_row is not None:
            try:
                self._freq_points_row.destroy()
            except Exception:
                pass

        self._freq_points_row = ctk.CTkFrame(parent_frame)
        self._freq_points_row.pack(pady=3)
        ctk.CTkLabel(self._freq_points_row, text="Freq Points", width=140, anchor="w").pack(side="left", padx=5)

        if self.no_vna_var.get():
            # Free entry (informational only)
            widget = ctk.CTkEntry(self._freq_points_row, width=120)
            widget.insert(0, "401")
            widget.pack(side="left")
        else:
            # Restricted dropdown
            widget = ctk.CTkOptionMenu(self._freq_points_row, values=self.ALLOWED_POINTS)
            widget.set(self.ALLOWED_POINTS[1])  # default "401"
            widget.pack(side="left")

        self.entries["freq_step"] = widget

    def _on_no_vna_toggle(self):
        """
        Toggle handler for the 'Do not modify VNA' checkbox.
        Shows/hides the explanatory note and rebuilds the Freq Points control.
        """
        # Show or hide note
        try:
            if self.no_vna_var.get():
                if self.no_vna_note_label and not self.no_vna_note_label.winfo_ismapped():
                    self.no_vna_note_label.pack(pady=(0, 6), anchor="w", padx=5)
            else:
                if self.no_vna_note_label and self.no_vna_note_label.winfo_ismapped():
                    self.no_vna_note_label.pack_forget()
        except Exception:
            pass

        # Rebuild the Freq Points control to match mode
        if hasattr(self, "param_frame") and self.param_frame.winfo_exists():
            self._build_freq_points_control(parent_frame=self.param_frame)

    def apply_plot_options_now(self):
        """
        Read title/grid/ylim fields and apply immediately to existing plot.
        """
        # Title
        if self.title_entry is not None:
            title = self.title_entry.get().strip() or "Live Pattern"
            self.plot_title_var.set(title)

        # Gridlines
        grid_on = bool(self.grid_var.get())

        # Y-limits (2D only)
        if self.y_min_entry is not None and self.y_max_entry is not None:
            ylims = None
            y_min_txt = self.y_min_entry.get().strip()
            y_max_txt = self.y_max_entry.get().strip()
            try:
                y0 = float(y_min_txt)
                y1 = float(y_max_txt)
                if y0 < y1:
                    ylims = (y0, y1)
            except Exception:
                ylims = None
            self.y_axis_limits = ylims

        # Apply to 2D
        if hasattr(self, "ax2d"):
            try:
                self.ax2d.set_title(self.plot_title_var.get())
                self.ax2d.grid(grid_on)
                if self.y_axis_limits:
                    self.ax2d.set_ylim(*self.y_axis_limits)
                self.canvas.draw()
            except Exception:
                pass

        # Apply to 3D
        if hasattr(self, "ax"):
            try:
                self.ax.set_title(self.plot_title_var.get())
                self.ax.grid(grid_on)
                self.canvas.draw()
            except Exception:
                pass

    def show_mode_selection(self):
        """
        Return to the mode-selection screen and clear transient state.

        Actions
        -------
        - Destroys parameter widgets and any active Matplotlib canvas.
        - Removes frequency dropdown and plotting buffers.
        - Hides progress bar and resets pause/abort flags.
        - Restores the initial buttons (modes + Close).
        """
        # destroy param and buttons
        for attr in ("param_frame", "options_frame", "content_frame", "start_btn", "back_btn"):
            if hasattr(self, attr):
                w = getattr(self, attr)
                try:
                    if w.winfo_exists():
                        w.destroy()
                except Exception:
                    pass

        # destroy canvas/plot
        if hasattr(self, "canvas_widget") and getattr(self, "canvas_widget", None):
            try:
                if self.canvas_widget.winfo_exists():
                    self.canvas_widget.destroy()
            except Exception:
                pass

        for attr in ("canvas", "fig", "ax", "ax2d", "_line2d"):
            if hasattr(self, attr):
                delattr(self, attr)

        # remove freq dropdown
        if hasattr(self, "freq_dropdown") and getattr(self, "freq_dropdown", None):
            try:
                if self.freq_dropdown.winfo_exists():
                    self.freq_dropdown.pack_forget()
                    self.freq_dropdown.destroy()
            except Exception:
                pass
        for attr in ("freq_dropdown", "freq_dropdown_var"):
            if hasattr(self, attr):
                delattr(self, attr)

        # clear plotting data
        for attr in ("_xvals", "_yvals", "_plot_buffer", "_plot_counter", "freq_data", "selected_freq"):
            if hasattr(self, attr):
                try:
                    delattr(self, attr)
                except Exception:
                    pass

        # progress bar
        if hasattr(self, "progress_bar") and getattr(self, "progress_bar", None):
            try:
                if self.progress_bar.winfo_exists():
                    self.progress_bar.pack_forget()
            except Exception:
                pass

        # reset flags
        self.abort_flag.clear()
        self.pause_flag.clear()

        # show mode buttons again + close
        for w in (self.full_scan_btn, self.xy_slice_btn, self.phi0_btn, self.phi90_btn, self.custom_slice_btn, self.close_btn):
            w.pack(pady=5)

        # hide scan control buttons
        self.abort_btn.configure(state="disabled")
        self.abort_btn.pack_forget()
        self.pause_btn.configure(state="disabled")
        self.pause_btn.pack_forget()

        self.label.configure(text="Select scan type to begin")
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 120}x{self.winfo_reqheight() + 120}")

    # ---------- plotting ----------

    def setup_plot_area(self, mode="full"):
        """
        Create the Matplotlib canvas appropriate for the selected mode.

        Parameters
        ----------
        mode : str, default="full"
            If "full", initialize a 3D axes; otherwise, a 2D axes plus a frequency
            dropdown for selecting which trace to display.

        Notes
        -----
        No-op if a canvas already exists.
        """
        if hasattr(self, "canvas_widget") and self.canvas_widget and self.canvas_widget.winfo_exists():
            return

        self.fig = plt.figure(figsize=(6, 4.5))
        if mode == "full":
            self.ax = self.fig.add_subplot(111, projection="3d")
            self.ax.set_title(self.plot_title_var.get())
            self.ax.grid(bool(self.grid_var.get()))
        else:
            # frequency selection dropdown
            self.freq_dropdown_var = ctk.StringVar()
            self.freq_dropdown = ctk.CTkOptionMenu(self, variable=self.freq_dropdown_var, values=[],
                                                   command=self.on_freq_selected)
            self.freq_dropdown.pack(pady=5)

            self.selected_freq = None
            self.freq_data = {}
            self.ax2d = self.fig.add_subplot(111)
            self.ax2d.set_xlabel("Angle (deg)")
            self.ax2d.set_ylabel(self.get_y_axis_label())
            self.ax2d.set_title(self.plot_title_var.get())
            self.ax2d.grid(bool(self.grid_var.get()))
            if self.y_axis_limits:
                self.ax2d.set_ylim(*self.y_axis_limits)
            self._xvals, self._yvals = [], []
            self._line2d, = self.ax2d.plot([], [], "o-")  # default style

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)

    def get_y_axis_label(self):
        """
        Return the human-readable Y-axis label for the selected VNA format.

        Returns
        -------
        str
            Label derived from `FORMAT_LABELS` (defaults to "Measurement").
        """
        return self.FORMAT_LABELS.get(self.selected_format, "Measurement")

    def update_2d_plot(self, angle, y_val):
        """
        Append one point to the live 2D slice trace and redraw.

        Parameters
        ----------
        angle : float
            The sweep angle for the slice (θ or φ depending on mode).
        y_val : float
            Value to plot at that angle (e.g., magnitude in dB).
        """
        if not hasattr(self, "ax2d"):
            return
        self._xvals.append(angle)
        self._yvals.append(y_val)

        def draw():
            if not self.winfo_exists():
                return
            self._line2d.set_data(self._xvals, self._yvals)
            self.ax2d.set_xlabel("Angle (deg)")
            self.ax2d.set_ylabel(self.get_y_axis_label())
            self.ax2d.set_title(self.plot_title_var.get())
            self.ax2d.grid(bool(self.grid_var.get()))
            # enforce manual limits if provided
            if self.y_axis_limits:
                self.ax2d.set_ylim(*self.y_axis_limits)
            else:
                # fallback: minimal autoscale if no limits given
                self.ax2d.relim()
                self.ax2d.autoscale_view()
            self.canvas.draw()

        if self.alive:
            self.after(0, draw)

    def update_3d_plot(self, phi, theta, db_val):
        """
        Queue a 3D point for batched rendering.

        Parameters
        ----------
        phi : float
            Elevation angle in degrees (treated as polar angle).
        theta : float
            Azimuth angle in degrees.
        db_val : float
            Value in dB; converted to linear radius via r = 10**(dB/20).

        Notes
        -----
        Points are buffered and rendered every 10 samples to reduce UI overhead.
        """
        if not hasattr(self, "ax") or not hasattr(self, "canvas"):
            return

        r = 10 ** (db_val / 20.0)
        theta_rad = np.radians(theta)
        phi_rad = np.radians(phi)
        # NOTE: preserving your original mapping (phi as "elevation", theta as "azimuth")
        x = r * np.sin(phi_rad) * np.cos(theta_rad)
        y = r * np.sin(phi_rad) * np.sin(theta_rad)
        z = r * np.cos(phi_rad)

        self._plot_buffer.append((x, y, z))
        self._plot_counter += 1
        if self._plot_counter % 10 != 0:
            return

        def draw():
            if not self.winfo_exists() or not self._plot_buffer:
                return
            xs, ys, zs = zip(*self._plot_buffer)
            self.ax.scatter(xs, ys, zs, s=10)
            self.ax.set_title(self.plot_title_var.get())
            self.ax.grid(bool(self.grid_var.get()))
            self.canvas.draw()
            self._plot_buffer.clear()

        if self.alive:
            self.after(0, draw)

    def update_live_2d_plot(self, freq, angle, mag):
        """
        Cache an angle/value sample under a specific frequency and refresh if selected.

        Parameters
        ----------
        freq : float
            Frequency in GHz (as returned by the VNA trace).
        angle : float
            Sweep angle for this sample.
        mag : float
            Sample value (e.g., dB). Stored unrounded for plotting; CSV handles rounding.
        """
        if freq not in self.freq_data:
            self.freq_data[freq] = ([], [])
        self.freq_data[freq][0].append(angle)
        self.freq_data[freq][1].append(mag)
        if self.selected_freq == freq:
            self.update_2d_plot_from_data()

    def update_2d_plot_from_data(self):
        """
        Redraw the 2D slice using cached samples for `self.selected_freq`.
        No-op if no data or plot isn't initialized.
        """
        if not hasattr(self, "ax2d") or not self.selected_freq:
            return
        x_vals, y_vals = self.freq_data.get(self.selected_freq, ([], []))
        if not x_vals:
            return

        self.ax2d.clear()
        self.ax2d.plot(x_vals, y_vals, "o-")
        self.ax2d.set_xlabel("Angle (deg)")
        self.ax2d.set_ylabel(self.get_y_axis_label())
        self.ax2d.set_title(self.plot_title_var.get() or f"{self.get_y_axis_label()} @ {self.selected_freq:.3f} GHz")
        self.ax2d.grid(bool(self.grid_var.get()))
        if self.y_axis_limits:
            self.ax2d.set_ylim(*self.y_axis_limits)
        self.canvas.draw()

    def update_frequency_dropdown(self, new_values):
        """
        Update the frequency dropdown with new values.

        Parameters
        ----------
        new_values : list[str]
            Frequencies formatted as strings (e.g., '2.450').

        Behaviour
        --------
        - Preserves the current selection if still present.
        - Otherwise selects the first available value.
        - Triggers a plot refresh when the selection changes.
        """
        if hasattr(self, "freq_dropdown") and self.freq_dropdown and self.freq_dropdown.winfo_exists():
            current = self.freq_dropdown_var.get()
            self.freq_dropdown.configure(values=new_values)
            if current in new_values:
                self.freq_dropdown_var.set(current)
                new_selected = float(current)
            elif new_values:
                self.freq_dropdown_var.set(new_values[0])
                new_selected = float(new_values[0])
            else:
                new_selected = None

            if new_selected != self.selected_freq:
                self.selected_freq = new_selected
                if self.selected_freq is not None:
                    self.update_2d_plot_from_data()
        else:
            # create fresh
            self.freq_dropdown_var = ctk.StringVar()
            self.freq_dropdown = ctk.CTkOptionMenu(self, variable=self.freq_dropdown_var,
                                                   values=new_values, command=self.on_freq_selected)
            self.freq_dropdown.pack(pady=5)
            if new_values:
                self.freq_dropdown_var.set(new_values[0])
                self.selected_freq = float(new_values[0])
                self.update_2d_plot_from_data()

    def on_freq_selected(self, freq_str):
        """
        Handle a change in the frequency dropdown selection.

        Parameters
        ----------
        freq_str : str
            Selected frequency text; parsed to float and used as key into `freq_data`.
        """
        try:
            freq = float(freq_str)
            if freq in self.freq_data:
                self.selected_freq = freq
                self.update_2d_plot_from_data()
        except ValueError:
            pass

    # ---------- scanning ----------

    def _play_chime(self):
        """
        Play a short system notification sound (cross-platform).
        """
        try:
            if sys.platform.startswith("win"):
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            elif sys.platform == "darwin":
                os.system('afplay /System/Library/Sounds/Glass.aiff')
            else:
                # Linux (requires 'paplay' or 'aplay' to be installed)
                os.system(
                    'paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null || aplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null')
        except Exception:
            pass

    def start_scan(self, mode):
        """
        Validate inputs, configure the VNA, reset plots, and launch the scan worker.

        Parameters
        ----------
        mode : {"full", "xy", "phi0", "phi90", "custom"}
            Determines angle ranges and plotting mode.

        Raises
        ------
        ValueError
            If any user-provided parameter is invalid.
        RuntimeError
            If VNA configuration fails.

        Notes
        -----
        This method only starts the thread; actual scanning occurs in `run_scan()`.
        """
        try:
            # parse steps
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
                if fixed_axis not in ("phi", "theta"):
                    raise ValueError("Fixed axis must be 'phi' or 'theta'")
                self.custom_fixed_axis = fixed_axis
                self.custom_fixed_angle = fixed_angle
                self.custom_step_size = step_size

            # freq/power/format/csv
            self.freq_start = float(self.entries["freq_start"].get())
            self.freq_stop = float(self.entries["freq_stop"].get())
            # freq_points may come from dropdown or entry
            self.freq_points = float(self.entries["freq_step"].get())
            if not self.no_vna_var.get():
                # Validate against allowed set when we WILL modify the VNA
                if str(int(self.freq_points)) not in self.ALLOWED_POINTS:
                    raise ValueError(f"Freq Points must be one of {', '.join(self.ALLOWED_POINTS)} when VNA is modified.")
            self.power_level = float(self.entries["power"].get())
            if not (-70 <= self.power_level <= 5):
                raise ValueError("Power must be between -70 and 5 dBm.")
            self.selected_format = self.entries["format"].get()

            # title/grid
            if self.title_entry is not None:
                t = self.title_entry.get().strip()
                self.plot_title_var.set(t if t else "Live Pattern")

            # manual Y-axis limits for 2D plots
            if self.selected_mode != "full":
                ylims = None
                if self.y_min_entry is not None and self.y_max_entry is not None:
                    y_min_txt = self.y_min_entry.get().strip()
                    y_max_txt = self.y_max_entry.get().strip()
                    try:
                        y_min = float(y_min_txt)
                        y_max = float(y_max_txt)
                    except Exception:
                        raise ValueError("Y-axis limits must be numbers.")
                    if not (y_min < y_max):
                        raise ValueError("Y-axis min must be less than max.")
                    ylims = (y_min, y_max)
                self.y_axis_limits = ylims
            else:
                self.y_axis_limits = None

            filename = self.entries["csv_path"].get().strip()
            if not filename.endswith(".csv"):
                filename += ".csv"
            self.csv_path = os.path.join("csv", filename)
            ui.session.last_test_csv = self.csv_path

            # polarization mode (UI selection)
            pol_choice = self.entries["polarization"].get()
            if "Both" in pol_choice:
                self.polarization_mode = "both"
            elif "Horizontal" in pol_choice:
                self.polarization_mode = "horizontal"
            else:
                self.polarization_mode = "vertical"

        except ValueError as e:
            self.label.configure(text=f"Invalid input: {e}")
            return

        # configure VNA (skip if "Do not modify VNA" is checked)
        try:
            if not self.no_vna_var.get():
                self.vna_setup()
        except RuntimeError as e:
            self.label.configure(text=str(e))
            return

        # reset UI flags
        self.abort_flag.clear()
        self.pause_flag.clear()
        self.abort_btn.configure(state="normal")
        self.back_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.label.configure(text="Scanning…")
        self.data.clear()

        # reset plots
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
                self.ax2d.set_title(self.plot_title_var.get())
                self.ax2d.grid(bool(self.grid_var.get()))
                if self.y_axis_limits:
                    self.ax2d.set_ylim(*self.y_axis_limits)
                self._xvals = []
                self._yvals = []
                self._line2d, = self.ax2d.plot([], [], "o-")
                self.freq_data = {}
                self.selected_freq = None
                if hasattr(self, "freq_dropdown"):
                    self.freq_dropdown.configure(values=[], variable=self.freq_dropdown_var)

        if hasattr(self, "canvas"):
            self.canvas.draw()

        self.setup_plot_area(mode)
        self.pause_btn.configure(state="normal", text="Pause")
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 120}x{self.winfo_reqheight() + 120}")

        # worker thread
        self.scan_thread = threading.Thread(target=self.run_scan, args=(mode,), daemon=True, name="ScanThread")
        self.scan_thread.start()

    def run_scan(self, mode="full"):
        """
        Worker thread: orchestrate motion, measurement, plotting, and CSV logging.

        Steps
        -----
        1. Home/position at (0, 0).
        2. Open a new CSV block with JSON metadata.
        3. Build theta/phi ranges based on `mode` and parameters.
        4. For each (phi, theta):
           - Respect pause/abort flags.
           - Move the positioner and wait for idle.
           - Read VNA trace and append CSV rows.
           - Update live plot(s) and progress bar.
        5. Return to (0, 0), set final status label, close the block, and clean up.

        Notes
        -----
        UI updates are marshalled to the main thread via `safe_gui_update()`/`after()`.
        """
        # Home to 0,0 as controller expects (before any polarization pass)
        try:
            self.serial.move_to(0, 0)
            if hasattr(self.serial, "wait_for_idle"):
                self.serial.wait_for_idle(60)
        except Exception as e:
            self.safe_gui_update(self.label, text=f"Positioner error: {e}")
            self._scan_cleanup()
            return

        # Precompute angle ranges once; they are the same for each polarization pass
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

        # Determine the polarization plan (label, absolute rotation in degrees)
        if self.polarization_mode == "both":
            pol_plan = [("vertical", 0.0), ("horizontal", 90.0)]
        elif self.polarization_mode == "horizontal":
            pol_plan = [("horizontal", 90.0)]
        else:
            pol_plan = [("vertical", 0.0)]

        # --- Main polarization loop: one CSV block per polarization -------------
        for idx, (pol_label, pol_angle) in enumerate(pol_plan):
            if self.abort_flag.is_set():
                break

            # Record human-readable label for CSV and UI
            self._active_polarization_label = pol_label

            # If doing BOTH, clear plots when switching to horizontal (second pass)
            if self.polarization_mode == "both" and idx == 1:
                if hasattr(self, "ax2d"):
                    try:
                        self.ax2d.cla()
                        self.ax2d.set_xlabel("Angle (deg)")
                        self.ax2d.set_ylabel(self.get_y_axis_label())
                        self.ax2d.set_title(self.plot_title_var.get())
                        self.ax2d.grid(bool(self.grid_var.get()))
                        if self.y_axis_limits:
                            self.ax2d.set_ylim(*self.y_axis_limits)
                        self._xvals, self._yvals = [], []
                        self._line2d, = self.ax2d.plot([], [], "o-")
                        self.canvas.draw()
                    except Exception:
                        pass
                if hasattr(self, "ax"):
                    try:
                        self.ax.cla()
                        self.ax.set_title(self.plot_title_var.get())
                        self.ax.grid(bool(self.grid_var.get()))
                        self.canvas.draw()
                    except Exception:
                        pass

            # Move rotation stage using the same API as Manual Mode (abs deg + wait_estimate)
            self._set_rotation_deg(pol_angle)
            self.safe_gui_update(self.label, text=f"Scanning… ({pol_label})")

            # Start a fresh CSV block for this polarization
            try:
                self.open_csv_block(self.csv_path)
            except Exception as e:
                self.safe_gui_update(self.label, text=f"CSV error: {e}")
                self._scan_cleanup()
                return

            total_steps = len(theta_range) * len(phi_range)
            done_steps = 0
            self.safe_gui_update(self.progress_bar, set=0, pack=True)
            self.data.clear()
            all_freqs = set()  # track freqs to populate dropdown

            # ---------------- Angle loops ----------------
            for phi in phi_range:
                if self.abort_flag.is_set():
                    break

                for theta in theta_range:
                    if self.abort_flag.is_set():
                        break

                    # pause loop
                    while self.pause_flag.is_set():
                        if self.abort_flag.is_set():
                            try:
                                self.serial.move_to(0, 0)
                            except Exception:
                                pass
                            self.safe_gui_update(self.label, text="Scan aborted.")
                            self.close_csv_block()
                            self._scan_cleanup()
                            return
                        time.sleep(0.1)

                    # move
                    try:
                        self.serial.move_to(phi, theta)
                        self.serial.wait_for_idle(60)
                    except Exception as e:
                        self.safe_gui_update(self.label, text=f"Positioner error: {e}")
                        self.close_csv_block()
                        self._scan_cleanup()
                        return

                    # measure
                    try:
                        freqs, mags = self.vna.read_trace()
                        # record all points
                        for f, m in zip(freqs, mags):
                            row = (phi, theta, f, round(m, 2))
                            self.data.append(row)
                            self.append_csv_row(self.csv_path, row)

                            # for 2D frequency selection cache
                            angle_key = {
                                "xy": phi,
                                "phi0": theta,
                                "phi90": theta,
                                "custom": theta if self.custom_fixed_axis == "phi" else phi,
                            }.get(mode, 0)
                            self.update_live_2d_plot(f, angle_key, m)
                            all_freqs.add(f)

                        # mid-band value for quick plotting
                        if np.size(mags) > 0:
                            mid_idx = int(np.size(freqs) // 2)
                            mid_val = mags[mid_idx] if 0 <= mid_idx < np.size(mags) else mags[-1]

                            if mode == "full":
                                self.update_3d_plot(phi, theta, mid_val)
                            else:
                                sweep_angle = {
                                    "xy": phi,
                                    "phi0": theta,
                                    "phi90": theta,
                                    "custom": theta if self.custom_fixed_axis == "phi" else phi,
                                }.get(mode, 0)
                                self.update_2d_plot(sweep_angle, mid_val)

                    except Exception as e:
                        self.safe_gui_update(self.label, text=f"VNA error: {e}")
                        self.close_csv_block()
                        self._scan_cleanup()
                        return

                    # progress
                    done_steps += 1
                    self.safe_gui_update(self.progress_bar, set=done_steps / total_steps)

                # update freq dropdown once per phi row
                if mode != "full" and all_freqs:
                    sorted_vals = sorted(all_freqs)
                    display_vals = [f"{val:.3f}" for val in sorted_vals]
                    self.after(0, lambda vals=display_vals: self.update_frequency_dropdown(vals))

            # flush 3D buffer for this polarization
            if mode == "full" and self._plot_buffer:
                self.safe_gui_update(self.flush_3d_plot_buffer)

            # Close CSV block for this polarization
            self.close_csv_block()

        # finish: try to return to home and restore vertical polarization
        try:
            self.serial.move_to(0, 0)
        except Exception:
            pass
        try:
            if hasattr(self.serial, "wait_for_idle"):
                self.serial.wait_for_idle(60)
        except Exception:
            pass

        # robust vertical restore (even if last pass was horizontal)
        self._restore_vertical()

        if not self.abort_flag.is_set():
            msg = "Scan complete"
            msg += " (both polarizations)." if self.polarization_mode == "both" else f" ({self.polarization_mode})."
            self.safe_gui_update(self.label, text=msg + " Results saved.")
            self._play_chime()
        else:
            self.safe_gui_update(self.label, text="Scan aborted.")

        # cleanup common UI state
        self._scan_cleanup()

    def flush_3d_plot_buffer(self):
        """
        Render and clear any buffered 3D points to the canvas.
        No-op if there is no 3D axes or buffer is empty.
        """
        if not hasattr(self, "ax") or not self._plot_buffer:
            return
        xs, ys, zs = zip(*self._plot_buffer)
        self.ax.scatter(xs, ys, zs, s=10)
        self.ax.set_title(self.plot_title_var.get())
        self.ax.grid(bool(self.grid_var.get()))
        self.canvas.draw()
        self._plot_buffer.clear()

    def toggle_pause(self):
        """
        Toggle the scan between paused and running states and update button/label text.
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
        """
        Restore UI controls to the idle state after a scan completes or aborts.

        Effects
        -------
        - Hides the progress bar.
        - Re-enables Back/Start; disables Abort/Pause.
        - Keeps any status message set by the caller.
        """
        self.safe_gui_update(self.progress_bar.pack_forget)
        self.safe_gui_update(self.back_btn, state="normal")
        self.safe_gui_update(self.start_btn, state="normal")
        self.safe_gui_update(self.abort_btn, state="disabled")
        self.safe_gui_update(self.pause_btn, state="disabled")

    # ---------- CSV (JSON header blocks) ----------

    def open_csv_block(self, filename):
        """
        Start a new test block in a multi-test CSV, writing block markers,
        a JSON config line, meta lines, then the column header.
        """
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        label = self.FORMAT_LABELS.get(self.selected_format, "Measurement")

        # Build JSON metadata for this test
        cfg = {
            "name": self.test_label,                # e.g., "Full Spherical Scan"
            "mode": self.selected_mode,             # "full", "xy", "phi0", "phi90", "custom"
            "polarization": self._active_polarization_label,  # record active polarization
            "sweep": {
                "start_ghz": float(self.freq_start),
                "stop_ghz": float(self.freq_stop),
                "points": int(self.freq_points),
                "format": self.selected_format,
                "power_dbm": float(self.power_level),
            },
            "grid": {
                "phi_step_deg": float(self.phi_step) if self.phi_step is not None else None,
                "theta_step_deg": float(self.theta_step) if self.theta_step is not None else None,
                "custom_axis": self.custom_fixed_axis,
                "custom_angle_deg": float(self.custom_fixed_angle) if self.custom_fixed_angle is not None else None,
                "custom_step_deg": float(self.custom_step_size) if self.custom_step_size is not None else None,
            },
            "plot_options": {
                "title": self.plot_title_var.get(),
                "grid": bool(self.grid_var.get()),
                "y_limits": self.y_axis_limits if self.y_axis_limits else None,
                "do_not_modify_vna": bool(self.no_vna_var.get()),
            },
            "created_local": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_utc": datetime.datetime.utcnow().isoformat() + "Z",
        }

        with open(filename, mode="a", newline="") as f:
            f.write("# --- TEST-START ---\n")
            f.write("# CONFIG_JSON: " + json.dumps(cfg, separators=(",", ":")) + "\n")
            # Optional META lines (best-effort device identity)
            try:
                ident = getattr(self.vna, "ident_string", None)
                vna_id = self.vna.ident_string() if callable(ident) else str(type(self.vna).__name__)
                f.write(f"# META: vna={vna_id}\n")
            except Exception:
                pass
            try:
                ident = getattr(self.serial, "ident_string", None)
                pos_id = self.serial.ident_string() if callable(ident) else str(type(self.serial).__name__)
                f.write(f"# META: positioner={pos_id}\n")
            except Exception:
                pass
            # polarization META
            try:
                f.write(f"# META: polarization={self._active_polarization_label}\n")
            except Exception:
                pass

            writer = csv.writer(f)
            writer.writerow(["Phi (deg)", "Theta (deg)", "Frequency (GHz)", label])

        self._csv_block_open = True
        # remember path for "Load Last Test"
        ui.session.last_test_csv = filename

    def append_csv_row(self, filename, row):
        """
        Append one data row to an existing CSV block.

        Parameters
        ----------
        filename : str
            CSV path.
        row : tuple
            (phi_deg, theta_deg, freq_ghz, value) to append.
        """
        with open(filename, mode="a", newline="") as f:
            csv.writer(f).writerow(row)

    def close_csv_block(self):
        """
        Close the current CSV test block by writing an end marker.
        Safe to call multiple times.
        """
        if not self._csv_block_open or not self.csv_path:
            return
        try:
            with open(self.csv_path, mode="a", newline="") as f:
                f.write("# --- TEST-END ---\n")
        finally:
            self._csv_block_open = False

    # ---------- VNA ----------

    def vna_setup(self):
        """
        Configure the VNA for a sweep and display format.

        Uses
        ----
        - STAR/STOP in GHz
        - POIN for number of points
        - POWE in dBm
        - Format token from `selected_format` (e.g., LOGM)

        Raises
        ------
        RuntimeError
            If any VNA command fails.
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