import customtkinter as ctk
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import ui.session
import os
import json
from io import StringIO


class DataAnalysisWindow(ctk.CTkToplevel):
    """
    Data analysis window for viewing antenna pattern tests from single- or multi-test CSVs.

    Features
    --------
    - Supports two multi-test formats:
        1) Legacy header style:
           # Test Type: ...
           # Date: ...
           #
           Phi (deg), Theta (deg), Frequency (GHz), Magnitude (dB)

        2) JSON block style (from PatternWizard):
           # --- TEST-START ---
           # CONFIG_JSON: {...}
           # META: key=value
           Phi (deg),Theta (deg),Frequency (GHz),<label from VNA format>
           ...

    - Builds a dropdown of tests, swaps active DataFrame on selection
    - Frequency dropdown updates per test
    - 2D slice and 3D scatter plotting, normalization toggle
    - Optional calibration offset CSV (freq_ghz, offset_db)
    """

    RENAME_MAP = {
        'Phi (deg)': 'phi_deg',
        'Theta (deg)': 'theta_deg',
        'Frequency (GHz)': 'freq_ghz',
        'Magnitude (dB)': 'mag_db',
        # common alternates
        'phi_deg': 'phi_deg',
        'theta_deg': 'theta_deg',
        'freq_ghz': 'freq_ghz',
        'mag_db': 'mag_db',
    }

    def __init__(self, parent):
        """Build window, widgets, and default state."""
        super().__init__(parent)
        self.title("Data Analysis")
        self.geometry("1200x800")
        self.attributes("-topmost", True)
        self.lift()
        self.after(10, lambda: self.focus_force())

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # active data for currently selected test
        self.df = None
        self.offset_df = None
        self.freq_list = []
        self.last_plot_mode = None

        # multi-test management
        self.test_blocks = []   # list of dicts: {meta: {...}, df: pd.DataFrame}
        self.test_labels = []   # strings for dropdown
        self.selected_test_label = ctk.StringVar(value="")  # label, not index

        self.create_widgets()

    # ==================== UI SETUP ====================

    def create_widgets(self):
        """Assemble variable holders, frames, plot canvas, and top controls."""
        self.create_control_vars()

        # Global label: shows calibration file name
        self.label_cal_file = ctk.CTkLabel(self, textvariable=self.cal_file_var, anchor="w")
        self.label_cal_file.pack(padx=20, pady=(10, 0), fill="x")

        self.create_frames()
        self.create_plot_area()
        self.create_buttons()

    def create_frames(self):
        """Create the plot area frame and the controls frame."""
        self.plot_frame = ctk.CTkFrame(self)
        self.plot_frame.pack(padx=20, pady=20, fill=ctk.BOTH, expand=True)
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(padx=20, pady=10, fill=ctk.X)

    def create_plot_area(self):
        """Create a Matplotlib Figure + canvas; toolbar is added when showing a plot."""
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.pack_forget()

    def create_control_vars(self):
        """Initialize Tk variables bound to UI controls."""
        self.freq_var = ctk.StringVar(value="")
        self.normalize_var = ctk.BooleanVar(value=False)
        self.slice_type_var = ctk.StringVar(value="phi")
        self.slice_value_var = ctk.StringVar(value="")
        self.cal_file_var = ctk.StringVar(value="No cal file loaded")

    def create_buttons(self):
        self.button_frame.grid_columnconfigure(0, weight=1)
        self.button_frame.grid_columnconfigure(1, weight=1)

        # row 0: normalize
        self.chk_normalize = ctk.CTkCheckBox(
            self.button_frame, text="Normalize to 0 dB",
            variable=self.normalize_var, command=self.refresh_current_plot
        )
        self.chk_normalize.grid(row=0, column=0, columnspan=2, padx=100, pady=5, sticky="w")

        # row 1: frequency dropdown
        self.freq_dropdown = ctk.CTkOptionMenu(
            self.button_frame, variable=self.freq_var, values=[], command=self.on_freq_change
        )
        self.freq_dropdown.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        # row 2: test selector
        self.test_selector = ctk.CTkOptionMenu(
            self.button_frame, values=[], variable=self.selected_test_label, command=self.on_test_selected
        )
        self.test_selector.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        # start action buttons at row 3+
        buttons = [
            ("Load CSV", self.load_csv),
            ("Load Last Test", self.load_last_csv),
            ("Load FSPL Offset", lambda: self.load_csv(cal=True)),
            ("Plot 2D Slice", self.plot_2d_slice),
            ("Plot 3D Spherical", self.plot_3d_spherical),
            ("Export PNG", lambda: self.export_plot("png")),
            ("Export PDF", lambda: self.export_plot("pdf")),
            ("Close", self.handle_close),
        ]
        base_row = 3
        for i, (text, cmd) in enumerate(buttons):
            self._add_button(self.button_frame, base_row + i, text, cmd)

    def _add_button(self, frame, row, text, command):
        """Convenience for a full-width button row."""
        ctk.CTkButton(frame, text=text, command=command).grid(
            row=row, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )

    # ==================== DATA LOADING ====================

    def load_csv(self, cal=False):
        """
        Prompt for a CSV and load either calibration offsets or multi-test data.
        """
        file_path = filedialog.askopenfilename(
            initialdir=os.path.join(os.getcwd(), 'csv'),
            filetypes=[("CSV Files", "*.csv")]
        )
        if not file_path:
            return

        if cal:
            self._load_csv_from_path(file_path, cal=True)
        else:
            # prefer multi-test parsing; fall back to single-test read if needed
            if not self.parse_multi_test_csv(file_path):
                self._load_csv_from_path(file_path, cal=False)

    def load_last_csv(self):
        """Load the last test file path stored in session."""
        file_path = ui.session.last_test_csv
        if file_path and os.path.exists(file_path):
            if not self.parse_multi_test_csv(file_path):
                self._load_csv_from_path(file_path, cal=False)
        else:
            print("No last test file found or path invalid.")

    def _load_csv_from_path(self, file_path, cal=False):
        """
        Load a non-block single CSV (either calibration or a single test).
        """
        try:
            df = pd.read_csv(file_path, header=0)
            if cal:
                df.rename(columns={
                    'Frequency (GHz)': 'freq_ghz',
                    'Correction (dB)': 'offset_db',
                    'Offset (dB)': 'offset_db',
                }, inplace=True, errors="ignore")
                df = df.astype({'freq_ghz': float, 'offset_db': float})
                self.offset_df = df
                self.cal_file_var.set(f"Cal file: {os.path.basename(file_path)}")
                print("Loaded calibration data:", file_path)
                return

            # Single test
            df = self.apply_common_column_renames(df)
            # If still no mag_db but exactly 4+ columns, use the last column as mag_db
            if 'mag_db' not in df.columns and len(df.columns) >= 4:
                last_col = df.columns[-1]
                df.rename(columns={last_col: 'mag_db'}, inplace=True)
            df = df.astype({
                'phi_deg': float,
                'theta_deg': float,
                'freq_ghz': float,
                'mag_db': float
            })
            self.test_blocks = [{"meta": {"type": "Single CSV", "date": ""}, "df": df}]
            self.test_labels = ["Single CSV"]
            self.test_selector.configure(values=self.test_labels)
            self.test_selector.set(self.test_labels[0])
            self.on_test_selected()
            print(f"Loaded single CSV: {file_path}")
        except Exception as e:
            print("Error loading file:", e)

    # ---------- Multi-test CSV parsing ----------

    def parse_multi_test_csv(self, filepath) -> bool:
        """
        Parse a CSV file that may contain multiple tests, populating test_blocks and dropdown.

        Returns
        -------
        bool
            True if multi-test blocks were found and parsed; False otherwise.
        """
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
        except OSError as e:
            print("Failed to read CSV:", e)
            return False

        # Try block-style first
        blocks = self._split_blocks_blockstyle(lines)
        if not blocks:
            # Try legacy header style
            blocks = self._split_blocks_legacy(lines)

        if not blocks:
            return False

        self.test_blocks.clear()
        self.test_labels.clear()

        for b in blocks:
            meta = b.get("meta", {"type": "Unknown", "date": ""})
            data_str = b.get("data", "")
            if not data_str.strip():
                continue
            try:
                df = pd.read_csv(StringIO(data_str))
            except Exception as e:
                print("Failed to read CSV block:", e)
                continue

            # rename columns to canonical names; try to derive mag_db if alt header used
            df = self.apply_common_column_renames(df)

            # Some block-style logs may have freq in Hz -> convert to GHz if found
            if "freq_hz" in df.columns and "freq_ghz" not in df.columns:
                try:
                    df["freq_ghz"] = df["freq_hz"].astype(float) / 1e9
                except Exception:
                    pass

            # Pick a magnitude column; prefer 'mag_db', else take last 4th+ column as magnitude
            if "mag_db" not in df.columns:
                for cand in ("s21_db", "s11_db", "magnitude_db", "Magnitude (dB)"):
                    if cand in df.columns:
                        df["mag_db"] = df[cand]
                        break
                if "mag_db" not in df.columns and len(df.columns) >= 4:
                    df.rename(columns={df.columns[-1]: "mag_db"}, inplace=True)

            # enforce numeric types (skip if missing)
            cast_map = {}
            for col in ("phi_deg", "theta_deg", "freq_ghz", "mag_db"):
                if col in df.columns:
                    cast_map[col] = float
            try:
                df = df.astype(cast_map)
            except Exception:
                pass

            self.test_blocks.append({"meta": meta, "df": df})

        # Build labels & bind dropdown
        if not self.test_blocks:
            return False

        self.test_labels = [
            f"{i+1}. {tb['meta'].get('type','Unknown')} {('(' + tb['meta'].get('date','') + ')') if tb['meta'].get('date') else ''}".strip()
            for i, tb in enumerate(self.test_blocks)
        ]
        self.test_selector.configure(values=self.test_labels)
        self.test_selector.set(self.test_labels[0])  # <- use widget setter
        self.on_test_selected()
        print(f"Loaded multi-test file: {os.path.basename(filepath)} ({len(self.test_blocks)} tests)")
        return True

    def _split_blocks_blockstyle(self, lines):
        """
        Split by '# --- TEST-START ---' ... '# --- TEST-END ---' with optional CONFIG_JSON/META lines.
        """
        BLOCK_START = "# --- TEST-START ---"
        BLOCK_END = "# --- TEST-END ---"
        CFG_PREFIX = "# CONFIG_JSON:"
        META_PREFIX = "# META:"

        blocks = []
        inside = False
        meta = {}
        data_lines = []

        def finalize():
            if data_lines:
                blocks.append({"meta": meta or {"type": "Unknown", "date": ""}, "data": "\n".join(data_lines)})

        for ln in lines:
            s = ln.rstrip("\n")
            if s.startswith(BLOCK_START):
                if data_lines:
                    finalize()
                inside = True
                meta = {}
                data_lines = []
                continue
            if s.startswith(BLOCK_END):
                inside = False
                finalize()
                meta = {}
                data_lines = []
                continue
            if not inside:
                continue

            if s.startswith(CFG_PREFIX):
                # extract test name/date if present
                try:
                    cfg = json.loads(s.split(":", 1)[1].strip())
                    name = cfg.get("name") or cfg.get("test_label") or "Unknown"
                    meta["type"] = name
                    # if config has timestamp fields:
                    meta["date"] = cfg.get("created_utc", "") or cfg.get("started_utc", "")
                except Exception:
                    pass
                continue
            if s.startswith(META_PREFIX):
                try:
                    kv = s[len(META_PREFIX):].strip()
                    k, v = kv.split("=", 1)
                    meta[k.strip()] = v.strip()
                except Exception:
                    pass
                continue

            # data (header + rows)
            data_lines.append(s)

        # trailing block
        if data_lines:
            finalize()

        return blocks

    def _split_blocks_legacy(self, lines):
        """
        Split by legacy:
          # Test Type: XYZ
          # Date: 2025-08-08 12:00:00
          #
          Phi (deg),Theta (deg),Frequency (GHz),Magnitude (dB)
          ...
        """
        blocks = []
        meta = {"type": "Unknown", "date": ""}
        data_lines = []
        inside = False

        def finalize():
            if data_lines:
                blocks.append({"meta": meta.copy(), "data": "\n".join(data_lines)})

        for ln in lines:
            s = ln.strip("\n")
            if s.startswith("# Test Type:"):
                # close previous
                if data_lines:
                    finalize()
                    data_lines = []
                meta = {"type": s.split(":", 1)[1].strip(), "date": meta.get("date", "")}
                inside = False
                continue
            if s.startswith("# Date:"):
                meta["date"] = s.split(":", 1)[1].strip()
                continue
            if s.strip() == "#":
                inside = True
                continue
            if inside:
                # header + rows until next '# Test Type:' or EOF
                data_lines.append(s)

        if data_lines:
            finalize()
        return blocks

    # ==================== COLUMN NORMALIZATION ====================

    def apply_common_column_renames(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rename any known column variants to canonical names expected by the app.
        """
        df.columns = [col.strip() for col in df.columns]
        col_map = {}
        # exact/loose match for known headers
        for orig_name, new_name in self.RENAME_MAP.items():
            for actual_col in df.columns:
                if actual_col.strip().lower() == orig_name.lower():
                    col_map[actual_col] = new_name
        df = df.rename(columns=col_map)

        # if we still don't have expected columns, try lowercase fallbacks
        low = {c.lower(): c for c in df.columns}
        if "phi_deg" not in df.columns and "phi" in low:
            df.rename(columns={low["phi"]: "phi_deg"}, inplace=True)
        if "theta_deg" not in df.columns and "theta" in low:
            df.rename(columns={low["theta"]: "theta_deg"}, inplace=True)
        if "freq_ghz" not in df.columns and "frequency (ghz)" in low:
            df.rename(columns={low["frequency (ghz)"]: "freq_ghz"}, inplace=True)
        if "mag_db" not in df.columns and "magnitude (db)" in low:
            df.rename(columns={low["magnitude (db)"]: "mag_db"}, inplace=True)

        return df

    # ==================== DROPDOWNS & SELECTION ====================

    def update_freq_options(self):
        """
        Rebuild the frequency dropdown from the current DataFrame.
        """
        if self.df is None or 'freq_ghz' not in self.df.columns:
            self.freq_dropdown.configure(values=[])
            self.freq_var.set("")
            return
        freqs = sorted(pd.unique(self.df['freq_ghz'].astype(float)))
        self.freq_list = [f"{f:.3f}" for f in freqs]
        self.freq_dropdown.configure(values=self.freq_list)
        if self.freq_list:
            self.freq_var.set(self.freq_list[0])
        else:
            self.freq_var.set("")
        self.on_freq_change()

    def on_freq_change(self, _=None):
        """
        React to a frequency change; if a plot is active, refresh it.
        """
        self.refresh_current_plot()

    def populate_test_selector(self):
        """
        Populate the tests dropdown using parsed blocks.
        (Kept for compatibility with your previous flow.)
        """
        if not self.test_blocks:
            self.test_selector.configure(values=[])
            self.selected_test_label.set("")
            return
        self.test_labels = [
            f"{i+1}. {tb['meta'].get('type','Unknown')} ({tb['meta'].get('date','')})"
            for i, tb in enumerate(self.test_blocks)
        ]
        self.test_selector.configure(values=self.test_labels)
        self.selected_test_label.set(self.test_labels[0])
        self.on_test_selected()

    def on_test_selected(self, *_):
        """
        Swap the active DataFrame to the selected test and rebuild frequency options.
        """
        if not self.test_blocks or not self.test_labels:
            return

        label = self.selected_test_label.get()  # CTkOptionMenu passes this via the tk variable

        # Preferred: labels start with "N. ..."
        idx = None
        try:
            idx = int(label.split(".", 1)[0]) - 1
        except Exception:
            pass

        # Fallback: exact label lookup
        if idx is None or not (0 <= idx < len(self.test_blocks)):
            try:
                idx = self.test_labels.index(label)
            except ValueError:
                idx = 0

        self.df = self.test_blocks[idx]['df']
        self.update_freq_options()
        self.refresh_current_plot()

    # ==================== UTILITY ====================

    def get_freq_filtered_df(self):
        """
        Return a copy of the active DataFrame filtered to the selected frequency,
        applying calibration offset if available.
        """
        if self.df is None or 'freq_ghz' not in self.df.columns:
            return None
        try:
            freq = float(self.freq_var.get())
            # Use isclose for robustness
            subset = self.df[np.isclose(self.df['freq_ghz'].astype(float), freq, rtol=0, atol=1e-6)].copy()

            # === Apply correction offset (optional) ===
            if getattr(self, 'offset_df', None) is not None:
                offset = float(np.interp(freq, self.offset_df['freq_ghz'], self.offset_df['offset_db']))
            else:
                offset = 0.0

            if 'mag_db' in subset.columns:
                subset['mag_db_corrected'] = subset['mag_db'].astype(float) + offset
            return subset

        except Exception as e:
            print("Invalid frequency selection or correction error:", e)
            return None

    def validate_columns(self, required):
        """
        Verify the active DataFrame contains required columns.
        """
        if self.df is None:
            print("No data loaded.")
            return False
        missing = [col for col in required if col not in self.df.columns]
        if missing:
            print(f"Missing columns: {missing}")
            return False
        return True

    def clear_plot_area(self):
        """Remove any existing toolbar/canvas packing from the plot frame."""
        for widget in self.plot_frame.winfo_children():
            widget.pack_forget()

    def show_plot(self):
        """Attach toolbar and canvas to the plot frame."""
        self.clear_plot_area()
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.update()
        self.toolbar.pack(side=ctk.TOP, fill=ctk.X, pady=(0, 10))
        self.canvas.get_tk_widget().pack(fill=ctk.BOTH, expand=True)

    def refresh_current_plot(self):
        """Refresh whichever plot mode was last used."""
        if self.last_plot_mode == '2d':
            slice_df = self.get_freq_filtered_df()
            if slice_df is not None:
                self.plot_2d_slice_with_selection(slice_df)
        elif self.last_plot_mode == '3d':
            self.plot_3d_spherical()

    def _default_plot_basename(self) -> str:
        """
        Build a descriptive default filename from the current test label,
        plot mode, and frequency selection.
        """
        # Current test label (string like "1. Full Spherical (2025-08-08)")
        label = getattr(self, "selected_test_label", None)
        test_label = label.get() if label else "plot"

        # Frequency (e.g., "2.450")
        freq_txt = (self.freq_var.get() or "").strip().replace(" ", "")
        if freq_txt:
            freq_txt = f"{freq_txt}GHz"

        # Mode (2d or 3d)
        mode = self.last_plot_mode or "plot"

        # Tidy up unsafe filename chars
        base = "_".join(filter(None, [test_label, freq_txt, mode]))
        for ch in r'\/:*?"<>|':
            base = base.replace(ch, "_")
        return base or "plot"

    def export_plot(self, ext: str = "png"):
        """
        Export the currently displayed plot to an image/PDF.

        Parameters
        ----------
        ext : {"png", "pdf"}
            Output format. PNG is raster (with dpi); PDF is vector.
        """
        # Ensure there is something to export
        if not hasattr(self, "figure") or self.figure is None:
            print("No figure to export.")
            return

        # Build default filename
        base = self._default_plot_basename()
        defext = f".{ext.lower()}"
        ft = [("PNG Image", "*.png")] if ext.lower() == "png" else [("PDF Document", "*.pdf")]
        try:
            path = filedialog.asksaveasfilename(
                initialdir=os.getcwd(),
                initialfile=f"{base}{defext}",
                defaultextension=defext,
                filetypes=ft,
                title=f"Export plot as {ext.upper()}"
            )
            if not path:
                return

            # Save with nice defaults
            if ext.lower() == "png":
                self.figure.savefig(path, dpi=300, bbox_inches="tight")
            else:
                self.figure.savefig(path, bbox_inches="tight")

            print(f"Exported plot: {path}")
        except Exception as e:
            print(f"Failed to export plot: {e}")

    def handle_close(self):
        """Destroy the window safely."""
        try:
            self.destroy()
        except Exception:
            pass

    # ==================== PLOTTING ====================

    def plot_2d_slice(self):
        """
        Choose a slice (phi=const or theta=const) from the current test and plot a 2D cut.
        """
        if not self.validate_columns(['theta_deg', 'phi_deg', 'mag_db', 'freq_ghz']):
            return

        slice_df = self.get_freq_filtered_df()
        if slice_df is None or slice_df.empty:
            print("No data at selected frequency.")
            return

        unique_phi = sorted(pd.unique(slice_df['phi_deg'].astype(float)))
        unique_theta = sorted(pd.unique(slice_df['theta_deg'].astype(float)))

        if len(unique_phi) > 1 and len(unique_theta) > 1:
            self.ask_slice_selection_dialog(unique_phi, unique_theta)
        else:
            if len(unique_phi) == 1:
                self.slice_type_var.set("phi")
                self.slice_value_var.set(f"{unique_phi[0]:.2f}")
            else:
                self.slice_type_var.set("theta")
                self.slice_value_var.set(f"{unique_theta[0]:.2f}")
            self.plot_2d_slice_with_selection(slice_df)

    def ask_slice_selection_dialog(self, unique_phi, unique_theta):
        """
        Pop up a small dialog to choose slice type/value when both vary.
        """
        dlg = ctk.CTkToplevel(self)
        dlg.title("Select 2D Slice")
        dlg.geometry("320x200")
        dlg.grab_set()

        local_slice_type_var = ctk.StringVar(value="phi")
        local_slice_value_var = ctk.StringVar(value=f"{unique_phi[0]:.2f}")

        ctk.CTkLabel(dlg, text="Slice by:").pack(pady=5)
        ctk.CTkRadioButton(dlg, text="Phi (\u03d5)", variable=local_slice_type_var, value="phi").pack(anchor="w")
        ctk.CTkRadioButton(dlg, text="Theta (\u03b8)", variable=local_slice_type_var, value="theta").pack(anchor="w")

        ctk.CTkLabel(dlg, text="Slice value (degrees):").pack(pady=5)
        entry_value = ctk.CTkEntry(dlg, textvariable=local_slice_value_var)
        entry_value.pack(pady=5, fill='x', padx=20)

        def on_slice_type_change(*_):
            if local_slice_type_var.get() == "phi":
                local_slice_value_var.set(f"{unique_phi[0]:.2f}")
            else:
                local_slice_value_var.set(f"{unique_theta[0]:.2f}")

        local_slice_type_var.trace_add('write', on_slice_type_change)

        def on_confirm():
            try:
                self.slice_type_var.set(local_slice_type_var.get())
                self.slice_value_var.set(local_slice_value_var.get())
                dlg.destroy()
                slice_df = self.get_freq_filtered_df()
                self.plot_2d_slice_with_selection(slice_df)
            except Exception as e:
                print("Failed to confirm slice selection:", e)

        ctk.CTkButton(dlg, text="Plot Slice", command=on_confirm).pack(pady=10)

    def plot_2d_slice_with_selection(self, slice_df):
        """
        Render a 2D slice for the selected frequency and slice definition.
        """
        try:
            slice_type = self.slice_type_var.get()
            slice_val = float(self.slice_value_var.get())
            filtered_df = slice_df[np.isclose(slice_df[f'{slice_type}_deg'].astype(float), slice_val, rtol=0, atol=1e-6)]
            if filtered_df.empty:
                print(f"No data found for {slice_type} = {slice_val}")
                return

            mag_db = filtered_df.get('mag_db_corrected', filtered_df['mag_db']).astype(float)
            if self.normalize_var.get():
                mag_db = mag_db - float(np.max(mag_db))

            self.figure.clf()
            self.ax = self.figure.add_subplot(111)

            if slice_type == 'phi':
                self.ax.plot(filtered_df['theta_deg'].astype(float), mag_db, label=f"\u03d5={slice_val:.2f}")
                self.ax.set_xlabel("Theta (\u00b0)")
            else:
                self.ax.plot(filtered_df['phi_deg'].astype(float), mag_db, label=f"\u03b8={slice_val:.2f}")
                self.ax.set_xlabel("Phi (\u00b0)")

            self.ax.set_ylabel("Magnitude (dB)")
            self.ax.set_title(f"2D Slice at {self.freq_var.get()} GHz")
            self.ax.grid(True)
            self.ax.legend()
            self.canvas.draw()
            self.show_plot()

            self.last_plot_mode = '2d'
        except Exception as e:
            print("Error in 2D slice with selection:", e)

    def plot_3d_spherical(self):
        """
        Render a 3D scatter of the selected-frequency spherical sample set.
        """
        if not self.validate_columns(['theta_deg', 'phi_deg', 'mag_db', 'freq_ghz']):
            return

        slice_df = self.get_freq_filtered_df()
        if slice_df is None or slice_df.empty:
            print("No data at selected frequency.")
            return

        try:
            theta = np.deg2rad(slice_df['theta_deg'].astype(float).values)
            phi = np.deg2rad(slice_df['phi_deg'].astype(float).values)

            mag_db = slice_df.get('mag_db_corrected', slice_df['mag_db']).astype(float).values
            if self.normalize_var.get():
                mag_db = mag_db - np.max(mag_db)
            r = 10 ** (mag_db / 20.0)

            # Match PatternWizard mapping: x = r*sin(phi)*cos(theta), etc.
            x = r * np.sin(phi) * np.cos(theta)
            y = r * np.sin(phi) * np.sin(theta)
            z = r * np.cos(phi)

            self.figure.clf()
            ax = self.figure.add_subplot(111, projection='3d')

            sc = ax.scatter(x, y, z, c=mag_db, cmap='viridis', marker='o')
            ax.set_title(f"3D Pattern at {self.freq_var.get()} GHz")
            cbar = self.figure.colorbar(sc, ax=ax, shrink=0.6, pad=0.1)
            cbar.set_label("Magnitude (dB)")

            self.last_plot_mode = '3d'
            self.canvas.draw()
            self.show_plot()
        except Exception as e:
            print("Error in 3D spherical plot:", e)

    # ==================== CALIBRATION LOADERS ====================

    def load_offset_file(self):
        """
        Load a calibration offset CSV into `offset_df` (expects freq_ghz, offset_db).
        """
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return
        try:
            df = pd.read_csv(file_path)
            df = df.astype({'freq_ghz': float, 'offset_db': float})
            self.offset_df = df
            print(f"Loaded offset file: {file_path}")
        except Exception as e:
            print("Failed to load offset file:", e)