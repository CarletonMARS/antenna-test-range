from PIL import Image
import customtkinter as ctk
from interfaces.serial_interface import SerialController
import settings


class ManualControlWindow(ctk.CTkToplevel):
    """
    A manual control GUI for interacting with a serial-connected positioner.

    Features:
    - Allows precise X/Y movement in various step sizes (±10, ±1, ±0.1, ±0.02)
    - Individual axis homing (X, Y, A) and combined homing
    - Save and go to (0,0,0) origin functionality
    - Displays live position feedback in a textbox
    - Shows a branded banner image
    - Wraps a `SerialController` interface to send movement and query commands
    """
    def __init__(self, parent, serial_ctrl: SerialController):
        """
        Initializes the manual control window with positioner controls and layout.

        Args:
            parent: The parent tkinter window or root.
            serial_ctrl (SerialController): Controller interface to the stepper system.
        """
        self.connected = False
        super().__init__(parent)
        self.ctrl = serial_ctrl
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.lift()
        self.after(10, lambda: self.focus_force())
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("POSITIONER MANUAL CONTROL")

        # BANNER IMAGE
        image_path = "images/DUO5.png"
        image = Image.open(image_path)
        self.ctk_image = ctk.CTkImage(light_image=image, size=(200, 200))
        self.label = ctk.CTkLabel(self, image=self.ctk_image, text="")
        self.label.grid(row=0, column=4, padx=10, pady=10)
        # X -10
        self.xminus10_button = ctk.CTkButton(self, text="X -10", command=self.xminus10)
        self.xminus10_button.grid(row=2, column=0, pady=10, padx=10)

        # X -1
        self.xminus1_button = ctk.CTkButton(self, text="X -1", command=self.xminus1)
        self.xminus1_button.grid(row=2, column=1, pady=10, padx=10)

        # X -0.1
        self.xminus0p1_button = ctk.CTkButton(self, text="X -0.1", command=self.xminus0p1)
        self.xminus0p1_button.grid(row=2, column=2, pady=10, padx=10)

        # X -0.02
        self.xminus0p02_button = ctk.CTkButton(self, text="X -0.02", command=self.xminus0p02)
        self.xminus0p02_button.grid(row=2, column=3, pady=10, padx=10)

        # X 10
        self.xplus10_button = ctk.CTkButton(self, text="X +10", command=self.xplus10)
        self.xplus10_button.grid(row=2, column=8, pady=10, padx=10)

        # X 1
        self.xplus1_button = ctk.CTkButton(self, text="X +1", command=self.xplus1)
        self.xplus1_button.grid(row=2, column=7, pady=10, padx=10)

        # X 0.1
        self.xplus0p1_button = ctk.CTkButton(self, text="X +0.1", command=self.xplus0p1)
        self.xplus0p1_button.grid(row=2, column=6, pady=10, padx=10)

        # X 0.02
        self.xplus0p02_button = ctk.CTkButton(self, text="X +0.02", command=self.xplus0p02)
        self.xplus0p02_button.grid(row=2, column=5, pady=10, padx=10)

        ##################################################################################################

        # Y -10
        self.yminus10_button = ctk.CTkButton(self, text="Y -10", command=self.yminus10)
        self.yminus10_button.grid(row=3, column=0, pady=10, padx=10)

        # Y -1
        self.yminus1_button = ctk.CTkButton(self, text="Y -1", command=self.yminus1)
        self.yminus1_button.grid(row=3, column=1, pady=10, padx=10)

        # Y -0.1
        self.yminus0p1_button = ctk.CTkButton(self, text="Y -0.1", command=self.yminus0p1)
        self.yminus0p1_button.grid(row=3, column=2, pady=10, padx=10)

        # Y -0.02
        self.yminus0p02_button = ctk.CTkButton(self, text="Y -0.02", command=self.yminus0p02)
        self.yminus0p02_button.grid(row=3, column=3, pady=10, padx=10)

        # Y 10
        self.yplus10_button = ctk.CTkButton(self, text="Y +10", command=self.yplus10)
        self.yplus10_button.grid(row=3, column=8, pady=10, padx=10)

        # Y 1
        self.yplus1_button = ctk.CTkButton(self, text="Y +1", command=self.yplus1)
        self.yplus1_button.grid(row=3, column=7, pady=10, padx=10)

        # Y 0.1
        self.yplus0p1_button = ctk.CTkButton(self, text="Y +0.1", command=self.yplus0p1)
        self.yplus0p1_button.grid(row=3, column=6, pady=10, padx=10)

        # Y 0.02
        self.yplus0p02_button = ctk.CTkButton(self, text="Y +0.02", command=self.yplus0p02)
        self.yplus0p02_button.grid(row=3, column=5, pady=10, padx=10)

        # Home X
        self.HomeX_button = ctk.CTkButton(self, text="HomeX", command=self.homex)
        self.HomeX_button.grid(row=4, column=1, pady=10, padx=10)

        # Home Y
        self.HomeY_button = ctk.CTkButton(self, text="HomeY", command=self.homey)
        self.HomeY_button.grid(row=4, column=2, pady=10, padx=10)

        # Home A
        self.HomeA_button = ctk.CTkButton(self, text="HomeA", command=self.homea)
        self.HomeA_button.grid(row=4, column=3, pady=10, padx=10)

        # Home All
        self.HomeALL_button = ctk.CTkButton(self, text="Home All", command=self.home)
        self.HomeALL_button.grid(row=4, column=4, pady=10, padx=10)

        # Goto 000
        self.goto0_button = ctk.CTkButton(self, text="GOTO 0,0,0", command=self.goto0)
        self.goto0_button.grid(row=4, column=7, pady=1, padx=10)

        # Save 000
        self.goto0_button = ctk.CTkButton(self, text="SAVE 0,0,0", command=self.save0)
        self.goto0_button.grid(row=5, column=7, pady=1, padx=10)

        # Close
        self.close_button = ctk.CTkButton(self, text='CLOSE', command=self.handle_close)
        self.close_button.grid(row=6, column=4, padx=1, pady=1)

        # TEXTBOX
        self.textbox = ctk.CTkTextbox(self, height=100, width=600, wrap="word")
        self.textbox.grid(row=5, column=4, padx=10, pady=10)
        self.update_idletasks()  # Calculate layout
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    def connect_to_controller(self):
        """
        Attempts to query and display the current position from the controller.

        Sets `self.connected` to True if successful.
        """
        try:
            x, y, z, a, b, c = self.ctrl.query_position()
            self.update_textbox(f"Connected. Position at connection time is X{x} Y{y} A{a}\n")
            self.connected = True
        except Exception as e:
            self.update_textbox(f"Failed to connect: {e}")

    def update_textbox(self, text):
        """
        Updates the textbox area with provided status text.

        Args:
            text (str): Text to display.
        """
        self.textbox.delete("1.0", "end")  # Clear previous text
        self.textbox.insert("end", text)  # Insert new text

    def xminus10(self):
        self.move_and_refresh(-10, 0)

    def xminus1(self):
        self.move_and_refresh(-1, 0)

    def xminus0p1(self):
        self.move_and_refresh(-0.1, 0)

    def xminus0p02(self):
        self.move_and_refresh(-0.02, 0)

    def xplus0p02(self):
        self.move_and_refresh(0.02, 0)

    def xplus0p1(self):
        self.move_and_refresh(0.1, 0)

    def xplus1(self):
        self.move_and_refresh(1, 0)

    def xplus10(self):
        self.move_and_refresh(10, 0)

    def yminus10(self):
        self.move_and_refresh(0, -10)

    def yminus1(self):
        self.move_and_refresh(0, -1)

    def yminus0p1(self):
        self.move_and_refresh(0, -0.1)

    def yminus0p02(self):
        self.move_and_refresh(0, -0.02)

    def yplus0p02(self):
        self.move_and_refresh(0, 0.02)

    def yplus0p1(self):
        self.move_and_refresh(0, 0.1)

    def yplus1(self):
        self.move_and_refresh(0, 1)

    def yplus10(self):
        self.move_and_refresh(0, 10)

    def homex(self):
        """Homes the X-axis and refreshes the position display."""
        self.ctrl.home_x()
        self.refresh(45)

    def homey(self):
        """Homes the Y-axis and refreshes the position display."""
        self.ctrl.home_y()
        self.refresh(45)

    def homea(self):
        """Homes the A-axis and refreshes the position display."""
        self.ctrl.home_a()
        self.refresh(45)

    def home(self):
        """Homes all (X, Y, A) axes and refreshes the position display."""
        self.ctrl.home_xya()
        self.refresh(45)

    def save0(self):
        """Saves the current position as the (0,0,0) origin."""
        self.ctrl.save0()
        self.refresh()

    def goto0(self):
        """Moves to the saved (0,0,0) origin and refreshes the display."""
        self.zero_and_refresh()

    def get_position(self):
        """
        Queries the current position from the controller.

        Returns:
            tuple: (x, y, z, a) or (None, None, None, None) if query fails.
        """
        try:
            x, y, z, a, *_ = self.ctrl.query_position()
            self.update_textbox(f"Current Position: X{x} Y{y} A{a}")
            return x, y, z, a
        except Exception as e:
            self.update_textbox(f"Error in getting position: {str(e)}")
            return None, None, None, None

    def refresh(self, timeout=10):
        """
        Waits for the controller to become idle, then updates position display.

        Args:
            timeout (int): Time in seconds to wait before timing out, default 10s.
        """
        try:
            self.ctrl.wait_for_idle(timeout)
        except RuntimeError as e:
            return self.update_textbox(f"Move timeout: {e}")
        x1, y1, z1, a1, *_ = self.ctrl.query_position()
        self.update_textbox(f"Current Position: X{x1} Y{y1} Z{z1} A{a1}")

    def move_and_refresh(self, dx, dy, dz=0, da=0):
        """
        Moves by a relative offset and refreshes the display.

        Args:
            dx (float): Delta X.
            dy (float): Delta Y.
            dz (float): Delta Z (default 0).
            da (float): Delta A (default 0).
        """
        x0, y0, z0, a0, *_ = self.ctrl.query_position()
        target_x = x0 + dx
        target_y = y0 + dy
        target_z = z0 + dz
        target_a = a0 + da
        self.ctrl.move_to(target_x, target_y, target_z, target_a)
        self.refresh()

    def zero_and_refresh(self):
        """Moves to the origin (0,0) and refreshes the position display."""
        self.ctrl.move_to(0, 0)
        self.refresh()

    def handle_close(self):
        try:
            self.destroy()
        except Exception:
            pass