import customtkinter as ctk
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import ui.session
import os


class DataAnalysisWindow(ctk.CTkToplevel):
    """
    GUI window for viewing and analyzing antenna pattern data.
    Supports CSV loading, calibration correction, 2D and 3D plotting.
    """

    RENAME_MAP = {
        'Phi (deg)': 'phi_deg',
        'Theta (deg)': 'theta_deg',
        'Frequency (GHz)': 'freq_ghz',
        'Magnitude (dB)': 'mag_db'
    }

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Data Analysis")
        self.geometry("1200x800")
        self.attributes("-topmost", True)
        self.lift()
        self.after(10, lambda: self.focus_force())

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.df = None
        self.offset_df = None
        self.freq_list = []
        self.last_plot_mode = None

        self.create_widgets()

    # ==================== UI SETUP ====================

    def create_widgets(self):
        self.create_control_vars()
        # Global label above everything
        self.label_cal_file = ctk.CTkLabel(self, textvariable=self.cal_file_var, anchor="w")
        self.label_cal_file.pack(padx=20, pady=(10, 0), fill="x")
        self.create_frames()
        self.create_plot_area()
        self.create_buttons()

    def create_frames(self):
        self.plot_frame = ctk.CTkFrame(self)
        self.plot_frame.pack(padx=20, pady=20, fill=ctk.BOTH, expand=True)
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(pady=10)

    def create_plot_area(self):
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.pack_forget()

    def create_control_vars(self):
        self.freq_var = ctk.StringVar(value="")
        self.normalize_var = ctk.BooleanVar(value=False)
        self.slice_type_var = ctk.StringVar(value="phi")
        self.slice_value_var = ctk.StringVar(value="")
        self.cal_file_var = ctk.StringVar(value="No cal file loaded")

    def create_buttons(self):
        self.chk_normalize = ctk.CTkCheckBox(
            self.button_frame, text="Normalize to 0 dB",
            variable=self.normalize_var,
            command=self.refresh_current_plot
        )
        self.chk_normalize.grid(row=0, column=0, columnspan=2, padx=100, pady=5, sticky="w")

        self.freq_dropdown = ctk.CTkOptionMenu(
            self.button_frame, variable=self.freq_var, values=[], command=self.on_freq_change
        )
        self.freq_dropdown.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        buttons = [
            ("Load CSV", self.load_csv),
            ("Load Last Test", self.load_last_csv),
            ("Load FSPL Offset", lambda: self.load_csv(cal=True)),
            ("Plot 2D Slice", self.plot_2d_slice),
            ("Plot 3D Spherical", self.plot_3d_spherical),
            ("Close", self.handle_close)
        ]
        for i, (text, cmd) in enumerate(buttons):
            self._add_button(self.button_frame, i + 1, text, cmd)

    def _add_button(self, frame, row, text, command):
        ctk.CTkButton(frame, text=text, command=command).grid(
            row=row, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )

    # ==================== DATA LOADING ====================

    def load_csv(self, cal=False):
        file_path = filedialog.askopenfilename(
            initialdir=os.path.join(os.getcwd(), 'csv'),
            filetypes=[("CSV Files", "*.csv")]
        )
        if file_path:
            self._load_csv_from_path(file_path, cal)

    def load_last_csv(self):
        file_path = ui.session.last_test_csv
        if file_path and os.path.exists(file_path):
            self._load_csv_from_path(file_path, cal=False)
        else:
            print("No last test file found or path invalid.")

    def _load_csv_from_path(self, file_path, cal=False):
        try:
            df = pd.read_csv(file_path, header=0)
            if cal:
                df.rename(columns={
                    'Frequency (GHz)': 'freq_ghz',
                    'Correction (dB)': 'offset_db',
                    'Offset (dB)': 'offset_dB'
                }, inplace=True, errors="ignore")
                df = df.astype({'freq_ghz': float, 'offset_db': float})
                self.offset_df = df
                self.cal_file_var.set(f"Cal file: {os.path.basename(file_path)}")
                print("Loaded calibration data:", file_path)
            else:
                df = self.apply_common_column_renames(df)
                df = df.astype({
                    'phi_deg': float,
                    'theta_deg': float,
                    'freq_ghz': float,
                    'mag_db': float
                })
                self.df = df
                self.update_freq_options()
                print(f"Loaded: {file_path}")
        except Exception as e:
            print("Error loading file:", e)

    def apply_common_column_renames(self, df):
        df.rename(columns=self.RENAME_MAP, inplace=True)
        return df

    def update_freq_options(self):
        if self.df is None or 'freq_ghz' not in self.df.columns:
            return
        freqs = sorted(self.df['freq_ghz'].unique())
        self.freq_list = [f"{f:.2f}" for f in freqs]
        self.freq_dropdown.configure(values=self.freq_list)
        self.freq_var.set(self.freq_list[0])
        self.on_freq_change()

    def on_freq_change(self, _=None):
        pass

    # ==================== UTILITY ====================

    def get_freq_filtered_df(self):
        if self.df is None or 'freq_ghz' not in self.df.columns:
            return None
        try:
            freq = float(self.freq_var.get())
            subset = self.df[self.df['freq_ghz'] == freq].copy()

            # === Apply correction offset ===
            if hasattr(self, 'offset_df') and self.offset_df is not None:
                offset = float(np.interp(freq, self.offset_df['freq_ghz'], self.offset_df['offset_db']))
            else:
                offset = 0.0

            subset['mag_db_corrected'] = subset['mag_db'] + offset
            return subset

        except Exception as e:
            print("Invalid frequency selection or correction error:", e)
            return None

    def get_boresight_based_offset(self, freq_ghz):
        """
        Compute calibration offset for a given frequency,
        relative to the measurement at boresight (phi=90, theta=0).
        """
        if self.offset_df is None or self.df is None:
            return 0.0
        try:
            # Interpolated calibration gain from offset csv
            cal_interp = float(np.interp(freq_ghz, self.offset_df['freq_ghz'], self.offset_df['offset_db']))

            # Boresight measurement in test data
            boresight = self.df[
                (np.isclose(self.df['freq_ghz'], freq_ghz)) &
                (np.isclose(self.df['phi_deg'], 90.0)) &
                (np.isclose(self.df['theta_deg'], 0.0))
                ]

            if boresight.empty:
                print(f"Boresight missing at {freq_ghz:.2f} GHz. Assuming 0 dB reference.")
                return cal_interp  # assume measured = 0 dB

            measured_gain = boresight['mag_db'].values[0]
            return cal_interp - measured_gain
        except Exception as e:
            print("Error computing boresight-based offset:", e)
            return 0.0

    def validate_columns(self, required):
        if self.df is None:
            print("No data loaded.")
            return False
        missing = [col for col in required if col not in self.df.columns]
        if missing:
            print(f"Missing columns: {missing}")
            return False
        return True

    def clear_plot_area(self):
        for widget in self.plot_frame.winfo_children():
            widget.pack_forget()

    def show_plot(self):
        self.clear_plot_area()
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.update()
        self.toolbar.pack(side=ctk.TOP, fill=ctk.X, pady=(0, 10))
        self.canvas.get_tk_widget().pack(fill=ctk.BOTH, expand=True)

    def refresh_current_plot(self):
        if self.last_plot_mode == '2d':
            slice_df = self.get_freq_filtered_df()
            if slice_df is not None:
                self.plot_2d_slice_with_selection(slice_df)
        elif self.last_plot_mode == '3d':
            self.plot_3d_spherical()

    def handle_close(self):
        try:
            self.destroy()
        except Exception:
            pass

    # ==================== PLOTTING ====================

    def plot_2d_slice(self):
        if not self.validate_columns(['theta_deg', 'phi_deg', 'mag_db', 'freq_ghz']):
            return

        slice_df = self.get_freq_filtered_df()
        if slice_df is None or slice_df.empty:
            print("No data at selected frequency.")
            return

        unique_phi = sorted(slice_df['phi_deg'].unique())
        unique_theta = sorted(slice_df['theta_deg'].unique())

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
        try:
            slice_type = self.slice_type_var.get()
            slice_val = float(self.slice_value_var.get())
            filtered_df = slice_df[np.isclose(slice_df[slice_type + '_deg'], slice_val)]
            if filtered_df.empty:
                print(f"No data found for {slice_type} = {slice_val}")
                return

            mag_db = filtered_df.get('mag_db_corrected', filtered_df['mag_db'])
            if self.normalize_var.get():
                mag_db = mag_db - np.max(mag_db)

            self.figure.clf()
            self.ax = self.figure.add_subplot(111)

            if slice_type == 'phi':
                self.ax.plot(filtered_df['theta_deg'], mag_db, label=f"\u03d5={slice_val:.2f}", color="cyan")
                self.ax.set_xlabel("Theta (\u00b0)")
            else:
                self.ax.plot(filtered_df['phi_deg'], mag_db, label=f"\u03b8={slice_val:.2f}", color="magenta")
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
        if not self.validate_columns(['theta_deg', 'phi_deg', 'mag_db', 'freq_ghz']):
            return

        slice_df = self.get_freq_filtered_df()
        if slice_df is None or slice_df.empty:
            print("No data at selected frequency.")
            return

        try:
            theta = np.deg2rad(slice_df['theta_deg'].values)
            phi = np.deg2rad(slice_df['phi_deg'].values)

            mag_db = slice_df.get('mag_db_corrected', slice_df['mag_db']).values
            if self.normalize_var.get():
                mag_db -= np.max(mag_db)
            r = 10 ** (mag_db / 20)

            x = r * np.sin(theta) * np.cos(phi)
            y = r * np.sin(theta) * np.sin(phi)
            z = r * np.cos(theta)

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

    def load_offset_file(self):
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
