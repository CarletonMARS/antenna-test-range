import customtkinter as ctk
from tkinter import filedialog
import pandas as pd
import numpy as np
import os


class CalibrationToolWindow(ctk.CTkToplevel):
    """
    A tool window to generate a frequency offset calibration file (.csv)
    from a boresight CSV and a .tbl calibration file.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Calibration Offset Tool")
        self.geometry("500x300")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.cal_df = None
        self.boresight_df = None

        self.create_widgets()

    def create_widgets(self):
        self.label_status = ctk.CTkLabel(self, text="Load calibration and boresight files")
        self.label_status.pack(pady=10)

        self.btn_load_cal = ctk.CTkButton(self, text="Load Calibration (.tbl)", command=self.load_cal_file)
        self.btn_load_cal.pack(pady=10, fill="x", padx=20)

        self.btn_load_boresight = ctk.CTkButton(self, text="Load Boresight CSV", command=self.load_boresight_file)
        self.btn_load_boresight.pack(pady=10, fill="x", padx=20)

        self.btn_generate_offset = ctk.CTkButton(
            self,
            text="Generate Offset File",
            command=self.generate_offset_file,
            state="disabled"
        )
        self.btn_generate_offset.pack(pady=10, fill="x", padx=20)

        self.btn_close = ctk.CTkButton(self, text="Close", command=self.destroy)
        self.btn_close.pack(pady=20)

    def load_cal_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Calibration Files", "*.tbl")])
        if not file_path:
            return
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()[1:]
            data = [line.strip().split(",") for line in lines if line.strip()]
            freqs = [float(row[0]) for row in data]
            corrections = [float(row[1]) for row in data]
            self.cal_df = pd.DataFrame({'freq_ghz': freqs, 'corr_db': corrections})
            self.label_status.configure(text=f"Loaded cal: {os.path.basename(file_path)}")
        except Exception as e:
            self.label_status.configure(text=f"Failed to load cal: {e}")

        self.update_generate_button_state()

    def load_boresight_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not file_path:
            return

        try:
            df = pd.read_csv(file_path)
            df.rename(columns={
                'Phi (deg)': 'phi_deg',
                'Theta (deg)': 'theta_deg',
                'Frequency (GHz)': 'freq_ghz',
                'Magnitude (dB)': 'mag_db'
            }, inplace=True, errors="ignore")
            df = df.astype({'phi_deg': float, 'theta_deg': float, 'freq_ghz': float, 'mag_db': float})
            self.boresight_df = df
            self.label_status.configure(text=f"Loaded boresight: {os.path.basename(file_path)}")
        except Exception as e:
            self.label_status.configure(text=f"Failed to load boresight: {e}")

        self.update_generate_button_state()

    def update_generate_button_state(self):
        """Enable generate button only if both calibration and boresight data are loaded."""
        if self.cal_df is not None and self.boresight_df is not None:
            self.btn_generate_offset.configure(state="normal")
        else:
            self.btn_generate_offset.configure(state="disabled")

    def generate_offset_file(self):
        if self.cal_df is None or self.boresight_df is None:
            self.label_status.configure(text="Load both calibration and boresight files first.")
            return

        try:
            freqs = sorted(self.boresight_df['freq_ghz'].unique())
            offsets = []

            for f in freqs:
                boresight = self.boresight_df[
                    (np.isclose(self.boresight_df['phi_deg'], 90.0)) &
                    (np.isclose(self.boresight_df['theta_deg'], 0.0)) &
                    (np.isclose(self.boresight_df['freq_ghz'], f))
                ]
                if boresight.empty:
                    print(f"Missing boresight at {f} GHz")
                    continue
                g_measured = boresight['mag_db'].values[0]
                g_ref = float(np.interp(f, self.cal_df['freq_ghz'], self.cal_df['corr_db']))
                offset = g_ref - g_measured
                offsets.append((f, offset))

            if not offsets:
                self.label_status.configure(text="No offsets generated: missing boresight data.")
                return

            df_out = pd.DataFrame(offsets, columns=['freq_ghz', 'offset_db'])
            out_path = filedialog.asksaveasfilename(defaultextension=".csv", title="Save Offset File")
            if out_path:
                df_out.to_csv(out_path, index=False)
                self.label_status.configure(text=f"Offset saved to: {os.path.basename(out_path)}")

        except Exception as e:
            self.label_status.configure(text=f"Failed to generate offset: {e}")
