import sys
import os

import customtkinter as ctk
from PIL import Image

import settings
from ui.manual_control import ManualControlWindow
from ui.pattern_wizard import PatternWizard
from ui.vna_panel import VNAFrontPanel
from ui.data_analyzer import DataAnalysisWindow
from interfaces.vna_interface import VNAController
from interfaces.serial_interface import SerialController


class MainApp(ctk.CTk):
    """
    Main GUI window for the Antenna Test Range Controller.
    Provides access to serial/VNA control, pattern wizard, and data analyzer.
    """

    def __init__(self):
        super().__init__()
        self._setup_theme()
        self._initialize_layout()
        self._create_widgets()

        self.vna_ctrl = None
        self.serial_ctrl = None

    # ---------------------- SETUP METHODS ----------------------

    def _setup_theme(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("ANTENNA TEST RANGE CONTROLLER ---- MARS")
        self.geometry("1000x700")
        self.resizable(True, True)

    def _initialize_layout(self):
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(expand=True, anchor="center")

    def _create_widgets(self):
        self._add_logo()
        self._add_connection_buttons()
        self._add_control_buttons()
        self._add_test_buttons()
        self._add_status_and_exit()

    # ---------------------- UI COMPONENTS ----------------------

    def _add_logo(self):
        image_path = os.path.join("images", "Carleton_Logo.png")
        image = Image.open(image_path)
        self.ctk_image = ctk.CTkImage(light_image=image, size=(300, 200))
        self.banner = ctk.CTkLabel(self.main_frame, image=self.ctk_image, text="")
        self.banner.grid(row=0, column=0, columnspan=2, pady=10)

    def _add_connection_buttons(self):
        self.btn_connect_serial = ctk.CTkButton(
            self.main_frame, text="Connect Positioner", command=self.connect_serial
        )
        self.btn_connect_serial.grid(row=1, column=0, padx=20, pady=5)

        self.btn_connect_vna = ctk.CTkButton(
            self.main_frame, text="Connect VNA", command=self.vna_connect
        )
        self.btn_connect_vna.grid(row=1, column=1, padx=20, pady=5)

    def _add_control_buttons(self):
        self.btn_manual_control = ctk.CTkButton(
            self.main_frame, text="MANUAL POSITIONER CONTROL",
            command=self.open_manual_control, state="disabled"
        )
        self.btn_manual_control.grid(row=2, column=0, padx=20, pady=5)

        self.btn_vna_control = ctk.CTkButton(
            self.main_frame, text="VNA SOFT PANEL",
            command=self.open_vna_panel, state="disabled"
        )
        self.btn_vna_control.grid(row=2, column=1, padx=20, pady=5)

    def _add_test_buttons(self):
        self.btn_pattern_wizard = ctk.CTkButton(
            self.main_frame, text="Run Test",
            command=self.open_pattern_wizard, state="disabled"
        )
        self.btn_pattern_wizard.grid(row=3, column=0, columnspan=2, padx=20, pady=10)

        self.btn_data_analyzer = ctk.CTkButton(
            self.main_frame, text="Data Analyzer",
            command=self.open_data_analyzer
        )
        self.btn_data_analyzer.grid(row=4, column=0, columnspan=2, padx=20, pady=10)

    def _add_status_and_exit(self):
        self.status = ctk.CTkLabel(self.main_frame, text="Not Connected")
        self.status.grid(row=5, column=0, columnspan=2, pady=10)

        self.btn_close = ctk.CTkButton(
            self.main_frame, text="CLOSE", command=self.handle_close
        )
        self.btn_close.grid(row=6, column=0, columnspan=2, pady=15)

    # ---------------------- WINDOW OPENERS ----------------------

    def open_vna_panel(self):
        VNAFrontPanel(self, self.vna_ctrl)

    def open_manual_control(self):
        ManualControlWindow(self, self.serial_ctrl)

    def open_pattern_wizard(self):
        PatternWizard(self, self.vna_ctrl, self.serial_ctrl)

    def open_data_analyzer(self):
        DataAnalysisWindow(self)

    # ---------------------- CONNECTION METHODS ----------------------

    def vna_connect(self):
        try:
            self.vna_ctrl = VNAController(settings.GPIB_ADDRESS)
            idn = self.vna_ctrl.connect()
            self.status.configure(text=f"VNA Connected: {idn}")
            self.btn_vna_control.configure(state="normal")
            self.btn_connect_vna.configure(text="VNA Connected", state="disabled")
            if self.serial_ctrl:
                self.btn_pattern_wizard.configure(state="normal")
        except Exception as e:
            self.status.configure(text=f"VNA failed: {e}")

    def connect_serial(self):
        try:
            self.serial_ctrl = SerialController(settings.COM_PORT, settings.BAUD_RATE)
            self.serial_ctrl.home_xya()
            self.serial_ctrl.wait_for_idle(30)
            self.serial_ctrl.move_to(0, 0)
            self.serial_ctrl.wait_for_idle(30)
            self.btn_connect_serial.configure(text="Positioner Connected", state="disabled")
            self.status.configure(text="Positioner Connected")
            self.btn_manual_control.configure(state="normal")
            if self.vna_ctrl:
                self.btn_pattern_wizard.configure(state="normal")
        except Exception as e:
            self.status.configure(text=f"Connection Failed: {e}")

    # ---------------------- EXIT ----------------------

    def handle_close(self):
        if self.vna_ctrl:
            self.vna_ctrl.handle_close()
        if self.serial_ctrl:
            self.serial_ctrl.handle_close()
        self.destroy()
        sys.exit(0)
