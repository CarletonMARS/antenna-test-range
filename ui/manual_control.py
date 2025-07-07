from PIL import Image
import customtkinter as ctk
from interfaces.serial_interface import SerialController
import settings


class ManualControlWindow(ctk.CTkToplevel):
    """
    A manual control GUI for interacting with a serial-connected positioner.

    Features:
    - Allows precise Phi/Theta movement in various step sizes (±10, ±1, ±0.1, ±0.02)
    - Individual axis homing (Phi, Theta, A) and combined homing
    - Save and go to (0,0,0) origin functionality
    - Displays live position feedback in a textbox
    - Shows a branded banner image
    - Wraps a `SerialController` interface to send movement and query commands
    """
    def __init__(self, parent, serial_ctrl: SerialController):
        super().__init__(parent)
        self.ctrl = serial_ctrl
        self.connected = False
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.lift()
        self.after(10, lambda: self.focus_force())
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("POSITIONER MANUAL CONTROL")

        # BANNER IMAGE
        image_path = "images/COORDS.png"
        image = Image.open(image_path)
        self.ctk_image = ctk.CTkImage(light_image=image, size=(200, 200))
        self.label = ctk.CTkLabel(self, image=self.ctk_image, text="")
        self.label.grid(row=0, column=4, padx=10, pady=10)

        # Phi -10
        self.phiminus10_button = ctk.CTkButton(self, text="Phi -10", command=self.phiminus10)
        self.phiminus10_button.grid(row=2, column=0, pady=10, padx=10)

        # Phi -1
        self.phiminus1_button = ctk.CTkButton(self, text="Phi -1", command=self.phiminus1)
        self.phiminus1_button.grid(row=2, column=1, pady=10, padx=10)

        # Phi -0.1
        self.phiminus0p1_button = ctk.CTkButton(self, text="Phi -0.1", command=self.phiminus0p1)
        self.phiminus0p1_button.grid(row=2, column=2, pady=10, padx=10)

        # Phi -0.02
        self.phiminus0p02_button = ctk.CTkButton(self, text="Phi -0.02", command=self.phiminus0p02)
        self.phiminus0p02_button.grid(row=2, column=3, pady=10, padx=10)

        # Phi +0.02
        self.phiplus0p02_button = ctk.CTkButton(self, text="Phi +0.02", command=self.phiplus0p02)
        self.phiplus0p02_button.grid(row=2, column=5, pady=10, padx=10)

        # Phi +0.1
        self.phiplus0p1_button = ctk.CTkButton(self, text="Phi +0.1", command=self.phiplus0p1)
        self.phiplus0p1_button.grid(row=2, column=6, pady=10, padx=10)

        # Phi +1
        self.phiplus1_button = ctk.CTkButton(self, text="Phi +1", command=self.phiplus1)
        self.phiplus1_button.grid(row=2, column=7, pady=10, padx=10)

        # Phi +10
        self.phiplus10_button = ctk.CTkButton(self, text="Phi +10", command=self.phiplus10)
        self.phiplus10_button.grid(row=2, column=8, pady=10, padx=10)

        # Theta -10
        self.thetaminus10_button = ctk.CTkButton(self, text="Theta -10", command=self.thetaminus10)
        self.thetaminus10_button.grid(row=3, column=0, pady=10, padx=10)

        # Theta -1
        self.thetaminus1_button = ctk.CTkButton(self, text="Theta -1", command=self.thetaminus1)
        self.thetaminus1_button.grid(row=3, column=1, pady=10, padx=10)

        # Theta -0.1
        self.thetaminus0p1_button = ctk.CTkButton(self, text="Theta -0.1", command=self.thetaminus0p1)
        self.thetaminus0p1_button.grid(row=3, column=2, pady=10, padx=10)

        # Theta -0.02
        self.thetaminus0p02_button = ctk.CTkButton(self, text="Theta -0.02", command=self.thetaminus0p02)
        self.thetaminus0p02_button.grid(row=3, column=3, pady=10, padx=10)

        # Theta +0.02
        self.thetaplus0p02_button = ctk.CTkButton(self, text="Theta +0.02", command=self.thetaplus0p02)
        self.thetaplus0p02_button.grid(row=3, column=5, pady=10, padx=10)

        # Theta +0.1
        self.thetaplus0p1_button = ctk.CTkButton(self, text="Theta +0.1", command=self.thetaplus0p1)
        self.thetaplus0p1_button.grid(row=3, column=6, pady=10, padx=10)

        # Theta +1
        self.thetaplus1_button = ctk.CTkButton(self, text="Theta +1", command=self.thetaplus1)
        self.thetaplus1_button.grid(row=3, column=7, pady=10, padx=10)

        # Theta +10
        self.thetaplus10_button = ctk.CTkButton(self, text="Theta +10", command=self.thetaplus10)
        self.thetaplus10_button.grid(row=3, column=8, pady=10, padx=10)

        # Home Phi
        self.home_phi_button = ctk.CTkButton(self, text="Home Phi", command=self.home_phi)
        self.home_phi_button.grid(row=4, column=1, pady=10, padx=10)

        # Home Theta
        self.home_theta_button = ctk.CTkButton(self, text="Home Theta", command=self.home_theta)
        self.home_theta_button.grid(row=4, column=2, pady=10, padx=10)

        # Home A
        self.homea_button = ctk.CTkButton(self, text="Home A", command=self.homea)
        self.homea_button.grid(row=4, column=3, pady=10, padx=10)

        # Home All
        self.homeall_button = ctk.CTkButton(self, text="Home All", command=self.home)
        self.homeall_button.grid(row=4, column=4, pady=10, padx=10)

        # GOTO 0,0,0
        self.goto0_button = ctk.CTkButton(self, text="GOTO 0,0,0", command=self.goto0)
        self.goto0_button.grid(row=4, column=7, pady=1, padx=10)

        # SAVE 0,0,0
        self.save0_button = ctk.CTkButton(self, text="SAVE 0,0,0", command=self.save0)
        self.save0_button.grid(row=5, column=7, pady=1, padx=10)

        # GOTO Custom Entry Fields
        self.phi_entry = ctk.CTkEntry(self, placeholder_text="Phi (°)", width=130)
        self.phi_entry.grid(row=6, column=0, padx=5, pady=5)

        self.theta_entry = ctk.CTkEntry(self, placeholder_text="Theta (°)", width=130)
        self.theta_entry.grid(row=6, column=1, padx=10, pady=10)

        self.goto_custom_button = ctk.CTkButton(self, text="GOTO CUSTOM", command=self.goto_custom)
        self.goto_custom_button.grid(row=6, column=2, padx=10, pady=10)

        # Close
        self.close_button = ctk.CTkButton(self, text='CLOSE', command=self.handle_close)
        self.close_button.grid(row=6, column=4, padx=1, pady=1)

        # TEXTBOX
        self.textbox = ctk.CTkTextbox(self, height=100, width=600, wrap="word")
        self.textbox.grid(row=5, column=4, padx=10, pady=10)
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    def connect_to_controller(self):
        try:
            phi, theta, z, a, b, c = self.ctrl.query_position()
            phi_display = -phi
            self.update_textbox(f"Connected. Position at connection time is Phi{phi_display} Theta{theta} A{a}\n")
            self.connected = True
        except Exception as e:
            self.update_textbox(f"Failed to connect: {e}")

    def update_textbox(self, text):
        self.textbox.delete("1.0", "end")
        self.textbox.insert("end", text)

    # Phi movement (invert direction for user convention)
    def phiminus10(self):
        self.move_and_refresh(+10, 0)
    def phiminus1(self):
        self.move_and_refresh(+1, 0)
    def phiminus0p1(self):
        self.move_and_refresh(+0.1, 0)
    def phiminus0p02(self):
        self.move_and_refresh(+0.02, 0)
    def phiplus0p02(self):
        self.move_and_refresh(-0.02, 0)
    def phiplus0p1(self):
        self.move_and_refresh(-0.1, 0)
    def phiplus1(self):
        self.move_and_refresh(-1, 0)
    def phiplus10(self):
        self.move_and_refresh(-10, 0)

    # Theta movement
    def thetaminus10(self): self.move_and_refresh(0, -10)
    def thetaminus1(self): self.move_and_refresh(0, -1)
    def thetaminus0p1(self): self.move_and_refresh(0, -0.1)
    def thetaminus0p02(self): self.move_and_refresh(0, -0.02)
    def thetaplus0p02(self): self.move_and_refresh(0, 0.02)
    def thetaplus0p1(self): self.move_and_refresh(0, 0.1)
    def thetaplus1(self): self.move_and_refresh(0, 1)
    def thetaplus10(self): self.move_and_refresh(0, 10)

    def home_phi(self):
        self.ctrl.home_x()
        self.refresh(45)

    def home_theta(self):
        self.ctrl.home_y()
        self.refresh(45)

    def homea(self):
        self.ctrl.home_a()
        self.refresh(45)

    def home(self):
        self.ctrl.home_xya()
        self.refresh(45)

    def save0(self):
        self.ctrl.save0()
        self.refresh()

    def goto0(self):
        self.zero_and_refresh()

    def get_position(self):
        try:
            phi, theta, z, a, *_ = self.ctrl.query_position()
            phi_display = -phi
            self.update_textbox(f"Current Position: Phi: {phi_display} Theta: {theta} A{a}")
            return phi, theta, z, a

        except Exception as e:
            self.update_textbox(f"Error in getting position: {str(e)}")
            return None, None, None, None

    def refresh(self, timeout=10):
        try:
            self.ctrl.wait_for_idle(timeout)
        except RuntimeError as e:
            return self.update_textbox(f"Move timeout: {e}")
        phi, theta, z, a, *_ = self.ctrl.query_position()
        phi_display = -phi
        self.update_textbox(f"Current Position: Phi: {phi_display} Theta: {theta} Z{z} A{a}")

    def move_and_refresh(self, dphi, dtheta, dz=0, da=0):
        phi0, theta0, z0, a0, *_ = self.ctrl.query_position()
        target_phi = phi0 + dphi
        target_theta = theta0 + dtheta
        target_z = z0 + dz
        target_a = a0 + da
        self.ctrl.move_to(target_phi, target_theta, target_z, target_a)
        self.refresh()

    def goto_custom(self):
        """
        Moves to the user-specified Phi and Theta values from the input fields.
        """
        try:
            phi_target = float(self.phi_entry.get())
            theta_target = float(self.theta_entry.get())
            _, _, z, a, *_ = self.ctrl.query_position()
            self.ctrl.move_to(phi_target, theta_target, z, a)
            self.refresh()
        except ValueError:
            self.update_textbox("Invalid input. Please enter numeric values for Phi and Theta.")
        except Exception as e:
            self.update_textbox(f"Failed to move: {e}")

    def zero_and_refresh(self):
        self.ctrl.move_to(0, 0)
        self.refresh()

    def handle_close(self):
        try:
            self.destroy()
        except Exception:
            pass
