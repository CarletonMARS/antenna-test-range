from PIL import Image
import os
import customtkinter as ctk
from interfaces.serial_interface import SerialController
import settings


class ManualControlWindow(ctk.CTkToplevel):
    """
    Manual GUI for serial-connected positioner:
    - Phi/Theta step control
    - Axis homing
    - Save/load 0,0,0
    - Position feedback
    - Branded banner
    """

    def __init__(self, parent, serial_ctrl: SerialController):
        super().__init__(parent)
        self.ctrl = serial_ctrl
        self.connected = False

        self._setup_window()
        self._add_banner()
        self._add_phi_controls()
        self._add_theta_controls()
        self._add_home_controls()
        self._add_zero_controls()
        self._add_custom_goto()
        self._add_textbox()

    # ---------------------- INIT HELPERS ----------------------

    def _setup_window(self):
        self.title("POSITIONER MANUAL CONTROL")
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.lift()
        self.after(10, lambda: self.focus_force())
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

    def _add_banner(self):
        image_path = os.path.join("images", "COORDS.png")
        image = Image.open(image_path)
        self.ctk_image = ctk.CTkImage(light_image=image, size=(200, 200))
        self.label = ctk.CTkLabel(self, image=self.ctk_image, text="")
        self.label.grid(row=0, column=4, padx=10, pady=10)

    def _add_phi_controls(self):
        labels = ["-10", "-1", "-0.1", "-0.02", "+0.02", "+0.1", "+1", "+10"]
        commands = [self.phiminus10, self.phiminus1, self.phiminus0p1, self.phiminus0p02,
                    self.phiplus0p02, self.phiplus0p1, self.phiplus1, self.phiplus10]
        cols = [0, 1, 2, 3, 5, 6, 7, 8]
        for label, cmd, col in zip(labels, commands, cols):
            ctk.CTkButton(self, text=f"Phi {label}", command=cmd).grid(row=2, column=col, padx=10, pady=10)

    def _add_theta_controls(self):
        labels = ["-10", "-1", "-0.1", "-0.02", "+0.02", "+0.1", "+1", "+10"]
        commands = [self.thetaminus10, self.thetaminus1, self.thetaminus0p1, self.thetaminus0p02,
                    self.thetaplus0p02, self.thetaplus0p1, self.thetaplus1, self.thetaplus10]
        cols = [0, 1, 2, 3, 5, 6, 7, 8]
        for label, cmd, col in zip(labels, commands, cols):
            ctk.CTkButton(self, text=f"Theta {label}", command=cmd).grid(row=3, column=col, padx=10, pady=10)

    def _add_home_controls(self):
        buttons = [
            ("Home Phi", self.home_phi, 1),
            ("Home Theta", self.home_theta, 2),
            ("Home A", self.homea, 3),
            ("Home All", self.home, 4)
        ]
        for label, cmd, col in buttons:
            ctk.CTkButton(self, text=label, command=cmd).grid(row=4, column=col, padx=10, pady=10)

    def _add_zero_controls(self):
        ctk.CTkButton(self, text="SAVE 0,0,0", command=self.save0).grid(row=5, column=7, padx=10, pady=5)
        ctk.CTkButton(self, text="GOTO 0,0,0", command=self.goto0).grid(row=4, column=7, padx=10, pady=5)

    def _add_custom_goto(self):
        self.phi_entry = ctk.CTkEntry(self, placeholder_text="Phi (°)", width=130)
        self.phi_entry.grid(row=6, column=0, padx=5, pady=5)
        self.theta_entry = ctk.CTkEntry(self, placeholder_text="Theta (°)", width=130)
        self.theta_entry.grid(row=6, column=1, padx=5, pady=5)
        ctk.CTkButton(self, text="GOTO CUSTOM", command=self.goto_custom).grid(row=6, column=2, padx=10, pady=5)
        ctk.CTkButton(self, text='CLOSE', command=self.handle_close).grid(row=6, column=4, padx=10, pady=5)

    def _add_textbox(self):
        self.textbox = ctk.CTkTextbox(self, height=100, width=600, wrap="word")
        self.textbox.grid(row=5, column=4, padx=10, pady=10)
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    # ---------------------- PHI MOVEMENT ----------------------

    def phiminus10(self): self.move_and_refresh(+10, 0)
    def phiminus1(self): self.move_and_refresh(+1, 0)
    def phiminus0p1(self): self.move_and_refresh(+0.1, 0)
    def phiminus0p02(self): self.move_and_refresh(+0.02, 0)
    def phiplus0p02(self): self.move_and_refresh(-0.02, 0)
    def phiplus0p1(self): self.move_and_refresh(-0.1, 0)
    def phiplus1(self): self.move_and_refresh(-1, 0)
    def phiplus10(self): self.move_and_refresh(-10, 0)

    # ---------------------- THETA MOVEMENT ----------------------

    def thetaminus10(self): self.move_and_refresh(0, -10)
    def thetaminus1(self): self.move_and_refresh(0, -1)
    def thetaminus0p1(self): self.move_and_refresh(0, -0.1)
    def thetaminus0p02(self): self.move_and_refresh(0, -0.02)
    def thetaplus0p02(self): self.move_and_refresh(0, 0.02)
    def thetaplus0p1(self): self.move_and_refresh(0, 0.1)
    def thetaplus1(self): self.move_and_refresh(0, 1)
    def thetaplus10(self): self.move_and_refresh(0, 10)

    # ---------------------- POSITION AND CONTROL ----------------------

    def home_phi(self): self.ctrl.home_x(); self.refresh(45)
    def home_theta(self): self.ctrl.home_y(); self.refresh(45)
    def homea(self): self.ctrl.home_a(); self.refresh(45)
    def home(self): self.ctrl.home_xya(); self.refresh(45)
    def save0(self): self.ctrl.save0(); self.refresh()
    def goto0(self): self.ctrl.move_to(0, 0); self.refresh()

    def goto_custom(self):
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

    def refresh(self, timeout=10):
        try:
            self.ctrl.wait_for_idle(timeout)
        except RuntimeError as e:
            return self.update_textbox(f"Move timeout: {e}")
        phi, theta, z, a, *_ = self.ctrl.query_position()
        self.update_textbox(f"Current Position: Phi: {-phi} Theta: {theta} Z{z} A{a}")

    def move_and_refresh(self, dphi, dtheta, dz=0, da=0):
        phi0, theta0, z0, a0, *_ = self.ctrl.query_position()
        self.ctrl.move_to(phi0 + dphi, theta0 + dtheta, z0 + dz, a0 + da)
        self.refresh()

    def update_textbox(self, text):
        self.textbox.delete("1.0", "end")
        self.textbox.insert("end", text)

    def handle_close(self):
        try:
            self.destroy()
        except Exception:
            pass
