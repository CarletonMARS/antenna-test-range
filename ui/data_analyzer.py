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

    Supported inputs
    ----------------
    1) Legacy single/multi-test header style:
       # Test Type: ...
       # Date: ...
       #
       Phi (deg), Theta (deg), Frequency (GHz), Magnitude (dB)

    2) PatternWizard JSON block style:
       # --- TEST-START ---
       # CONFIG_JSON: {...}
       # META: key=value
       Phi (deg),Theta (deg),Frequency (GHz),<label from VNA format>
       ...
       # --- TEST-END ---

    Core features
    -------------
    - Parses multi-test CSVs into blocks with labels and per-block metadata.
    - Test dropdown switches the active DataFrame and updates frequency dropdown.
    - 2D slice and 3D spherical plotting with optional normalization.
    - Optional calibration offset CSV (columns: freq_ghz, offset_db).
    - Plotting options (title, gridlines, manual y-limits) similar to PatternWizard.
    - Toolbar, PNG/PDF export with descriptive default filenames.
    """

    # Canonical column names used internally
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
        """
        Build the window, set defaults, and assemble the UI.
        """
        super().__init__(parent)
        self.title("Data Analysis")
        self.geometry("1200x800")
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.after(10, self.focus_force)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Active state
        self.df = None                       # current test DataFrame
        self.offset_df = None                # calibration offsets (freq_ghz, offset_db)
        self.freq_list = []                  # string list for dropdown (e.g., ['2.400', '2.450'])
        self.last_plot_mode = None           # '2d' or '3d'

        # Parsed multi-test structures
        self.test_blocks = []                # list of dicts: {meta: {...}, df: pd.DataFrame}
        self.test_labels = []                # dropdown labels per block
        self.selected_test_label = ctk.StringVar(value="")

        # UI-bound vars
        self.create_control_vars()

        # Build UI chrome
        self.create_frames()
        self.create_status_bar()
        self.create_plot_area()
        self.create_controls()               # reorganized controls (not stacked)
        self.update_status_bar()

        # WM close
        self.protocol("WM_DELETE_WINDOW", self.handle_close)

    # ==================== UI VARIABLES & FRAMES ====================

    def create_control_vars(self):
        """
        Initialize Tk variables bound to controls and plot options.
        """
        self.freq_var = ctk.StringVar(value="")
        self.normalize_var = ctk.BooleanVar(value=False)

        # slice selection dialog bookkeeping
        self.slice_type_var = ctk.StringVar(value="phi")
        self.slice_value_var = ctk.StringVar(value="")

        # calibration
        self.cal_file_var = ctk.StringVar(value="No cal file loaded")

        # plot options (PatternWizard parity)
        self.plot_title_var = ctk.StringVar(value="Pattern")
        self.grid_var = ctk.BooleanVar(value=True)
        self.y_min_var = ctk.StringVar(value="")
        self.y_max_var = ctk.StringVar(value="")
        self._y_axis_limits = None  # (ymin, ymax) or None

    def create_frames(self):
        """
        Create the main layout frames:
        - status bar on top
        - content split: left controls / right plot
        """
        # top status
        self.status_frame = ctk.CTkFrame(self, corner_radius=12)
        self.status_frame.pack(padx=20, pady=(12, 0), fill="x")

        # content area
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.pack(padx=20, pady=16, fill=ctk.BOTH, expand=True)

        # Left: controls panel (fixed width)
        self.controls_frame = ctk.CTkFrame(self.content_frame, corner_radius=12)
        self.controls_frame.pack(side="left", fill="y", padx=(0, 12), pady=0)

        # Right: plot area (expands)
        self.plot_frame = ctk.CTkFrame(self.content_frame, corner_radius=12)
        self.plot_frame.pack(side="right", fill=ctk.BOTH, expand=True)

    def create_status_bar(self):
        """
        Build the persistent status summary bar.
        """
        self.status_text = ctk.StringVar(value="No cal file loaded • 0 tests")
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            textvariable=self.status_text,
            anchor="w",
            font=("Helvetica", 15, "bold"),
            padx=12,
            pady=10
        )
        self.status_label.pack(fill="x")

    def create_plot_area(self):
        """
        Create a Matplotlib Figure + canvas; toolbar is attached on show.
        """
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        # Only show toolbar when a plot is displayed
        self.toolbar.pack_forget()

    def create_controls(self):
        """
        Build a tidy, sectioned control panel instead of one tall stack.

        Layout
        ------
        [ File I/O ]          [ Plot Options ]
        [ Test/Freq ]         [ Actions      ]
        [ Export/Close ]
        """
        # Section: File I/O
        file_group = ctk.CTkFrame(self.controls_frame)
        file_group.pack(fill="x", padx=12, pady=(12, 8))
        ctk.CTkLabel(file_group, text="File I/O", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(4, 6))
        row = ctk.CTkFrame(file_group); row.pack(fill="x", pady=3)
        ctk.CTkButton(row, text="Load CSV…", command=self.load_csv).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(row, text="Load Last", command=self.load_last_csv).pack(side="left", expand=True, fill="x", padx=(4, 0))
        ctk.CTkButton(file_group, text="Load FSPL Offset…", command=lambda: self.load_csv(cal=True)).pack(fill="x", pady=3)

        # Section: Test / Frequency
        tf_group = ctk.CTkFrame(self.controls_frame)
        tf_group.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(tf_group, text="Test / Frequency", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(4, 6))

        self.test_selector = ctk.CTkOptionMenu(
            tf_group, values=[], variable=self.selected_test_label,
            command=lambda *_: (self.on_test_selected(), self.update_status_bar())
        )
        self.test_selector.pack(fill="x", pady=4)

        self.freq_dropdown = ctk.CTkOptionMenu(
            tf_group, variable=self.freq_var, values=[],
            command=lambda _: (self.on_freq_change(), self.update_status_bar())
        )
        self.freq_dropdown.pack(fill="x", pady=4)

        # normalize toggle right below
        self.chk_normalize = ctk.CTkCheckBox(
            tf_group, text="Normalize to 0 dB",
            variable=self.normalize_var,
            command=lambda: (self.refresh_current_plot(), self.update_status_bar())
        )
        self.chk_normalize.pack(anchor="w", pady=(6, 2))

        # Section: Plot Options (PatternWizard parity)
        opts_group = ctk.CTkFrame(self.controls_frame)
        opts_group.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(opts_group, text="Plot Options", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(4, 6))

        # Title
        tr = ctk.CTkFrame(opts_group); tr.pack(fill="x", pady=3)
        ctk.CTkLabel(tr, text="Title", width=80, anchor="w").pack(side="left")
        self.title_entry = ctk.CTkEntry(tr)
        self.title_entry.insert(0, self.plot_title_var.get())
        self.title_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # Gridlines
        self.grid_check = ctk.CTkCheckBox(opts_group, text="Show gridlines", variable=self.grid_var,
                                          command=self.apply_plot_options_now)
        self.grid_check.pack(anchor="w", pady=3)

        # Y-limits (2D only; applied when 2D is displayed)
        yl = ctk.CTkFrame(opts_group); yl.pack(fill="x", pady=3)
        ctk.CTkLabel(yl, text="Y-limits (min,max)", width=120, anchor="w").pack(side="left")
        self.y_min_entry = ctk.CTkEntry(yl, width=70); self.y_min_entry.pack(side="left", padx=(6, 4))
        self.y_max_entry = ctk.CTkEntry(yl, width=70); self.y_max_entry.pack(side="left")

        # Apply button
        ctk.CTkButton(opts_group, text="Apply Options", command=self.apply_plot_options_now).pack(fill="x", pady=(6, 0))

        # Section: Actions
        act_group = ctk.CTkFrame(self.controls_frame)
        act_group.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(act_group, text="Actions", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(4, 6))

        row2 = ctk.CTkFrame(act_group); row2.pack(fill="x", pady=3)
        ctk.CTkButton(row2, text="Plot 2D Slice", command=self.plot_2d_slice).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(row2, text="Plot 3D Spherical", command=self.plot_3d_spherical).pack(side="left", expand=True, fill="x", padx=(4, 0))

        ctk.CTkButton(act_group, text="Test Info", command=self.show_test_info).pack(fill="x", pady=3)

        # Section: Export / Close
        exp_group = ctk.CTkFrame(self.controls_frame)
        exp_group.pack(fill="x", padx=12, pady=(8, 12))
        ctk.CTkLabel(exp_group, text="Export / Close", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(4, 6))

        row3 = ctk.CTkFrame(exp_group); row3.pack(fill="x", pady=3)
        ctk.CTkButton(row3, text="Export PNG", command=lambda: self.export_plot("png")).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(row3, text="Export PDF", command=lambda: self.export_plot("pdf")).pack(side="left", expand=True, fill="x", padx=(4, 0))

        ctk.CTkButton(exp_group, text="Close", fg_color="#8b1c1c", hover_color="#6e1616",
                      command=self.handle_close).pack(fill="x", pady=(6, 0))

    # ==================== STATUS/TOAST HELPERS ====================

    def _get_selected_block_meta(self):
        """
        Return the metadata dict for the currently selected block label.
        """
        if not self.test_blocks or not self.test_labels:
            return {}
        label = self.selected_test_label.get()
        try:
            idx = int(label.split(".", 1)[0]) - 1
        except Exception:
            try:
                idx = self.test_labels.index(label)
            except ValueError:
                idx = 0
        idx = max(0, min(idx, len(self.test_blocks) - 1))
        return self.test_blocks[idx].get("meta", {})

    def update_status_bar(self):
        """
        Update the condensed status summary line.
        """
        cal_txt = self.cal_file_var.get() or "No cal file loaded"
        n_tests = len(self.test_blocks)
        sel = (self.selected_test_label.get() or "").strip() or "No test selected"
        f = (self.freq_var.get() or "").strip()
        f_txt = f"{f} GHz" if f else "—"
        norm_txt = "Normalize: ON" if self.normalize_var.get() else "Normalize: OFF"

        # Shorten cal text if needed
        if cal_txt.lower().startswith("cal file:"):
            cal_txt = cal_txt.split(":", 1)[1].strip() or "No cal file loaded"

        pol = ""
        try:
            meta = getattr(self, "current_meta", {}) or self._get_selected_block_meta()
            pol = meta.get("polarization", "")
        except Exception:
            pass
        pol_txt = f"Pol: {pol}" if pol else "Pol: —"

        parts = [
            f"Cal: {cal_txt}",
            f"Tests: {n_tests}",
            f"Selected: {sel}",
            pol_txt,
            f"Freq: {f_txt}",
            norm_txt,
        ]
        self.status_text.set("  •  ".join(parts))

    def flash_status(self, message: str, ms: int = 3000):
        """
        Temporarily show a message in the status bar, then restore the summary.

        Parameters
        ----------
        message : str
            Temporary message to display.
        ms : int
            Display duration (milliseconds).
        """
        try:
            self.status_text.set(message)
            self.after(ms, self.update_status_bar)
        except Exception:
            pass

    # ==================== DATA LOADING ====================

    def load_csv(self, cal=False):
        """
        Prompt for a CSV and load either calibration offsets or multi-/single-test data.

        Parameters
        ----------
        cal : bool
            If True, interpret the file as an offset file (freq_ghz, offset_db).
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
            # prefer multi-test parsing; fall back to single-test read
            if not self.parse_multi_test_csv(file_path):
                self._load_csv_from_path(file_path, cal=False)

    def load_last_csv(self):
        """
        Load the last test file path stored in ui.session.last_test_csv.
        """
        file_path = ui.session.last_test_csv
        if file_path and os.path.exists(file_path):
            if not self.parse_multi_test_csv(file_path):
                self._load_csv_from_path(file_path, cal=False)
        else:
            self.flash_status("No last test file found or path invalid.")

    def _load_csv_from_path(self, file_path, cal=False):
        """
        Load a non-block single CSV (either calibration or a single test).

        Parameters
        ----------
        file_path : str
            Path to the CSV.
        cal : bool
            If True, load as calibration offsets.
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
                self.update_status_bar()
                self.flash_status(f"Calibration loaded: {os.path.basename(file_path)}")
                return

            # Single test
            df = self.apply_common_column_renames(df)
            # If still no mag_db but 4+ columns, use the last column as mag_db
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
            self.update_status_bar()
            self.flash_status(f"Loaded: {os.path.basename(file_path)}")
        except Exception as e:
            self.flash_status(f"Error loading file: {e}")

    # ---------- Multi-test CSV parsing ----------

    def parse_multi_test_csv(self, filepath) -> bool:
        """
        Parse a CSV that may contain multiple tests, populating test_blocks and dropdown.

        Returns
        -------
        bool
            True if multi-test blocks were found and parsed; False otherwise.
        """
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
        except OSError as e:
            self.flash_status(f"Failed to read CSV: {e}")
            return False

        # Try block-style first; fall back to legacy
        blocks = self._split_blocks_blockstyle(lines)
        if not blocks:
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
                self.flash_status(f"Failed to read one block: {e}")
                continue

            df = self.apply_common_column_renames(df)

            # freq in Hz -> GHz if present
            if "freq_hz" in df.columns and "freq_ghz" not in df.columns:
                try:
                    df["freq_ghz"] = df["freq_hz"].astype(float) / 1e9
                except Exception:
                    pass

            # choose magnitude column
            if "mag_db" not in df.columns:
                for cand in ("s21_db", "s11_db", "magnitude_db", "Magnitude (dB)"):
                    if cand in df.columns:
                        df["mag_db"] = df[cand]
                        break
                if "mag_db" not in df.columns and len(df.columns) >= 4:
                    df.rename(columns={df.columns[-1]: "mag_db"}, inplace=True)

            # numeric casts (best-effort)
            cast_map = {}
            for col in ("phi_deg", "theta_deg", "freq_ghz", "mag_db"):
                if col in df.columns:
                    cast_map[col] = float
            try:
                df = df.astype(cast_map)
            except Exception:
                pass

            self.test_blocks.append({"meta": meta, "df": df})

        if not self.test_blocks:
            return False

        # labels
        self.test_labels = []
        for i, tb in enumerate(self.test_blocks):
            m = tb.get("meta", {})
            tname = m.get("type", "Unknown")
            tdate = m.get("date", "")
            pol = m.get("polarization", "")
            pol_txt = f"[{pol}]" if pol else ""
            label = f"{i + 1}. {tname} {pol_txt} {f'({tdate})' if tdate else ''}".strip()
            self.test_labels.append(label)

        self.test_selector.configure(values=self.test_labels)
        self.test_selector.set(self.test_labels[0])
        self.on_test_selected()
        self.update_status_bar()
        self.flash_status(f"Loaded {len(self.test_blocks)} test(s) from {os.path.basename(filepath)}")
        return True

    def _split_blocks_blockstyle(self, lines):
        """
        Split by block markers with optional CONFIG_JSON and META lines.

        Returns
        -------
        list[dict]
            Each dict has 'meta' and 'data' keys.
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
                # sniff header to extract last column label
                try:
                    header_line = None
                    for ln in data_lines:
                        if ln.strip() and not ln.lstrip().startswith("#"):
                            header_line = ln
                            break
                    if header_line and "," in header_line:
                        cols = [c.strip() for c in header_line.split(",")]
                        if cols:
                            meta.setdefault("y_label", cols[-1])
                except Exception:
                    pass
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
                try:
                    cfg = json.loads(s.split(":", 1)[1].strip())
                    name = cfg.get("name") or cfg.get("test_label") or "Unknown"
                    meta["type"] = name
                    meta["date"] = cfg.get("created_utc", "") or cfg.get("started_utc", "")
                    # propagate plot options for nicer defaults
                    if "plot_options" in cfg:
                        po = cfg["plot_options"]
                        if isinstance(po, dict):
                            for k, v in po.items():
                                meta.setdefault(k, v)
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

            data_lines.append(s)

        if data_lines:
            finalize()

        return blocks

    def _split_blocks_legacy(self, lines):
        """
        Split by legacy header style with '# Test Type:' and '# Date:' lines.

        Returns
        -------
        list[dict]
            Each dict has 'meta' and 'data' keys.
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
                data_lines.append(s)

        if data_lines:
            finalize()
        return blocks

    # ==================== COLUMN NORMALIZATION ====================

    def apply_common_column_renames(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rename any known column variants to canonical names expected by the app.

        Parameters
        ----------
        df : pd.DataFrame
            Source DataFrame.

        Returns
        -------
        pd.DataFrame
            DataFrame with harmonized column names.
        """
        df.columns = [col.strip() for col in df.columns]
        col_map = {}
        for orig_name, new_name in self.RENAME_MAP.items():
            for actual_col in df.columns:
                if actual_col.strip().lower() == orig_name.lower():
                    col_map[actual_col] = new_name
        df = df.rename(columns=col_map)

        # lowercase fallbacks
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
            self.update_status_bar()
            return
        freqs = sorted(pd.unique(self.df['freq_ghz'].astype(float)))
        self.freq_list = [f"{f:.3f}" for f in freqs]
        self.freq_dropdown.configure(values=self.freq_list)
        if self.freq_list:
            self.freq_var.set(self.freq_list[0])
        else:
            self.freq_var.set("")
        self.on_freq_change()
        self.update_status_bar()

    def on_freq_change(self, _=None):
        """
        React to a frequency change; refresh the last plot mode if any.
        """
        self.refresh_current_plot()

    def on_test_selected(self, *_):
        """
        Swap the active DataFrame to the chosen test block and refresh dropdown/plot.
        """
        if not self.test_blocks or not self.test_labels:
            return

        label = self.selected_test_label.get()
        idx = None
        try:
            idx = int(label.split(".", 1)[0]) - 1
        except Exception:
            pass
        if idx is None or not (0 <= idx < len(self.test_blocks)):
            try:
                idx = self.test_labels.index(label)
            except ValueError:
                idx = 0

        self.df = self.test_blocks[idx]['df']
        self.current_meta = self.test_blocks[idx].get("meta", {})

        # Adopt saved plot options if present (block-style)
        po_title = self.current_meta.get("title")
        if isinstance(po_title, str) and po_title.strip():
            self.plot_title_var.set(po_title.strip())
            self.title_entry.delete(0, "end")
            self.title_entry.insert(0, self.plot_title_var.get())
        grid = self.current_meta.get("grid")
        if isinstance(grid, bool):
            self.grid_var.set(grid)
            self.grid_check.select() if grid else self.grid_check.deselect()
        ylims = self.current_meta.get("y_limits")
        if isinstance(ylims, (list, tuple)) and len(ylims) == 2 and all(isinstance(v, (int, float)) for v in ylims):
            self._y_axis_limits = (float(ylims[0]), float(ylims[1]))
            self.y_min_var.set(f"{ylims[0]}")
            self.y_max_var.set(f"{ylims[1]}")
            self.y_min_entry.delete(0, "end"); self.y_min_entry.insert(0, f"{ylims[0]}")
            self.y_max_entry.delete(0, "end"); self.y_max_entry.insert(0, f"{ylims[1]}")
        else:
            self._y_axis_limits = None
            self.y_min_entry.delete(0, "end")
            self.y_max_entry.delete(0, "end")

        self.update_freq_options()
        self.refresh_current_plot()
        self.update_status_bar()

    # ==================== UTILITY ====================

    def get_freq_filtered_df(self):
        """
        Return a copy of the active DataFrame filtered to the selected frequency,
        applying calibration offset if available.

        Returns
        -------
        pd.DataFrame | None
        """
        if self.df is None or 'freq_ghz' not in self.df.columns:
            return None
        try:
            freq = float(self.freq_var.get())
            subset = self.df[np.isclose(self.df['freq_ghz'].astype(float), freq, rtol=0, atol=1e-6)].copy()

            # Apply correction offset (optional)
            if getattr(self, 'offset_df', None) is not None and \
               'freq_ghz' in self.offset_df.columns and 'offset_db' in self.offset_df.columns:
                offset = float(np.interp(freq, self.offset_df['freq_ghz'], self.offset_df['offset_db']))
            else:
                offset = 0.0

            if 'mag_db' in subset.columns:
                subset['mag_db_corrected'] = subset['mag_db'].astype(float) + offset
            return subset

        except Exception as e:
            self.flash_status(f"Frequency/offset error: {e}")
            return None

    def validate_columns(self, required):
        """
        Verify the active DataFrame contains required columns.

        Parameters
        ----------
        required : list[str]
            Column names to check.

        Returns
        -------
        bool
            True if all are present; False otherwise.
        """
        if self.df is None:
            self.flash_status("No data loaded.")
            return False
        missing = [col for col in required if col not in self.df.columns]
        if missing:
            self.flash_status(f"Missing columns: {missing}")
            return False
        return True

    def clear_plot_area(self):
        """
        Remove any existing toolbar/canvas packing from the plot frame.
        """
        for widget in self.plot_frame.winfo_children():
            widget.pack_forget()

    def show_plot(self):
        """
        Attach toolbar and canvas to the plot frame.
        """
        self.clear_plot_area()
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.update()
        self.toolbar.pack(side=ctk.TOP, fill=ctk.X, pady=(0, 10))
        self.canvas.get_tk_widget().pack(fill=ctk.BOTH, expand=True)

    def refresh_current_plot(self):
        """
        Refresh whichever plot mode was last used, if any.
        """
        if self.last_plot_mode == '2d':
            slice_df = self.get_freq_filtered_df()
            if slice_df is not None:
                self.plot_2d_slice_with_selection(slice_df)
        elif self.last_plot_mode == '3d':
            self.plot_3d_spherical()

    # ==================== PLOTTING ====================

    def apply_plot_options_now(self):
        """
        Read title/grid/ylim fields and apply immediately to the current figure.
        """
        # Title
        title = (self.title_entry.get().strip() if self.title_entry else "") or "Pattern"
        self.plot_title_var.set(title)

        # Gridlines
        grid_on = bool(self.grid_var.get())

        # Y-limits (2D only)
        ylims = None
        y_min_txt = self.y_min_entry.get().strip() if self.y_min_entry else ""
        y_max_txt = self.y_max_entry.get().strip() if self.y_max_entry else ""
        if y_min_txt and y_max_txt:
            try:
                y0 = float(y_min_txt); y1 = float(y_max_txt)
                if y0 < y1:
                    ylims = (y0, y1)
            except Exception:
                ylims = None
        self._y_axis_limits = ylims

        # Apply to current axes
        try:
            # 2D
            if hasattr(self, "ax") and self.ax.name == "rectilinear":
                self.ax.set_title(self.plot_title_var.get())
                self.ax.grid(grid_on)
                if self._y_axis_limits:
                    self.ax.set_ylim(*self._y_axis_limits)
                self.canvas.draw()
            # 3D
            if hasattr(self, "ax") and self.ax.name == "3d":
                self.ax.set_title(self.plot_title_var.get())
                # 3D grid toggle isn't standard; leave as title-only
                self.canvas.draw()
        except Exception:
            pass

    def _ylabel_from_meta(self) -> str:
        """
        Determine the Y label / colorbar label using current meta (fallback "Magnitude (dB)").
        """
        return (getattr(self, "current_meta", {}) or self._get_selected_block_meta()).get("y_label", "Magnitude (dB)")

    def plot_2d_slice(self):
        """
        Choose a slice (phi=const or theta=const) from the current test and plot a 2D cut.

        Behaviour
        ---------
        - If both phi and theta vary, prompts the user to choose which to hold constant.
        - If only one varies, uses that automatically.
        """
        if not self.validate_columns(['theta_deg', 'phi_deg', 'mag_db', 'freq_ghz']):
            return

        slice_df = self.get_freq_filtered_df()
        if slice_df is None or slice_df.empty:
            self.flash_status("No data at selected frequency.")
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
                self.flash_status(f"Slice selection error: {e}")

        ctk.CTkButton(dlg, text="Plot Slice", command=on_confirm).pack(pady=10)

    def plot_2d_slice_with_selection(self, slice_df):
        """
        Render a 2D slice for the selected frequency and slice definition.

        Parameters
        ----------
        slice_df : pd.DataFrame
            Pre-filtered DataFrame at the selected frequency.
        """
        try:
            slice_type = self.slice_type_var.get()
            slice_val = float(self.slice_value_var.get())
            filtered_df = slice_df[np.isclose(slice_df[f'{slice_type}_deg'].astype(float), slice_val, rtol=0, atol=1e-6)]
            if filtered_df.empty:
                self.flash_status(f"No data found for {slice_type} = {slice_val}")
                return

            mag_db = filtered_df.get('mag_db_corrected', filtered_df['mag_db']).astype(float)
            if self.normalize_var.get():
                mag_db = mag_db - float(np.max(mag_db))

            # reset axes
            self.figure.clf()
            self.ax = self.figure.add_subplot(111)

            if slice_type == 'phi':
                self.ax.plot(filtered_df['theta_deg'].astype(float), mag_db, label=f"\u03d5={slice_val:.2f}")
                self.ax.set_xlabel("Theta (\u00b0)")
            else:
                self.ax.plot(filtered_df['phi_deg'].astype(float), mag_db, label=f"\u03b8={slice_val:.2f}")
                self.ax.set_xlabel("Phi (\u00b0)")

            self.ax.set_ylabel(self._ylabel_from_meta())

            # apply plot options
            self.ax.set_title(self.plot_title_var.get() or f"2D Slice at {self.freq_var.get()} GHz")
            self.ax.grid(bool(self.grid_var.get()))
            if self._y_axis_limits:
                try:
                    self.ax.set_ylim(*self._y_axis_limits)
                except Exception:
                    pass

            self.ax.legend()
            self.canvas.draw()
            self.show_plot()

            self.last_plot_mode = '2d'
        except Exception as e:
            self.flash_status(f"2D slice error: {e}")

    def plot_3d_spherical(self):
        """
        Render a 3D scatter of the selected-frequency spherical sample set.
        """
        if not self.validate_columns(['theta_deg', 'phi_deg', 'mag_db', 'freq_ghz']):
            return

        slice_df = self.get_freq_filtered_df()
        if slice_df is None or slice_df.empty:
            self.flash_status("No data at selected frequency.")
            return

        try:
            theta = np.deg2rad(slice_df['theta_deg'].astype(float).values)
            phi = np.deg2rad(slice_df['phi_deg'].astype(float).values)

            mag_db = slice_df.get('mag_db_corrected', slice_df['mag_db']).astype(float).values
            if self.normalize_var.get():
                mag_db = mag_db - np.max(mag_db)

            # radial mapping (match PatternWizard)
            r = 10 ** (mag_db / 20.0)
            x = r * np.sin(phi) * np.cos(theta)
            y = r * np.sin(phi) * np.sin(theta)
            z = r * np.cos(phi)

            self.figure.clf()
            ax = self.figure.add_subplot(111, projection='3d')

            sc = ax.scatter(x, y, z, c=mag_db, cmap='viridis', marker='o')
            # options: title only (3D grid toggle is inconsistent across backends)
            ax.set_title(self.plot_title_var.get() or f"3D Pattern at {self.freq_var.get()} GHz")

            cbar = self.figure.colorbar(sc, ax=ax, shrink=0.6, pad=0.1)
            cbar.set_label(self._ylabel_from_meta())

            self.ax = ax
            self.last_plot_mode = '3d'
            self.canvas.draw()
            self.show_plot()
        except Exception as e:
            self.flash_status(f"3D plot error: {e}")

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
            self.cal_file_var.set(f"Cal file: {os.path.basename(file_path)}")
            self.update_status_bar()
            self.flash_status(f"Calibration loaded: {os.path.basename(file_path)}")
        except Exception as e:
            self.flash_status(f"Failed to load offset file: {e}")

    # ==================== INFO / EXPORT / CLOSE ====================

    def show_test_info(self):
        """
        Show a small dialog listing metadata for the selected test block.
        """
        meta = getattr(self, "current_meta", {}) or self._get_selected_block_meta()
        if not meta:
            self.flash_status("No test metadata available.")
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("Test Info")
        dlg.geometry("420x320")
        dlg.grab_set()
        txt = ctk.CTkTextbox(dlg, wrap="word")
        txt.pack(fill="both", expand=True, padx=12, pady=12)
        lines = []
        # Pretty-print a few common keys first
        for k in ("type", "date", "polarization", "y_label"):
            if k in meta:
                lines.append(f"{k}: {meta[k]}")
        # Then the rest
        for k, v in meta.items():
            if k not in ("type", "date", "polarization", "y_label"):
                lines.append(f"{k}: {v}")
        txt.insert("1.0", "\n".join(lines))
        txt.configure(state="disabled")
        ctk.CTkButton(dlg, text="Close", command=dlg.destroy).pack(pady=(0, 12))

    def _default_plot_basename(self) -> str:
        """
        Build a descriptive default filename from the current test label,
        plot mode, and frequency selection.

        Returns
        -------
        str
        """
        # Current test label (e.g., "1. Full Spherical (2025-08-08)")
        label = getattr(self, "selected_test_label", None)
        test_label = label.get() if label else "plot"

        # Frequency
        freq_txt = (self.freq_var.get() or "").strip().replace(" ", "")
        if freq_txt:
            freq_txt = f"{freq_txt}GHz"

        # Mode
        mode = self.last_plot_mode or "plot"

        # Safe filename
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
        if not hasattr(self, "figure") or self.figure is None:
            self.flash_status("No figure to export.")
            return

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

            if ext.lower() == "png":
                self.figure.savefig(path, dpi=300, bbox_inches="tight")
            else:
                self.figure.savefig(path, bbox_inches="tight")

            self.flash_status(f"Exported plot: {os.path.basename(path)}")
        except Exception as e:
            self.flash_status(f"Failed to export plot: {e}")

    def handle_close(self):
        """
        Destroy the window safely (best-effort).
        """
        try:
            self.destroy()
        except Exception:
            pass