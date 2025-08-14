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
    - Optional Arduino-based rotation stage controls (collapsible/compact)
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
        self.rot: Optional[ArduinoRotationStage] = rot_stage or ArduinoRotationStage(
            ArduinoStageConfig(port=getattr(settings, "ARDUINO_PORT", "COM7"))
        )

        self.connected = False  # rotation stage connection state (best-effort/soft)
        self._rot_poll_id = None  # after()-id for status polling

        self._setup_window()
        self._add_banner()

        # --- Compact, collapsible rotation stage UI
        self._build_rotary_header_and_panel()   # header row + hidden detail panel (row=1)

        self._add_phi_controls()    # rows 2–3
        self._add_theta_controls()
        self._add_home_controls()   # row 4
        self._add_zero_controls()   # rows 4–5
        self._add_custom_goto()     # row 6
        self._add_textbox()         # row 5 (wide)

        # start with rotary panel collapsed to be unobtrusive
        self._set_rotary_collapsed(True)

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
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
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
            ctk.CTkLabel(self, text=f"[Banner missing: {e}]").grid(row=0, column=4, padx=10, pady=10)

    # ---------------------- Compact Rotary UI ----------------------

    def _build_rotary_header_and_panel(self):
        """
        Create a slim header bar with a toggle to expand/collapse the rotary controls,
        plus a hidden details frame with jog/goto/zero controls.
        """
        # Header row (very compact)
        self.rot_header = ctk.CTkFrame(self, fg_color="transparent")
        self.rot_header.grid(row=1, column=0, columnspan=9, padx=10, pady=(0, 0), sticky="ew")
        self.rot_header.grid_columnconfigure(0, weight=1)
        self.rot_header.grid_columnconfigure(1, weight=0)

        self.rot_toggle_btn = ctk.CTkButton(
            self.rot_header,
            text="Rotation Stage ▸",
            width=140,
            height=28,
            command=self._toggle_rotary_panel
        )
        self.rot_toggle_btn.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)

        # tiny status chip on the right
        self.rot_status_chip = ctk.CTkLabel(
            self.rot_header,
            text="Disconnected",
            font=("Helvetica", 12, "bold"),
            text_color="white",
            fg_color="#555555",
            corner_radius=12,
            padx=10, pady=4
        )
        self.rot_status_chip.grid(row=0, column=1, sticky="e", pady=4)

        # Details panel (hidden when collapsed)
        self.rot_panel = ctk.CTkFrame(self, corner_radius=10)
        self.rot_panel.grid(row=1, column=0, columnspan=9, padx=10, pady=(4, 6), sticky="ew")
        for c in range(12):
            self.rot_panel.grid_columnconfigure(c, weight=1)

        # Row 0: Title (subtle) + quick small nudges (compact)
        ctk.CTkLabel(self.rot_panel, text="Rotation Stage (Arduino)", font=("Helvetica", 13, "bold")
                     ).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 2))

        # Row 1: compact jog segmented buttons
        # We use small CTkButtons arranged tightly instead of a huge row of big buttons
        jogs = [(-10, "−10°"), (-1, "−1°"), (-0.1, "−0.1°"), (-0.02, "−0.02°"),
                (0.02, "+0.02°"), (0.1, "+0.1°"), (1, "+1°"), (10, "+10°")]
        for i, (val, label) in enumerate(jogs):
            ctk.CTkButton(self.rot_panel, text=label, width=74, height=30,
                          command=lambda d=val: self.rot_move_rel(d)
                          ).grid(row=1, column=i, padx=3, pady=6, sticky="ew")

        # Row 2: absolute goto + save zero (compact)
        self.rot_goto_entry = ctk.CTkEntry(self.rot_panel, placeholder_text="GOTO (°)", width=120)
        self.rot_goto_entry.grid(row=2, column=0, columnspan=2, padx=6, pady=(2, 10), sticky="w")

        ctk.CTkButton(self.rot_panel, text="Go", width=70, command=self.rot_goto
                      ).grid(row=2, column=2, padx=4, pady=(2, 10), sticky="w")

        ctk.CTkButton(self.rot_panel, text="Save 0°", width=90, command=self.rot_save0
                      ).grid(row=2, column=3, padx=4, pady=(2, 10), sticky="w")

        # update the chip based on current state
        self._update_rot_status_chip(connected=self._detect_rot_connected())

    def _detect_rot_connected(self) -> bool:
        """
        Best-effort detection of whether the Arduino stage is usable.
        """
        try:
            return bool(self.rot is not None and getattr(self.rot, "is_open", True))
        except Exception:
            return self.rot is not None

    def _update_rot_status_chip(self, connected: bool):
        """
        Update the small status chip text and color.
        """
        if connected:
            self.rot_status_chip.configure(text="Connected", fg_color="#2e7d32")  # green
        else:
            self.rot_status_chip.configure(text="Disconnected", fg_color="#7b1fa2")  # purple-ish

    # --- NEW: status chip update from BUSY/IDLE (non-breaking, separate from 'connected') ---
    def _set_rot_status_state(self, state_txt: str):
        """
        Update chip to BUSY/IDLE (color-coded).
        Accepts 'BUSY', 'IDLE', or any other string → falls back to 'Connected'.
        """
        st = (state_txt or "").upper()
        if st == "BUSY":
            self.rot_status_chip.configure(text="BUSY", fg_color="#f9a825")   # amber
        elif st == "IDLE":
            self.rot_status_chip.configure(text="IDLE", fg_color="#2e7d32")   # green
        else:
            # fallback to just connected color
            self._update_rot_status_chip(self._detect_rot_connected())

    # --- NEW: lightweight polling to keep chip fresh while panel is open ---
    def _poll_rot_status(self):
        if not self.rot_panel.winfo_ismapped():
            return  # don't poll while collapsed
        try:
            if self._detect_rot_connected():
                st = self.rot.query_status()
                if st:
                    self._set_rot_status_state(st)
                else:
                    self._update_rot_status_chip(True)
            else:
                self._update_rot_status_chip(False)
        except Exception:
            self._update_rot_status_chip(False)
        # schedule next poll
        self._rot_poll_id = self.after(600, self._poll_rot_status)

    def _set_rotary_collapsed(self, collapsed: bool):
        """
        Show/hide the rotary detail panel and adjust toggle icon.
        """
        if collapsed:
            self.rot_panel.grid_remove()
            self.rot_toggle_btn.configure(text="Rotation Stage ▸")
            # stop polling when hidden
            if self._rot_poll_id:
                try:
                    self.after_cancel(self._rot_poll_id)
                except Exception:
                    pass
                self._rot_poll_id = None
        else:
            self.rot_panel.grid()  # re-show in the same grid slot
            self.rot_toggle_btn.configure(text="Rotation Stage ▾")
            # start polling when visible
            if self._rot_poll_id is None:
                self._poll_rot_status()

    def _toggle_rotary_panel(self):
        """
        Toggle between collapsed and expanded panel.
        """
        visible = self.rot_panel.winfo_ismapped()
        self._set_rotary_collapsed(visible)  # if visible -> collapse; else expand

        # when expanding, refresh the status chip
        if not visible:
            self._update_rot_status_chip(self._detect_rot_connected())

    # ---------------------- PHI MOVEMENT ----------------------
    # due to the absolute coordinates of the arm, the applied coordinate system is opposite of the absolute phi

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

    # ---------------------- THETA MOVEMENT ----------------------

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

    # ---------------------- HOMING / ZERO / GOTO ----------------------

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
        """
        try:
            if self.rot is None:
                raise RuntimeError("Rotation stage not initialized.")

            reply = self.rot.move_rel_deg(deg)  # firmware echoes relative steps
            # deterministic wait using BUSY/DONE (fallback to estimate on timeout)
            ok = self.rot.wait_until_done(timeout=30.0)
            if not ok:
                self.rot.wait_estimate(deg)  # last-resort fallback (kept behavior-safe)

            self.update_textbox(
                f"Rot moved {deg}°" +
                (f", echo: {reply}" if reply is not None else "") +
                ("" if ok else " (timed out → fallback wait)")
            )
            # update status chip
            self._set_rot_status_state(self.rot.query_status() or "IDLE")
        except Exception as e:
            self.update_textbox(f"Rot move failed: {e}")
            self._update_rot_status_chip(False)

    def rot_save0(self):
        """
        Set the current rotation position as the origin (0°).
        """
        try:
            if self.rot is None:
                raise RuntimeError("Rotation stage not initialized.")
            r = self.rot.reset_origin()
            self.update_textbox(f"Rot origin set (reply: {r})")
            # reflect persisted zero just by showing current status
            self._set_rot_status_state(self.rot.query_status() or "IDLE")
        except Exception as e:
            self.update_textbox(f"Rot zero failed: {e}")
            self._update_rot_status_chip(False)

    def rot_goto(self):
        """
        Move the Arduino rotation stage to an absolute angle (degrees).
        """
        try:
            if self.rot is None:
                raise RuntimeError("Rotation stage not initialized.")
            target = float(self.rot_goto_entry.get())

            self.rot.move_abs_deg(target)
            # NEW: deterministic wait using DONE/IDLE
            ok = self.rot.wait_until_done(timeout=60.0)
            if not ok:
                self.rot.wait_estimate(target)  # fallback (kept for safety)

            self.update_textbox(f"Rot moved to {target}° (abs)" + ("" if ok else " (timed out → fallback wait)"))
            self._set_rot_status_state(self.rot.query_status() or "IDLE")
        except ValueError:
            self.update_textbox("Rot GOTO: enter a number.")
        except Exception as e:
            self.update_textbox(f"Rot goto failed: {e}")
            self._update_rot_status_chip(False)

    # ---------------------- PHI MOVEMENT ----------------------

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
        """
        phi0, theta0, z0, a0, *_ = self.ctrl.query_position()
        self.ctrl.move_to(phi0 + dphi, theta0 + dtheta, z0 + dz, a0 + da)
        self.refresh()

    def update_textbox(self, text: str):
        """
        Replace the textbox contents with a status string.
        """
        self.textbox.delete("1.0", "end")
        self.textbox.insert("end", text)

    def handle_close(self):
        """
        Safely close the rotation stage (if present) and destroy the window.
        """
        # stop polling cleanly
        try:
            if self._rot_poll_id:
                self.after_cancel(self._rot_poll_id)
        except Exception:
            pass
        self._rot_poll_id = None

        try:
            if self.rot is not None:
                self.rot.close()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass