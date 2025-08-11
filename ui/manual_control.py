from typing import Optional

from PIL import Image
import os
import customtkinter as ctk

from interfaces.serial_interface import SerialController
from interfaces.arduino_interface import ArduinoRotationStage, ArduinoStageConfig  # <- corrected import
import settings


class ManualControlWindow(ctk.CTkToplevel):
    """
    Manual control window for the serial-connected positioner and an Arduino rotation stage.

    Features
    -------
    - Phi/Theta jog buttons (coarse → fine)
    - Axis homing (phi, theta, A, or all)
    - Save/Goto 0,0,0
    - Custom GOTO for (phi, theta)
    - Live position feedback
    - Banner image
    - Optional Arduino-based rotation stage controls
    """

    def __init__(self, parent, serial_ctrl: SerialController,
                 rot_stage: Optional[ArduinoRotationStage] = None):
        """
        Initialize the manual control window and build the UI.

        Parameters
        ----------
        parent : tk.Misc
            Parent window.
        serial_ctrl : SerialController
            GRBL-like controller for phi/theta/z/a axes.
        rot_stage : Optional[ArduinoRotationStage]
            Optional Arduino rotation stage instance. If None, a default one is created.
        """
        super().__init__(parent)
        self.ctrl = serial_ctrl
        # Keep your default port; adjust as needed in your environment.
        self.rot: Optional[ArduinoRotationStage] = rot_stage or ArduinoRotationStage(
            ArduinoStageConfig(port=getattr(settings, "ARDUINO_PORT", "COM7"))
        )

        self.connected = False

        self._setup_window()
        self._add_banner()
        self._add_rotary_controls()   # Arduino rotation stage controls
        self._add_phi_controls()
        self._add_theta_controls()
        self._add_home_controls()
        self._add_zero_controls()
        self._add_custom_goto()
        self._add_textbox()

    # ---------------------- INIT HELPERS ----------------------

    def _setup_window(self):
        """
        Configure the toplevel window aesthetics and focus behavior.
        """
        self.title("POSITIONER MANUAL CONTROL")
        self.resizable(True, True)
        # Grid baseline so widgets stretch nicely
        for col in range(9):
            self.columnconfigure(col, weight=1)
        for row in range(7):
            self.rowconfigure(row, weight=0)
        self.rowconfigure(6, weight=1)

        self.lift()
        self.after(10, self.focus_force)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

    def _add_banner(self):
        """
        Add the banner image centered near the top row.
        """
        image_path = os.path.join("images", "COORDS.png")
        try:
            image = Image.open(image_path)
            self.ctk_image = ctk.CTkImage(light_image=image, size=(200, 200))
            lbl = ctk.CTkLabel(self, image=self.ctk_image, text="")
            lbl.grid(row=0, column=4, padx=10, pady=10)
        except Exception as e:
            # If the image is missing, show a small text label instead.
            ctk.CTkLabel(self, text=f"[Banner missing: {e}]").grid(row=0, column=4, padx=10, pady=10)

    def _add_rotary_controls(self):
        """
        Add Arduino rotation stage controls (relative jog, absolute GOTO, save zero).
        """
        self.rot_frame = ctk.CTkFrame(self)
        self.rot_frame.grid(row=1, column=0, columnspan=9, padx=10, pady=(5, 0), sticky="w")

        ctk.CTkLabel(
            self.rot_frame, text="Rotation Stage (Arduino)", font=("Helvetica", 14, "bold")
        ).grid(row=0, column=0, columnspan=8, sticky="w", padx=6, pady=(6, 2))

        btn_specs = [
            ("Rot -10°", -10),
            ("Rot -1°",  -1),
            ("Rot -0.1°", -0.1),
            ("Rot +0.1°", +0.1),
            ("Rot +1°",   +1),
            ("Rot +10°",  +10),
        ]
        for i, (txt, deg) in enumerate(btn_specs):
            ctk.CTkButton(
                self.rot_frame, text=txt, command=lambda d=deg: self.rot_move_rel(d)
            ).grid(row=1, column=i, padx=6, pady=6)

        # Absolute GOTO and save zero
        self.rot_goto_entry = ctk.CTkEntry(self.rot_frame, placeholder_text="Rot GOTO (°)", width=120)
        self.rot_goto_entry.grid(row=1, column=len(btn_specs), padx=6, pady=6)

        ctk.CTkButton(self.rot_frame, text="Rot GOTO", command=self.rot_goto
                      ).grid(row=1, column=len(btn_specs) + 1, padx=6, pady=6)

        ctk.CTkButton(self.rot_frame, text="Rot SAVE 0", command=self.rot_save0
                      ).grid(row=1, column=len(btn_specs) + 2, padx=6, pady=6)

    def _add_phi_controls(self):
        """
        Add phi jog controls (note: sign inverted to match applied coordinate system).
        """
        labels = ["-10", "-1", "-0.1", "-0.02", "+0.02", "+0.1", "+1", "+10"]
        commands = [self.phiminus10, self.phiminus1, self.phiminus0p1, self.phiminus0p02,
                    self.phiplus0p02, self.phiplus0p1, self.phiplus1, self.phiplus10]
        cols = [0, 1, 2, 3, 5, 6, 7, 8]
        for label, cmd, col in zip(labels, commands, cols):
            ctk.CTkButton(self, text=f"Phi {label}", command=cmd).grid(row=2, column=col, padx=10, pady=10)

    def _add_theta_controls(self):
        """
        Add theta jog controls (symmetric step sizes to phi).
        """
        labels = ["-10", "-1", "-0.1", "-0.02", "+0.02", "+0.1", "+1", "+10"]
        commands = [self.thetaminus10, self.thetaminus1, self.thetaminus0p1, self.thetaminus0p02,
                    self.thetaplus0p02, self.thetaplus0p1, self.thetaplus1, self.thetaplus10]
        cols = [0, 1, 2, 3, 5, 6, 7, 8]
        for label, cmd, col in zip(labels, commands, cols):
            ctk.CTkButton(self, text=f"Theta {label}", command=cmd).grid(row=3, column=col, padx=10, pady=10)

    def _add_home_controls(self):
        """
        Add homing buttons for individual axes and All.
        """
        buttons = [
            ("Home Phi", self.home_phi, 1),
            ("Home Theta", self.home_theta, 2),
            ("Home A", self.homea, 3),
            ("Home All", self.home, 4),
        ]
        for label, cmd, col in buttons:
            ctk.CTkButton(self, text=label, command=cmd).grid(row=4, column=col, padx=10, pady=10)

    def _add_zero_controls(self):
        """
        Add Save/Goto 0,0,0 commands.
        """
        ctk.CTkButton(self, text="SAVE 0,0,0", command=self.save0).grid(row=5, column=7, padx=10, pady=5)
        ctk.CTkButton(self, text="GOTO 0,0,0", command=self.goto0).grid(row=4, column=7, padx=10, pady=5)

    def _add_custom_goto(self):
        """
        Add entries and button for a custom GOTO (phi, theta).
        """
        self.phi_entry = ctk.CTkEntry(self, placeholder_text="Phi (°)", width=130)
        self.phi_entry.grid(row=6, column=0, padx=5, pady=5)

        self.theta_entry = ctk.CTkEntry(self, placeholder_text="Theta (°)", width=130)
        self.theta_entry.grid(row=6, column=1, padx=5, pady=5)

        ctk.CTkButton(self, text="GOTO CUSTOM", command=self.goto_custom).grid(row=6, column=2, padx=10, pady=5)
        ctk.CTkButton(self, text="CLOSE", command=self.handle_close).grid(row=6, column=4, padx=10, pady=5)

    def _add_textbox(self):
        """
        Add a textbox for status and position feedback.
        """
        self.textbox = ctk.CTkTextbox(self, height=100, width=600, wrap="word")
        self.textbox.grid(row=5, column=4, padx=10, pady=10, columnspan=4, sticky="nsew")
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth() + 100}x{self.winfo_reqheight() + 100}")

    # ---------------------- Arduino rotation helpers ----------------------

    def rot_move_rel(self, deg: float):
        """
        Move the Arduino rotation stage by a relative angle.

        Parameters
        ----------
        deg : float
            Relative rotation in degrees (positive CW/CCW depends on stage config).
        """
        try:
            if self.rot is None:
                raise RuntimeError("Rotation stage not initialized.")
            reply = self.rot.move_rel_deg(deg)
            self.rot.wait_estimate(deg)
            if reply is not None:
                self.update_textbox(f"Rot moved {deg}°, echo: {reply}")
            else:
                self.update_textbox(f"Rot moved {deg}°")
        except Exception as e:
            self.update_textbox(f"Rot move failed: {e}")

    def rot_save0(self):
        """
        Set the current rotation position as the origin (0°).
        """
        try:
            if self.rot is None:
                raise RuntimeError("Rotation stage not initialized.")
            r = self.rot.reset_origin()
            self.update_textbox(f"Rot origin set (reply: {r})")
        except Exception as e:
            self.update_textbox(f"Rot zero failed: {e}")

    def rot_goto(self):
        """
        Move the Arduino rotation stage to an absolute angle (degrees).
        """
        try:
            if self.rot is None:
                raise RuntimeError("Rotation stage not initialized.")
            target = float(self.rot_goto_entry.get())
            self.rot.move_abs_deg(target)
            self.rot.wait_estimate(target)  # crude estimate
            self.update_textbox(f"Rot moved to {target}° (abs)")
        except ValueError:
            self.update_textbox("Rot GOTO: enter a number.")
        except Exception as e:
            self.update_textbox(f"Rot goto failed: {e}")

    # ---------------------- PHI MOVEMENT ----------------------
    # due to the absolute coordinates of the arm, the applied coordinate system is opposite of the absolute phi

    def phiminus10(self):
        """Jog phi by -10° (applied as +10 in controller)."""
        self.move_and_refresh(+10, 0)

    def phiminus1(self):
        """Jog phi by -1° (applied as +1 in controller)."""
        self.move_and_refresh(+1, 0)

    def phiminus0p1(self):
        """Jog phi by -0.1°."""
        self.move_and_refresh(+0.1, 0)

    def phiminus0p02(self):
        """Jog phi by -0.02°."""
        self.move_and_refresh(+0.02, 0)

    def phiplus0p02(self):
        """Jog phi by +0.02° (applied as -0.02)."""
        self.move_and_refresh(-0.02, 0)

    def phiplus0p1(self):
        """Jog phi by +0.1° (applied as -0.1)."""
        self.move_and_refresh(-0.1, 0)

    def phiplus1(self):
        """Jog phi by +1° (applied as -1)."""
        self.move_and_refresh(-1, 0)

    def phiplus10(self):
        """Jog phi by +10° (applied as -10)."""
        self.move_and_refresh(-10, 0)

    # ---------------------- THETA MOVEMENT ----------------------

    def thetaminus10(self):
        """Jog theta by -10°."""
        self.move_and_refresh(0, -10)

    def thetaminus1(self):
        """Jog theta by -1°."""
        self.move_and_refresh(0, -1)

    def thetaminus0p1(self):
        """Jog theta by -0.1°."""
        self.move_and_refresh(0, -0.1)

    def thetaminus0p02(self):
        """Jog theta by -0.02°."""
        self.move_and_refresh(0, -0.02)

    def thetaplus0p02(self):
        """Jog theta by +0.02°."""
        self.move_and_refresh(0, 0.02)

    def thetaplus0p1(self):
        """Jog theta by +0.1°."""
        self.move_and_refresh(0, 0.1)

    def thetaplus1(self):
        """Jog theta by +1°."""
        self.move_and_refresh(0, 1)

    def thetaplus10(self):
        """Jog theta by +10°."""
        self.move_and_refresh(0, 10)

    # ---------------------- POSITION AND CONTROL ----------------------

    def home_phi(self):
        """Home the phi axis and refresh position readout."""
        self.ctrl.home_x()
        self.refresh(45)

    def home_theta(self):
        """Home the theta axis and refresh position readout."""
        self.ctrl.home_y()
        self.refresh(45)

    def homea(self):
        """Home the A axis and refresh position readout."""
        self.ctrl.home_a()
        self.refresh(45)

    def home(self):
        """Home phi, theta, and A axes; then refresh."""
        self.ctrl.home_xya()
        self.refresh(45)

    def save0(self):
        """Save the current position as (0,0,0)."""
        self.ctrl.save0()
        self.refresh()

    def goto0(self):
        """Move to the saved (0,0,0) and refresh."""
        self.ctrl.move_to(0, 0)
        self.refresh()

    def goto_custom(self):
        """
        Move to a custom (phi, theta) while preserving current z/a.

        Notes
        -----
        Phi sign is inverted to match the applied coordinate system.
        """
        try:
            phi_target = float(self.phi_entry.get())
            theta_target = float(self.theta_entry.get())
            _, _, z, a, *_ = self.ctrl.query_position()
            self.ctrl.move_to(-phi_target, theta_target, z, a)
            self.refresh()
        except ValueError:
            self.update_textbox("Invalid input. Please enter numeric values for Phi and Theta.")
        except Exception as e:
            self.update_textbox(f"Failed to move: {e}")

    def refresh(self, timeout: float = 10):
        """
        Wait for motion to complete and update the status textbox.

        Parameters
        ----------
        timeout : float
            Seconds to wait for the controller to become idle.
        """
        try:
            self.ctrl.wait_for_idle(timeout)
        except RuntimeError as e:
            self.update_textbox(f"Move timeout: {e}")
            return
        phi, theta, z, a, *_ = self.ctrl.query_position()
        self.update_textbox(f"Current Position: Phi: {-phi} Theta: {theta} Z{z} A{a}")

    def move_and_refresh(self, dphi: float, dtheta: float, dz: float = 0, da: float = 0):
        """
        Delta move by (dphi, dtheta, dz, da) and refresh the readout.

        Parameters
        ----------
        dphi : float
            Delta for phi (deg). Positive sign is applied directly to the controller.
        dtheta : float
            Delta for theta (deg).
        dz : float, optional
            Delta for Z axis.
        da : float, optional
            Delta for A axis.
        """
        phi0, theta0, z0, a0, *_ = self.ctrl.query_position()
        self.ctrl.move_to(phi0 + dphi, theta0 + dtheta, z0 + dz, a0 + da)
        self.refresh()

    def update_textbox(self, text: str):
        """
        Replace the textbox contents with a status string.

        Parameters
        ----------
        text : str
            Message to display in the status area.
        """
        self.textbox.delete("1.0", "end")
        self.textbox.insert("end", text)

    def handle_close(self):
        """
        Safely close the rotation stage (if present) and destroy the window.
        """
        try:
            if self.rot is not None:
                self.rot.close()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass