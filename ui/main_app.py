import sys
import os
from typing import Optional

import customtkinter as ctk
from PIL import Image

import settings
from ui.manual_control import ManualControlWindow
from ui.pattern_wizard import PatternWizard
from ui.vna_panel import VNAFrontPanel
from ui.data_analyzer import DataAnalysisWindow
from interfaces.vna_interface import VNAController
from interfaces.serial_interface import SerialController
from ui.calibration_tool import CalibrationToolWindow


class MainApp(ctk.CTk):
    """
    Main GUI window for the Antenna Test Range Controller.

    Provides launch points for:
    - Positioner connection & manual control
    - VNA connection & front panel
    - Pattern Wizard (requires both VNA and Positioner)
    - Data Analyzer and Calibration Tool
    """

    def __init__(self):
        """
        Initialize the main window, theme, layout, and default state.
        """
        super().__init__()
        self.vna_ctrl: Optional[VNAController] = None
        self.serial_ctrl: Optional[SerialController] = None

        self._setup_theme()
        self._initialize_layout()
        self._create_widgets()

        # Close behavior
        self.protocol("WM_DELETE_WINDOW", self.handle_close)

    # ---------------------- SETUP METHODS ----------------------

    def _setup_theme(self):
        """
        Apply appearance theme, window title, sizing, and resizing policy.
        """
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("ANTENNA TEST RANGE CONTROLLER —— MARS")
        self.geometry("1000x700")
        self.resizable(True, True)

    def _initialize_layout(self):
        """
        Create the main container frame and basic grid policy.
        """
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(expand=True, anchor="center")
        # Give the two columns equal space so buttons line up nicely.
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)

    def _create_widgets(self):
        """
        Build all top-level UI sections in order.
        """
        self._add_logo()
        self._add_connection_buttons()
        self._add_control_buttons()
        self._add_test_buttons()
        self._add_status_and_exit()
        self._refresh_launch_states()

    # ---------------------- UI COMPONENTS ----------------------

    def _add_logo(self):
        """
        Add a centered banner/logo image (falls back to text if missing).
        """
        image_path = os.path.join("images", "Carleton_Logo.png")
        try:
            image = Image.open(image_path)
            self.ctk_image = ctk.CTkImage(light_image=image, size=(300, 200))
            self.banner = ctk.CTkLabel(self.main_frame, image=self.ctk_image, text="")
        except Exception as e:
            self.banner = ctk.CTkLabel(self.main_frame, text=f"[Logo not found: {e}]")
        self.banner.grid(row=0, column=0, columnspan=2, pady=10)

    def _add_connection_buttons(self):
        """
        Create VNA and Positioner connection buttons.
        """
        self.btn_connect_serial = ctk.CTkButton(
            self.main_frame, text="Connect Positioner", command=self.connect_serial
        )
        self.btn_connect_serial.grid(row=1, column=0, padx=20, pady=5, sticky="ew")

        self.btn_connect_vna = ctk.CTkButton(
            self.main_frame, text="Connect VNA", command=self.vna_connect
        )
        self.btn_connect_vna.grid(row=1, column=1, padx=20, pady=5, sticky="ew")

    def _add_control_buttons(self):
        """
        Create launch buttons for manual positioner control and VNA front panel.
        Disabled until corresponding instruments are connected.
        """
        self.btn_manual_control = ctk.CTkButton(
            self.main_frame,
            text="MANUAL POSITIONER CONTROL",
            command=self.open_manual_control,
            state="disabled",
        )
        self.btn_manual_control.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.btn_vna_control = ctk.CTkButton(
            self.main_frame,
            text="VNA SOFT PANEL",
            command=self.open_vna_panel,
            state="disabled",
        )
        self.btn_vna_control.grid(row=2, column=1, padx=20, pady=5, sticky="ew")

    def _add_test_buttons(self):
        """
        Create buttons for test runner, calibration tool, and data analyzer.
        Pattern Wizard is enabled only when both VNA and positioner are connected.
        """
        self.btn_pattern_wizard = ctk.CTkButton(
            self.main_frame,
            text="Run Test",
            command=self.open_pattern_wizard,
            state="disabled",
        )
        self.btn_pattern_wizard.grid(row=3, column=0, columnspan=2, padx=20, pady=10, sticky="ew")

        self.btn_calibration_tool = ctk.CTkButton(
            self.main_frame, text="Calibration Tool", command=self.open_calibration_menu
        )
        self.btn_calibration_tool.grid(row=4, column=0, columnspan=2, padx=20, pady=10, sticky="ew")

        self.btn_data_analyzer = ctk.CTkButton(
            self.main_frame, text="Data Analyzer", command=self.open_data_analyzer
        )
        self.btn_data_analyzer.grid(row=5, column=0, columnspan=2, padx=20, pady=10, sticky="ew")

    def _add_status_and_exit(self):
        """
        Add connection status label and a Close button.
        """
        self.status = ctk.CTkLabel(self.main_frame, text="Not Connected")
        self.status.grid(row=6, column=0, columnspan=2, pady=10)

        self.btn_close = ctk.CTkButton(self.main_frame, text="CLOSE", command=self.handle_close)
        self.btn_close.grid(row=7, column=0, columnspan=2, pady=15, sticky="ew")

    # ---------------------- WINDOW OPENERS ----------------------

    def open_vna_panel(self):
        """
        Open the VNA soft front panel window (requires VNA connected).
        """
        if not self.vna_ctrl:
            self._set_status("VNA not connected.")
            return
        VNAFrontPanel(self, self.vna_ctrl)

    def open_manual_control(self):
        """
        Open the manual positioner control window (requires positioner connected).
        """
        if not self.serial_ctrl:
            self._set_status("Positioner not connected.")
            return
        ManualControlWindow(self, self.serial_ctrl)

    def open_pattern_wizard(self):
        """
        Open the Pattern Wizard (requires both VNA and positioner).
        """
        if not (self.vna_ctrl and self.serial_ctrl):
            self._set_status("Connect both VNA and Positioner to run tests.")
            return
        PatternWizard(self, self.vna_ctrl, self.serial_ctrl)

    def open_data_analyzer(self):
        """
        Open the data analysis window.
        """
        DataAnalysisWindow(self)

    def open_calibration_menu(self):
        """
        Open the calibration offset tool.
        """
        CalibrationToolWindow(self)

    # ---------------------- CONNECTION METHODS ----------------------

    def vna_connect(self):
        """
        Connect to the VNA using the configured GPIB address.
        Enables the VNA front panel on success.
        """
        try:
            self.vna_ctrl = VNAController(settings.GPIB_ADDRESS)
            idn = self.vna_ctrl.connect()
            self._set_status(f"VNA Connected: {idn}")
            self.btn_vna_control.configure(state="normal")
            self.btn_connect_vna.configure(text="VNA Connected", state="disabled")
            self._refresh_launch_states()
        except Exception as e:
            self._set_status(f"VNA failed: {e}")
            self.vna_ctrl = None
            self.btn_vna_control.configure(state="disabled")
            self.btn_connect_vna.configure(text="Connect VNA", state="normal")

    def connect_serial(self):
        """
        Connect to the positioner (serial), perform a basic home to 0,0,
        and enable manual control on success.
        """
        try:
            self.serial_ctrl = SerialController(settings.COM_PORT, settings.BAUD_RATE)
            # Optional: establish a known state
            self.serial_ctrl.home_xya()
            self.serial_ctrl.wait_for_idle(30)
            self.serial_ctrl.move_to(0, 0)
            self.serial_ctrl.wait_for_idle(30)

            self.btn_connect_serial.configure(text="Positioner Connected", state="disabled")
            self._set_status("Positioner Connected")
            self.btn_manual_control.configure(state="normal")
            self._refresh_launch_states()
        except Exception as e:
            self._set_status(f"Connection Failed: {e}")
            self.serial_ctrl = None
            self.btn_manual_control.configure(state="disabled")
            self.btn_connect_serial.configure(text="Connect Positioner", state="normal")

    # ---------------------- EXIT ----------------------

    def handle_close(self):
        """
        Close instrument connections (if any) and exit the application.
        """
        try:
            if self.vna_ctrl:
                self.vna_ctrl.handle_close()
        except Exception:
            pass
        try:
            if self.serial_ctrl:
                self.serial_ctrl.handle_close()
        except Exception:
            pass
        try:
            self.destroy()
        finally:
            sys.exit(0)

    # ---------------------- HELPERS ----------------------

    def _set_status(self, text: str):
        """
        Update the status label with a short message.

        Parameters
        ----------
        text : str
            The message to display.
        """
        try:
            self.status.configure(text=text)
        except Exception:
            pass

    def _refresh_launch_states(self):
        """
        Enable/disable launch buttons based on current connection state.
        """
        # VNA panel depends on vna_ctrl
        self.btn_vna_control.configure(state="normal" if self.vna_ctrl else "disabled")
        # Manual control depends on serial
        self.btn_manual_control.configure(state="normal" if self.serial_ctrl else "disabled")
        # Pattern Wizard needs both
        both = "normal" if (self.vna_ctrl and self.serial_ctrl) else "disabled"
        self.btn_pattern_wizard.configure(state=both)