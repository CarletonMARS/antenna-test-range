import customtkinter as ctk
from tkinter import filedialog, Toplevel, Label
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import ui.session
import os

class DataAnalysisWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Data Analysis")
        self.geometry("1200x800")
        self.attributes("-topmost", True)
        self.lift()
        self.after(10, lambda: self.focus_force())

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # === Frames ===
        self.plot_frame = ctk.CTkFrame(self)
        self.plot_frame.pack(padx=20, pady=20, fill=ctk.BOTH, expand=True)

        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(pady=10)

        # === Matplotlib Figure Setup ===
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.pack_forget()

        # === Control Variables ===
        self.df = None
        self.freq_list = []
        self.freq_var = ctk.StringVar(value="")
        self.normalize_var = ctk.BooleanVar(value=False)
        self.last_plot_mode = None  # can be '2d' or '3d'

        # Variables for slice selection, set dynamically when needed
        self.slice_type_var = ctk.StringVar(value="phi")
        self.slice_value_var = ctk.StringVar(value="")

        # === GUI Controls ===
        self.chk_normalize = ctk.CTkCheckBox(
            self.button_frame,
            text="Normalize to 0 dB",
            variable=self.normalize_var,
            command=self.refresh_current_plot
        )
        self.chk_normalize.pack(pady=5)

        self.freq_dropdown = ctk.CTkOptionMenu(
            self.button_frame,
            variable=self.freq_var,
            values=[],
            command=self.on_freq_change
        )
        self.freq_dropdown.pack(pady=5, fill='x')

        self.btn_load_csv = ctk.CTkButton(self.button_frame, text="Load CSV", command=self.load_csv)
        self.btn_load_last = ctk.CTkButton(self.button_frame, text="Load Last Test", command=self.load_last_csv)
        self.btn_plot_slice = ctk.CTkButton(self.button_frame, text="Plot 2D Slice", command=self.plot_2d_slice)
        self.btn_plot_3d = ctk.CTkButton(self.button_frame, text="Plot 3D Spherical", command=self.plot_3d_spherical)

        self.btn_load_csv.grid(row=0, column=0, padx=20, pady=5)


    def load_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file_path:
            self.df = pd.read_csv(file_path, header=0, dtype=str)
            self.df.rename(columns={
                'Phi (deg)': 'phi_deg',
                'Theta (deg)': 'theta_deg',
                'Frequency (GHz)': 'freq_ghz',
                'Magnitude (dB)': 'mag_db'
            }, inplace=True)
            try:
                self.df = self.df.astype({
                    'phi_deg': float,
                    'theta_deg': float,
                    'freq_ghz': float,
                    'mag_db': float
                })
                self.update_freq_options()
                print(f"Loaded: {file_path}")
            except Exception as e:
                print("Error parsing numeric values:", e)

    def load_last_csv(self):
        try:
            file_path = ui.session.last_test_csv
            if not file_path or not os.path.exists(file_path):
                print("No last test file found or path invalid.")
                return

            self.df = pd.read_csv(file_path, header=0, dtype=str)
            self.df.rename(columns={
                'Phi (deg)': 'phi_deg',
                'Theta (deg)': 'theta_deg',
                'Frequency (GHz)': 'freq_ghz',
                'Magnitude (dB)': 'mag_db'
            }, inplace=True)

            self.df = self.df.astype({
                'phi_deg': float,
                'theta_deg': float,
                'freq_ghz': float,
                'mag_db': float
            })

            self.update_freq_options()
            print(f"Loaded last test: {file_path}")
        except Exception as e:
            print("Failed to load last test file:", e)
    def update_freq_options(self):
        if self.df is None or 'freq_ghz' not in self.df.columns:
            return
        freqs = sorted(self.df['freq_ghz'].unique())
        self.freq_list = [f"{f:.2f}" for f in freqs]
        self.freq_dropdown.configure(values=self.freq_list)
        self.freq_var.set(self.freq_list[0])
        self.on_freq_change()

    def on_freq_change(self, _=None):
        # Placeholder for frequency-dependent updates
        pass

    def get_freq_filtered_df(self):
        if self.df is None or 'freq_ghz' not in self.df.columns:
            return None
        try:
            freq = float(self.freq_var.get())
            return self.df[self.df['freq_ghz'] == freq].copy()
        except Exception as e:
            print("Invalid frequency selection:", e)
            return None

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

    def plot_2d_slice(self):
        if not self.validate_columns(['theta_deg', 'phi_deg', 'mag_db', 'freq_ghz']):
            return

        slice_df = self.get_freq_filtered_df()
        if slice_df is None or slice_df.empty:
            print("No data at selected frequency.")
            return

        unique_phi = sorted(slice_df['phi_deg'].unique())
        unique_theta = sorted(slice_df['theta_deg'].unique())
        # Show dialog if both phi and theta vary
        if len(unique_phi) > 1 and len(unique_theta) > 1:
            self.ask_slice_selection_dialog(unique_phi, unique_theta)
            return
        else:
            # Automatically pick slice type and value
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
        dlg.grab_set()  # Modal

        # LOCAL vars to avoid destroyed-widget errors
        local_slice_type_var = ctk.StringVar(value="phi")
        local_slice_value_var = ctk.StringVar(value=f"{unique_phi[0]:.2f}")

        # Slice type label
        label_slice_by = ctk.CTkLabel(dlg, text="Slice by:", font=("Arial", 12, "bold"))
        label_slice_by.pack(pady=(10, 5))

        # Radio buttons for slice direction
        ctk.CTkRadioButton(dlg, text="Phi (φ)", variable=local_slice_type_var, value="phi").pack(anchor="w", padx=20)
        ctk.CTkRadioButton(dlg, text="Theta (θ)", variable=local_slice_type_var, value="theta").pack(anchor="w",
                                                                                                     padx=20)

        # Entry label and textbox
        label_value = ctk.CTkLabel(dlg, text="Slice value (degrees):", font=("Arial", 12, "bold"))
        label_value.pack(pady=(10, 2))
        entry_value = ctk.CTkEntry(dlg, textvariable=local_slice_value_var)
        entry_value.pack(pady=5, fill='x', padx=20)
        dlg.update_idletasks()  # Calculate layout
        dlg.geometry(f"{dlg.winfo_reqwidth()+100}x{dlg.winfo_reqheight()+100}")

        def on_slice_type_change(*args):
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

        ctk.CTkButton(dlg, text="Plot Slice", command=on_confirm).pack(pady=15)

    def plot_2d_slice_with_selection(self, slice_df):
        try:
            slice_type = self.slice_type_var.get()
            slice_val = float(self.slice_value_var.get())

            filtered_df = slice_df[np.isclose(slice_df[slice_type + '_deg'], slice_val)]

            if filtered_df.empty:
                print(f"No data found for {slice_type} = {slice_val}")
                return

            plot_mag = filtered_df['mag_db']
            if self.normalize_var.get():
                plot_mag = plot_mag - np.max(plot_mag)

            self.figure.clf()
            self.ax = self.figure.add_subplot(111)

            if slice_type == 'phi':
                self.ax.plot(filtered_df['theta_deg'], plot_mag, label=f"φ={slice_val:.2f}°", color="cyan")
                self.ax.set_xlabel("Theta (°)")
            else:
                self.ax.plot(filtered_df['phi_deg'], plot_mag, label=f"θ={slice_val:.2f}°", color="magenta")
                self.ax.set_xlabel("Phi (°)")

            self.ax.set_ylabel("Magnitude (dB)")
            self.ax.set_title(f"2D Slice at {self.freq_var.get()} GHz")
            self.ax.grid(True)
            self.ax.legend()
            self.canvas.draw()
            self.show_plot()

            self.last_plot_mode = '2d'

            self.update_idletasks()  # Calculate layout
            self.geometry(f"{self.winfo_reqwidth()+100}x{self.winfo_reqheight()+100}")
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

            mag_db = slice_df['mag_db'].values
            if self.normalize_var.get():
                mag_db -= np.max(mag_db)
            r = 10 ** (mag_db / 20)

            x = r * np.sin(theta) * np.cos(phi)
            y = r * np.sin(theta) * np.sin(phi)
            z = r * np.cos(theta)

            self.figure.clf()
            ax = self.figure.add_subplot(111, projection='3d')

            sc = ax.scatter(x, y, z, c=mag_db, cmap='viridis', marker='o')

            ax.set_title(f"3D Scatter Pattern at {self.freq_var.get()} GHz")
            cbar = self.figure.colorbar(sc, ax=ax, shrink=0.6, pad=0.1)
            cbar.set_label("Magnitude (dB)")

            self.last_plot_mode = '3d'

            self.canvas.draw()
            self.show_plot()
        except Exception as e:
            print("Error in 3D spherical:", e)

    def refresh_current_plot(self):
        if self.last_plot_mode == '2d':
            slice_df = self.get_freq_filtered_df()
            if slice_df is not None:
                self.plot_2d_slice_with_selection(slice_df)
        elif self.last_plot_mode == '3d':
            self.plot_3d_spherical()
