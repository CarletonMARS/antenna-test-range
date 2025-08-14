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
    - Utility: display trace, export CSV, reset, refresh, close

    A live plot area occupies the bottom; toolbar appears when a trace is shown.
    Includes a stimulus readback panel showing current Start/Stop/Centre/Span/Power,
    and highlights the currently selected S-parameter button.
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
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.after(10, self.focus_force)

        # containers
        self.measure_frame = None
        self.stimulus_frame = None
        self.display_frame = None
        self.utility_frame = None
        self.readback_frame = None
        self.plot_frame = None

        # plot handles
        self.canvas = None
        self.toolbar = None

        # UI state
        self.sparam_buttons = {}       # name -> CTkButton
        self._btn_default_colors = {}  # name -> original fg_color tuple
        self.readback_labels = {}      # key -> CTkLabel
        self._selected_sparam = None

        self._build_layout()
        self.refresh_instrument_state()   # query S-param + stimulus, update UI

        # initial geometry after layout
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    # ---------------------- LAYOUT ----------------------

    def _build_layout(self):
        """
        Build the grouped layout: four top frames + readback + bottom plot area.
        """
        # grid config for window
        for c in range(4):
            self.grid_columnconfigure(c, weight=1)
        # row 0: groups, row 1: readback, row 4: plot area
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

        # Readback panel (spans full width below groups)
        self.readback_frame = ctk.CTkFrame(self)
        self.readback_frame.grid(row=1, column=0, columnspan=4, padx=10, pady=(0, 10), sticky="ew")
        self._create_readback_panel(self.readback_frame)

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
        Also capture their default colors to restore when deselecting.
        """
        params = ("S11", "S12", "S21", "S22")
        for i, name in enumerate(params, start=0):
            btn = self._btn(frame, row=1, col=i % 4, text=name, cmd=lambda n=name: self._on_click_sparam(n))
            self.sparam_buttons[name] = btn
            # store default fg_color (tuple for light/dark)
            try:
                self._btn_default_colors[name] = btn.cget("fg_color")
            except Exception:
                self._btn_default_colors[name] = None  # fallback

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
        Add trace display/export, reset, refresh, and close controls to the 'Utility' frame.
        """
        self._btn(frame, 1, 0, "DISPLAY TRACE", self.display_trace, colspan=2)
        self._btn(frame, 2, 0, "EXPORT CSV", self.export_trace_csv, colspan=2)
        self._btn(frame, 3, 0, "RESET VNA", lambda: self.vna_ctrl.write("*RST"), colspan=2)
        self._btn(frame, 4, 0, "REFRESH STATE", self.refresh_instrument_state, colspan=2)
        self._btn(frame, 5, 0, "CLOSE", self.handle_close, colspan=2)

    def _create_readback_panel(self, frame):
        """
        Build the stimulus readback panel (Start/Stop/Centre/Span/Power + S-parameter).
        """
        title = ctk.CTkLabel(frame, text="Stimulus Readback", font=("Helvetica", 14, "bold"))
        title.grid(row=0, column=0, columnspan=10, sticky="w", padx=8, pady=(8, 2))

        # keys: in order we’ll show them
        keys = ["start_ghz", "stop_ghz", "center_ghz", "span_ghz", "power_dbm", "sparam"]
        labels = ["Start (GHz)", "Stop (GHz)", "Centre (GHz)", "Span (GHz)", "Power (dBm)", "S-Param"]

        for i, (k, lbl) in enumerate(zip(keys, labels), start=0):
            ctk.CTkLabel(frame, text=f"{lbl}:", anchor="w").grid(row=1 + i // 3, column=(i % 3) * 2, padx=(8, 4), pady=6, sticky="w")
            vlabel = ctk.CTkLabel(frame, text="—", anchor="w", font=("Helvetica", 12, "bold"))
            vlabel.grid(row=1 + i // 3, column=(i % 3) * 2 + 1, padx=(0, 12), pady=6, sticky="w")
            self.readback_labels[k] = vlabel

        for c in range(6):
            frame.grid_columnconfigure(c, weight=1)

    # ---------------------- STATE / QUERY ----------------------

    def refresh_instrument_state(self):
        """
        Query the instrument for current S-parameter and stimulus settings.
        Updates the readback panel and highlights the selected S-parameter button.
        """
        try:
            # query S-parameter
            sparam = self._query_selected_sparam()
            if sparam:
                self._selected_sparam = sparam
                self._highlight_sparam(sparam)
                self._set_readback_value("sparam", sparam)

            # query stimulus
            stim = self._query_stimulus_settings()
            if stim:
                for k, v in stim.items():
                    self._set_readback_value(k, v)

        except Exception as e:
            # do not raise; keep UI responsive
            print(f"Refresh state failed: {e}")

    def _set_readback_value(self, key, value):
        """
        Set one field in the readback panel, formatting floats nicely.
        """
        lbl = self.readback_labels.get(key)
        if not lbl:
            return
        if isinstance(value, (int, float)):
            if "power" in key:
                txt = f"{value:.2f}"
            else:
                txt = f"{value:.6f}".rstrip("0").rstrip(".")
        else:
            txt = str(value)
        lbl.configure(text=txt)

    def _highlight_sparam(self, selected: str):
        """
        Color the selected S-parameter button green; restore others to default.
        """
        selected = (selected or "").upper()
        for name, btn in self.sparam_buttons.items():
            try:
                if name.upper() == selected:
                    btn.configure(fg_color="#1E9E62", hover_color="#197F50")  # pleasant green
                else:
                    default = self._btn_default_colors.get(name)
                    if default:
                        btn.configure(fg_color=default)  # restore theme color
                    else:
                        btn.configure(fg_color=None)      # fallback
            except Exception:
                pass

    def _query_selected_sparam(self):
        """
        Ask the VNA controller which S-parameter is active.

        Tries common method names:
        - get_selected_sparam()
        - query_selected_sparam()
        - current_sparam (property)
        Falls back to None if not available.
        """
        v = self.vna_ctrl
        for attr in ("get_selected_sparam", "query_selected_sparam"):
            fn = getattr(v, attr, None)
            if callable(fn):
                try:
                    s = fn()
                    if isinstance(s, str) and s.upper() in {"S11", "S12", "S21", "S22"}:
                        return s.upper()
                except Exception:
                    pass
        # property-like
        try:
            s = getattr(v, "current_sparam", None)
            if isinstance(s, str) and s.upper() in {"S11", "S12", "S21", "S22"}:
                return s.upper()
        except Exception:
            pass
        return None

    def _query_stimulus_settings(self):
        """
        Ask the VNA controller for stimulus settings.

        Tries, in order:
        - get_stimulus() -> dict with keys: start_ghz, stop_ghz, center_ghz, span_ghz, power_dbm
        - individual getters: get_start_ghz(), get_stop_ghz(), get_center_ghz(), get_span_ghz(), get_power_dbm()
        - query() strings if controller exposes a generic query (STAR? etc.) — optional

        Returns:
            dict | None
        """
        v = self.vna_ctrl
        # 1) unified getter
        get_all = getattr(v, "get_stimulus", None)
        if callable(get_all):
            try:
                d = get_all()
                if isinstance(d, dict):
                    return d
            except Exception:
                pass

        # 2) individual getters
        keys_funcs = {
            "start_ghz": "get_start_ghz",
            "stop_ghz": "get_stop_ghz",
            "center_ghz": "get_center_ghz",
            "span_ghz": "get_span_ghz",
            "power_dbm": "get_power_dbm",
        }
        out = {}
        for k, fn_name in keys_funcs.items():
            fn = getattr(v, fn_name, None)
            if callable(fn):
                try:
                    out[k] = float(fn())
                except Exception:
                    pass

        if out:
            return out

        # 3) optional generic query path (best-effort; safe if unsupported)
        q = getattr(v, "query", None)
        if callable(q):
            def _qnum(cmd):
                try:
                    r = q(cmd)
                    return float(str(r).strip())
                except Exception:
                    return None
            out = {
                "start_ghz": _qnum("STAR?"),
                "stop_ghz": _qnum("STOP?"),
                "center_ghz": _qnum("CENT?"),
                "span_ghz": _qnum("SPAN?"),
                "power_dbm": _qnum("POWE?"),
            }
            # keep only non-None
            out = {k: v for k, v in out.items() if v is not None}
            if out:
                return out

        return None

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
        popup.lift()
        popup.attributes("-topmost", True)
        popup.after(200, lambda: self.attributes("-topmost", False))
        popup.after(10, self.focus_force)
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

    def _on_click_sparam(self, sparam: str):
        """
        Handle a user click on an S-parameter button: set on VNA and update highlight.
        """
        try:
            self.vna_ctrl.select_sparam(sparam)
            self._selected_sparam = sparam.upper()
            self._highlight_sparam(self._selected_sparam)
            self._set_readback_value("sparam", self._selected_sparam)
        except Exception as e:
            print(f"Failed to select {sparam}: {e}")

    def select_sparam(self, sparam: str):
        """
        Select the active S-parameter (programmatic API-compatible entry point).

        Args:
            sparam (str): One of 'S11', 'S12', 'S21', 'S22'.
        """
        self._on_click_sparam(sparam)

    def set_start(self):
        """
        Prompt for start frequency (GHz) and send STAR command. Updates readback.
        """
        self._popup_entry("Enter START (GHz):", lambda v: self._set_and_refresh("STAR", "start_ghz", float(v)))

    def set_stop(self):
        """
        Prompt for stop frequency (GHz) and send STOP command. Updates readback.
        """
        self._popup_entry("Enter STOP (GHz):", lambda v: self._set_and_refresh("STOP", "stop_ghz", float(v)))

    def set_centre(self):
        """
        Prompt for center frequency (GHz) and send CENT command. Updates readback.
        """
        self._popup_entry("Enter CENTRE (GHz):", lambda v: self._set_and_refresh("CENT", "center_ghz", float(v)))

    def set_span(self):
        """
        Prompt for frequency span (GHz) and send SPAN command. Updates readback.
        """
        self._popup_entry("Enter SPAN (GHz):", lambda v: self._set_and_refresh("SPAN", "span_ghz", float(v)))

    def set_power(self):
        """
        Prompt for output power (dBm) in [-70, +5] and send POWE command. Updates readback.
        """
        def callback(v):
            try:
                power = float(v)
                if power < -70 or power > 5:
                    raise ValueError("Power must be between -70 and +5 dBm.")
                self.vna_ctrl.write(f"POWE {power}")
                self._set_readback_value("power_dbm", power)
            except Exception as e:
                self._show_error_popup(f"Invalid power value: {e}")
        self._popup_entry("Enter POWER (dBm):", callback)

    def _set_and_refresh(self, cmd_token: str, readback_key: str, value: float):
        """
        Send a numeric setting to the VNA with units and update the readback label.

        Args:
            cmd_token (str): SCPI-like command token (e.g., 'STAR', 'STOP', 'CENT', 'SPAN').
            readback_key (str): Key in the readback label dict to update.
            value (float): Value to send (GHz).
        """
        try:
            self.vna_ctrl.write(f"{cmd_token} {value}GHz")
            self._set_readback_value(readback_key, value)
        except Exception as e:
            self._show_error_popup(f"Failed to set {cmd_token}: {e}")

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