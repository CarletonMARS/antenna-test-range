import csv
import customtkinter as ctk
from PIL import Image
import pyvisa
import tkinter as tk
import time
import serial
import settings
from decimal import *
import pprint
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from datetime import datetime
import sys
import os
import threading
from interfaces.serial_interface import SerialController
class manual_control_App(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__()
        self.ctrl = None
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.lift()
        self.after(10, lambda: self.focus_force())
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.geometry("3440x1440")
        self.title("POSITIONER MANUAL CONTROL")

        # BANNER IMAGE
        image_path = "DUO5.png"
        image = Image.open(image_path)
        self.ctk_image = ctk.CTkImage(light_image=image, size=(200, 200))
        self.label = ctk.CTkLabel(self, image=self.ctk_image, text="")
        self.label.grid(row=0, column=4, padx=10, pady=10)

        #CONNECT
        self.connect_button = ctk.CTkButton(self, text="connect", command=self.connect_to_controller)
        self.connect_button.grid(row=1, column=4, pady=10, padx=10)

        #X -10
        self.xminus10_button = ctk.CTkButton(self, text="X -10", command=self.xminus10)
        self.xminus10_button.grid(row=2, column=0, pady=10, padx=10)

        #X -1
        self.xminus1_button = ctk.CTkButton(self, text="X -1", command=self.xminus1)
        self.xminus1_button.grid(row=2, column=1, pady=10, padx=10)

        #X -0.1
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

        #Home X
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

        #Goto 000
        self.goto0_button = ctk.CTkButton(self, text="GOTO 0,0,0", command=self.goto0)
        self.goto0_button.grid(row=4, column=7, pady=10, padx=10)

        #Close
        self.close_button = ctk.CTkButton(self, text='CLOSE', command=self.close)
        self.close_button.grid(row=6, column=4, padx=1, pady=1)

        #TEXTBOX
        self.textbox = ctk.CTkTextbox(self, height=100, width=1500, wrap="word")
        self.textbox.grid(row=5, column=4, padx=10, pady=10)

    def connect_to_controller(self):
        self.ctrl = SerialController(settings.COM_PORT, settings.BAUD_RATE)
        try:
            x,y,z,a,b,c = self.ctrl.query_position()
            self.update_textbox(f"Connected. Position at connection time is X{x} Y{y} A{a}\n")
            self.connect_button.configure(text='Connected', state=tk.DISABLED)
        except Exception as e:
            self.update_textbox(f"Failed to connect: {e}")

    def update_textbox(self, text):
        """Updates the textbox with new text."""
        self.textbox.delete("1.0", "end")  # Clear previous text
        self.textbox.insert("end", text)  # Insert new text

    def xminus10(self):
        self.move_and_refresh(-10,0)

    def xminus1(self):
        self.move_and_refresh(-1,0)

    def xminus0p1(self):
        self.move_and_refresh(-0.1,0)

    def xminus0p02(self):
        self.move_and_refresh(-0.02,0)


    def xplus0p02(self):
        self.move_and_refresh(0.02,0)


    def xplus0p1(self):
        self.move_and_refresh(0.1,0)

    def xplus1(self):
        self.move_and_refresh(1,0)

    def xplus10(self):
        self.move_and_refresh(10,0)


    def yminus10(self):
        self.move_and_refresh(0,-10)


    def yminus1(self):
        self.move_and_refresh(0,-1)

    def yminus0p1(self):
        self.move_and_refresh(0,-0.1)

    def yminus0p02(self):
        self.move_and_refresh(0,-0.02)

    def yplus0p02(self):
        self.move_and_refresh(0, 0.02)

    def yplus0p1(self):
        self.move_and_refresh(0, 0.1)

    def yplus1(self):
        self.move_and_refresh(0, 1)

    def yplus10(self):
        self.move_and_refresh(0, 10)

    def homex(self):
        self.ctrl.home_x()
        self.refresh(45)

    def homey(self):
        self.ctrl.home_y()
        self.refresh(45)

    def homea(self):
        self.ctrl.home_a()
        self.refresh(45)

    def home(self):
        self.ctrl.home_xya()
        self.refresh(45)

    def goto0(self):
        self.zero_and_refresh()

    def get_position(self):
        # try:
        #     self.serial_connection.flushInput()
        #     self.serial_connection.write(('?').encode('utf-8'))
        #     time.sleep(0.1)
        #     response = self.serial_connection.readline().decode('utf-8').strip()
        #
        #     if '<Idle|WPos:' in response:
        #         try:
        #             values = response.split('|')[1].split(':')[1].split(',')
        #             x, y, z, a = float(values[0]), float(values[1]), float(values[2]), float(values[3])
        #             self.update_textbox(f"Current Position: X{x} Y{y} A{a}")
        #             return float(x), float(y), float(a)
        #         except (IndexError, ValueError):
        #             self.update_textbox("Invalid response format for position.")
        #             return None, None, None
        #     else:
        #         self.update_textbox("Failed. Was the RESULTS file opened?")
        #         return None, None, None
        # except serial.SerialException as e:
        #     self.update_textbox(f"Error in getting position: {str(e)}")
        #     return None, None, None
        try:
            x, y, z, a, *_ = self.ctrl.query_position()
            self.update_textbox(f"Current Position: X{x} Y{y} A{a}")
            return x, y, z, a
        except Exception as e:
            self.update_textbox(f"Error in getting position: {str(e)}")
            return None, None, None, None

    def refresh(self, timeout=10):
        try:
            self.ctrl.wait_for_idle(timeout)
        except RuntimeError as e:
            return self.update_textbox(f"Move timeout: {e}")
        x1, y1, *_ = self.ctrl.query_position()
        self.update_textbox(f"Current Position: X{x1} Y{y1} A0")

    def move_and_refresh(self, dx, dy):
        x0, y0, *_ = self.ctrl.query_position()
        target_x = x0 + dx
        target_y = y0 + dy
        self.ctrl.move_to(target_x, target_y)
        self.refresh()

    def zero_and_refresh(self):

        self.ctrl.move_to(0, 0)
        self.refresh()


    def close(self):
        self.ctrl.handle_close()
        self.destroy()

class SFP(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__()
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.lift()
        self.after(10, lambda: self.focus_force())
        self.start_gui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.connect()

    def start_gui(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.geometry("3440x1440")
        self.title("AGILENT 8722ES SOFT FRONT PANEL")

        # BANNER IMAGE
        image_path = "Keysight_Agilent_8722ES.jpg"
        image = Image.open(image_path)
        self.ctk_image = ctk.CTkImage(light_image=image, size=(350, 201))
        self.label = ctk.CTkLabel(self, image=self.ctk_image, text="")
        self.label.grid(row=0, column=2, padx=10, pady=10)

        # Connect button
        self.connectButton = ctk.CTkButton(self, text="CONNECT", command=self.connect)
        self.connectButton.grid(row=0, column=0, padx=1, pady=1)

        # Measure button
        self.meas = ctk.CTkButton(self, text="Meas", command=self.measure)
        self.meas.grid(row=1, column=0, padx=1, pady=1)

        #FORMAT BUTTON
        self.formatbutton = ctk.CTkButton(self, text="Format", command=self.format)
        self.formatbutton.grid(row=1, column=1, padx=1, pady=1)

        #Scale Ref Button
        self.scalerefbutton = ctk.CTkButton(self, text="Scale Ref", command=self.scaleref)
        self.scalerefbutton.grid(row=1, column=2, padx=1, pady=1)

        #Start frequency button
        self.startbutton = ctk.CTkButton(self, text="START", command=self.start)
        self.startbutton.grid(row=2, column=0, padx=1, pady=1)

        #STOP
        self.stopbutton = ctk.CTkButton(self, text="STOP", command=self.stop)
        self.stopbutton.grid(row=2, column=1, padx=1, pady=1)

        #POWER
        self.powerbutton = ctk.CTkButton(self, text="POWER", command=self.power)
        self.powerbutton.grid(row=2, column=2, padx=1, pady=1)

        self.centrebutton = ctk.CTkButton(self, text="CENTRE", command=self.centre)
        self.centrebutton.grid(row=2, column=3, padx=1, pady=1)

        self.spanbutton = ctk.CTkButton(self, text="SPAN", command=self.span)
        self.spanbutton.grid(row=2, column=4, padx=1, pady=1)

        self.readtracebutton = ctk.CTkButton(self, text="DISPLAY TRACE", command=self.create_dataplot)
        self.readtracebutton.grid(row=3, column=2, padx=1, pady=1)

        self.plot_frame = ctk.CTkFrame(self)
        self.plot_frame.grid(row=3, column=5, padx=1, pady=1)
        self.canvas = None
        self.toolbar = None

        self.exportcsvbutton = ctk.CTkButton(self, text="EXPORT CSV", command=self.exportcsv)
        self.exportcsvbutton.grid(row=3, column=3, padx=1, pady=1)

        self.clear_error_messages_button = ctk.CTkButton(self, text='RESET VNA', command=self.clear)
        self.clear_error_messages_button.grid(row=4, column=0, padx=1, pady=1)

        #close button
        self.close_button = ctk.CTkButton(self, text="CLOSE", command=self.close)
        self.close_button.grid(row=4, column=3, padx=1, pady=1)

    def clear(self):
        self.write("*RST")

    def write(self, msg):
        self.VNA.write(msg)
        time.sleep(0.1)

    def connect(self):
        try:
            self.rm = pyvisa.ResourceManager()
            self.VNA = self.rm.open_resource("GPIB0::16::INSTR")
            print(self.VNA.query("*IDN?"))
            self.connectButton.configure(text='Connected', state=tk.DISABLED)
            self.connected_flag = True
        except pyvisa.VisaIOError:
            print("FAILED TO CONNECT TO VNA")

    def measure(self):
        self.erase_gui()
        self.create_sparams()

    def erase_gui(self):
        for widget in self.winfo_children():
            widget.destroy()

    def create_sparams(self):
        self.s11button = ctk.CTkButton(self, text="S11", command=self.s11)
        self.s11button.grid(row=0, column=0, padx=10, pady=10)
        self.s12button = ctk.CTkButton(self, text='S12', command=self.s12)
        self.s12button.grid(row=0, column=1, padx=10, pady=10)
        self.s21button = ctk.CTkButton(self, text='S21', command=self.s21)
        self.s21button.grid(row=0, column=2, padx=10, pady=10)
        self.s22button = ctk.CTkButton(self, text='S22', command=self.s22)
        self.s22button.grid(row=0, column=3, padx=10, pady=10)
        self.sparamsbackbutton = ctk.CTkButton(self, text='BACK', command=self.format_back)
        self.sparamsbackbutton.grid(row=0, column=4, padx=1, pady=1)

    def s11(self):
        self.write("S11")

    def s12(self):
        self.write("S12")

    def s21(self):
        self.write("S21")

    def s22(self):
        self.write("S22")

    def on_close(self):
        if self.VNA:
            self.VNA.control_ren(0)
            self.VNA.close()
            print("VNA disconnected")
        self.destroy()

    def format(self):
        self.erase_gui()
        self.create_format()

    def create_format(self):
        self.LOGMAGbutton = ctk.CTkButton(self, text="LOG MAG", command=self.LOGMAG)
        self.LOGMAGbutton.grid(row=0, column=0, padx=1, pady=1)
        self.phasebutton = ctk.CTkButton(self, text = "PHASE", command=self.phase)
        self.phasebutton.grid(row=0, column=1, padx=1, pady=1)
        self.delaybutton = ctk.CTkButton(self, text='DELAY', command=self.delay)
        self.delaybutton.grid(row=0, column=2, padx=1, pady=1)
        self.SCButton = ctk.CTkButton(self, text="SMITH CHART", command=self.smithchart)
        self.SCButton.grid(row=0, column=3, padx=1, pady=1)
        self.polarbutton = ctk.CTkButton(self, text="POLAR", command=self.polar)
        self.polarbutton.grid(row=0, column=4, padx=1, pady=1)
        self.LINMAGbutton = ctk.CTkButton(self, text='LIN MAG', command=self.LINMAG)
        self.LINMAGbutton.grid(row=0, column=5, padx=1, pady=1)
        self.swrbutton = ctk.CTkButton(self, text='SWR', command=self.SWR)
        self.swrbutton.grid(row=0, column=6, padx=1, pady=1)
        self.realbutton = ctk.CTkButton(self, text='REAL', command=self.real)
        self.realbutton.grid(row=0, column=7, padx=1, pady=1)
        self.imagbutton = ctk.CTkButton(self, text='IMAG', command=self.imag)
        self.imagbutton.grid(row=0, column=8, padx=1, pady=1)
        self.backbutton = ctk.CTkButton(self, text="BACK", command=self.format_back)
        self.backbutton.grid(row=0, column=9, padx=1, pady=1)

    def LOGMAG(self):
        self.write("LOGM")

    def phase(self):
        self.write("PHAS")

    def delay(self):
        self.write("DELA")

    def smithchart(self):
        self.write("SMIC")

    def polar(self):
        self.write("POLA")

    def LINMAG(self):
        self.write("LINM")

    def SWR(self):
        self.write("SWR")

    def real(self):
        self.write("REAL")

    def imag(self):
        self.write("IMAG")

    def format_back(self):
        self.erase_gui()
        self.start_gui()

    def scaleref(self):
        self.erase_gui()
        self.create_scaleref()

    def create_scaleref(self):
        self.autoscalebutton = ctk.CTkButton(self, text='AUTO SCALE', command=self.autoscale)
        self.autoscalebutton.grid(row=0, column=0, padx=1, pady=1)
        self.scalerefbackbutton = ctk.CTkButton(self, text="BACK", command=self.format_back)
        self.scalerefbackbutton.grid(row=0, column=1, padx=1, pady=1)

    def autoscale(self):
        self.write("AUTO")

    def start(self):
        self.erase_gui()
        self.create_start()

    def create_start(self):
        self.startlabel = ctk.CTkLabel(self, text="ENTER START FREQUENCY IN GHz", font=("Arial", 16), text_color="white")
        self.startlabel.grid(row=0, column=0, padx=1, pady=1)
        self.estart = ctk.CTkEntry(self, placeholder_text="f_start")
        self.estart.grid(row=0, column=1, padx=1, pady=1)
        self.enterbutton = ctk.CTkButton(self, text='Enter', command=self.getstart)
        self.enterbutton.grid(row=0, column=2, padx=1, pady=1)
        self.startbackbutton = ctk.CTkButton(self, text="back", command=self.format_back)
        self.startbackbutton.grid(row=1, column = 3, padx=1, pady=1)

    def getstart(self):
        self.start = str(self.estart.get())
        self.write("STAR " + self.start + "GHz")
        time.sleep(0.1)

    def stop(self):
        self.erase_gui()
        self.create_stop()

    def create_stop(self):
        self.stoplabel = ctk.CTkLabel(self, text="ENTER STOP FREQUENCY IN GHz", font=("Arial", 16),
                                       text_color="white")
        self.stoplabel.grid(row=0, column=0, padx=1, pady=1)
        self.estop = ctk.CTkEntry(self, placeholder_text="f_stop")
        self.estop.grid(row=0, column=1, padx=1, pady=1)
        self.enterbutton = ctk.CTkButton(self, text='Enter', command=self.getstop)
        self.enterbutton.grid(row=0, column=2, padx=1, pady=1)
        self.stopbackbutton = ctk.CTkButton(self, text="back", command=self.format_back)
        self.stopbackbutton.grid(row=1, column=3, padx=1, pady=1)

    def getstop(self):
        self.stop = str(self.estop.get())
        self.write("STOP " + self.stop + "GHz")
        time.sleep(0.1)

    def power(self):
        self.erase_gui()
        self.create_power()

    def create_power(self):
        self.powerlabel = ctk.CTkLabel(self, text="ENTER POWER in dBm (-20 to -5)", font=("Arial", 16),
                                      text_color="white")
        self.powerlabel.grid(row=0, column=0, padx=1, pady=1)
        self.epower = ctk.CTkEntry(self, placeholder_text="power")
        self.epower.grid(row=0, column=1, padx=1, pady=1)
        self.enterbutton = ctk.CTkButton(self, text='Enter', command=self.getpower)
        self.enterbutton.grid(row=0, column=2, padx=1, pady=1)
        self.powerbackbutton = ctk.CTkButton(self, text="back", command=self.format_back)
        self.powerbackbutton.grid(row=1, column=3, padx=1, pady=1)

    def getpower(self):
        self.power = str(self.epower.get())
        self.write("POWE " + self.power)
        time.sleep(0.1)

    def centre(self):
        self.erase_gui()
        self.create_centre()

    def create_centre(self):
        self.centrelabel = ctk.CTkLabel(self, text="ENTER CENTRE FREQUENCY (GHz)", font=("Arial", 16),
                                       text_color="white")
        self.centrelabel.grid(row=0, column=0, padx=1, pady=1)
        self.ecentre = ctk.CTkEntry(self, placeholder_text="f_centre")
        self.ecentre.grid(row=0, column=1, padx=1, pady=1)
        self.centrebutton = ctk.CTkButton(self, text='Enter', command=self.getcentre)
        self.centrebutton.grid(row=0, column=2, padx=1, pady=1)
        self.centrebackbutton = ctk.CTkButton(self, text="back", command=self.format_back)
        self.centrebackbutton.grid(row=1, column=3, padx=1, pady=1)

    def getcentre(self):
        self.centre = str(self.ecentre.get())
        self.write("CENT " + self.centre + "GHz")
        time.sleep(0.1)

    def span(self):
        self.erase_gui()
        self.create_span()

    def create_span(self):
        self.spanlabel = ctk.CTkLabel(self, text="ENTER SPAN (GHz)", font=("Arial", 16),
                                       text_color="white")
        self.spanlabel.grid(row=0, column=0, padx=1, pady=1)
        self.espan = ctk.CTkEntry(self, placeholder_text="f_span")
        self.espan.grid(row=0, column=1, padx=1, pady=1)
        self.spanbutton = ctk.CTkButton(self, text='Enter', command=self.getspan)
        self.spanbutton.grid(row=0, column=2, padx=1, pady=1)
        self.spanbackbutton = ctk.CTkButton(self, text="back", command=self.format_back)
        self.spanbackbutton.grid(row=1, column=3, padx=1, pady=1)

    def getspan(self):
        self.span = str(self.espan.get())
        self.write("SPAN " + self.span + "GHz")
        time.sleep(0.1)

    def readtrace(self):
        self.write("OUTPLIML")
        self.frequency_points = self.VNA.read().split("\n") #Read frequency points, split at newline

        self.write("FORM5;")
        self.write("CHAN1;")

        self.result_mags = self.VNA.query_binary_values("OUTPFORM;", container=tuple, header_fmt="hp")

        print(len(self.frequency_points), len(self.result_mags))

        data_list = []

        for i, j in enumerate(self.frequency_points):
            if i != (len(self.frequency_points)-1):
                data_list.append([(float(self.frequency_points[i].split(",")[0].strip(" ")))/1e9, self.result_mags[i*2]])

        return data_list

    def create_dataplot(self):
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
            self.toolbar.destroy()
            self.canvas = None
            self.toolbar = None

        self.data = self.readtrace()
        self.frequencies = []
        self.magnitudes = []
        for i, j in enumerate(self.data):
            self.frequencies.append(self.data[i][0])
            self.magnitudes.append(self.data[i][1])

        pprint.pprint(self.frequencies)
        pprint.pprint(self.magnitudes)

        self.plot = plt.figure(figsize=(8, 6))
        plt.plot(self.frequencies, self.magnitudes, label='Magnitude')
        plt.xlabel('Frequency (GHz)')
        plt.ylabel('Magnitude (dB)')
        plt.title('Magnitude vs Frequency')
        plt.legend()
        plt.grid(False)

        num_ticks = 10

        # Generate tick positions evenly spaced between the first and last frequency values
        self.ticks = np.linspace(self.frequencies[0], self.frequencies[-1], num_ticks)

        # Create formatted tick labels to show two decimal places
        self.tick_labels = [f"{tick:.2f}" for tick in self.ticks]

        # Set the x-axis ticks to the generated positions and labels
        plt.xticks(self.ticks, self.tick_labels)




        # Embed the Matplotlib figure into the CustomTkinter frame
        self.canvas = FigureCanvasTkAgg(self.plot, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)


        # Add a Matplotlib navigation toolbar (optional)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.update()
        self.toolbar.pack(side="bottom", fill="x")

    def exportcsv(self):
        self.erase_gui()
        self.create_export()

    def create_export(self):
        self.exportlabel = ctk.CTkLabel(self, text="Enter File Name", font=("Arial", 16),
                                       text_color="white")
        self.exportlabel.grid(row=0, column=0, padx=1, pady=1)
        self.eexport = ctk.CTkEntry(self, placeholder_text="path")
        self.eexport.grid(row=0, column=1, padx=1, pady=1)
        self.enterbutton = ctk.CTkButton(self, text='Enter', command=self.getexport)
        self.enterbutton.grid(row=0, column=2, padx=1, pady=1)
        self.exportbackbutton = ctk.CTkButton(self, text="back", command=self.format_back)
        self.exportbackbutton.grid(row=1, column=3, padx=1, pady=1)

    def getexport(self):
        self.export_path = str(self.eexport.get())
        self.data = self.readtrace()
        self.today = (str(datetime.now())).split(" ")[0]

        self.full_directory = "C:\\Users\\alexszabo\\Desktop\\NEW POSITIONER FEB 2025\\CSV EXPORTS\\" + self.today

        if not os.path.exists(self.full_directory):
            os.makedirs(self.full_directory)

        with open(self.full_directory + "\\" + self.export_path + ".csv", 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(self.data)

    def close(self):
        self.destroy()

class threeDpat(ctk.CTkToplevel):

    def __init__(self, parent):
        super().__init__()

        self.theta = None
        self.phi = None
        self.stop = None
        self.step = None
        self.start = None
        self.path = None
        self.IFbandwidth = None
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.lift()
        self.after(10, lambda: self.focus_force())
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.geometry("3440x1440")
        self.title("3D SPHERICAL PATTERN WIZARD")

        #SET START FREQUENCY
        self.fStart = ctk.CTkLabel(self, text="START FREQUENCY (GHz)", font=("Arial", 16), text_color="white")
        self.fStart.grid(row=0, column=0, padx=10, pady=10)

        self.efStart = ctk.CTkEntry(self, placeholder_text="DEFAULT = 1GHz")
        self.efStart.grid(row=0, column=1, padx=10, pady=10)

        self.start_result = ctk.CTkLabel(self, text="")
        self.start_result.grid(row=0, column=2, padx=10, pady=10)

        #SET STOP FREQUENCY
        self.fStop = ctk.CTkLabel(self, text="STOP FREQUENCY (GHz)", font=("Arial", 16), text_color="white")
        self.fStop.grid(row=1, column=0, padx=10, pady=10)

        self.efStop = ctk.CTkEntry(self, placeholder_text="DEFAULT = 20GHz")
        self.efStop.grid(row=1, column=1, padx=10, pady=10)

        self.stop_result = ctk.CTkLabel(self, text="")
        self.stop_result.grid(row=1, column=2, padx=10, pady=10)

        #SET IF BANDWIDTH
        self.IFB = ctk.CTkLabel(self, text='IF BANDWIDTH', font=("Arial", 16), text_color='white')
        self.IFB.grid(row=2, column=0, padx=10, pady=10)

        self.eIFB = ctk.CTkEntry(self, placeholder_text="enter IFB")
        self.eIFB.grid(row=2, column=1, padx=10, pady=10)

        self.IFB_result = ctk.CTkLabel(self, text="")
        self.IFB_result.grid(row=2, column=2, padx=10, pady=10)

        #SET STEP SIZE
        self.fStep = ctk.CTkLabel(self, text="STEP SIZE (GHz)", font=("Arial", 16), text_color="white")
        self.fStep.grid(row=3, column=0, padx=10, pady=10)

        self.efStep = ctk.CTkEntry(self, placeholder_text="DEFAULT = 1GHz")
        self.efStep.grid(row=3, column=1, padx=10, pady=10)

        self.step_result = ctk.CTkLabel(self, text="")
        self.step_result.grid(row=3, column=2, padx=10, pady=10)

        #SET THETA RESOLUTION
        self.thetaStep = ctk.CTkLabel(self, text="STEP SIZE - THETA (degrees)", font=("Arial", 16), text_color="white")
        self.thetaStep.grid(row=4, column=0, padx=10, pady=10)

        self.eTheta = ctk.CTkEntry(self, placeholder_text="DEFAULT = 1")
        self.eTheta.grid(row=4, column=1, padx=10, pady=10)

        self.theta_result = ctk.CTkLabel(self, text="")
        self.theta_result.grid(row=4, column=2, padx=10, pady=10)

        # SET PHI RESOLUTION
        self.phiStep = ctk.CTkLabel(self, text="STEP SIZE - PHI (degrees)", font=("Arial", 16), text_color="white")
        self.phiStep.grid(row=5, column=0, padx=10, pady=10)

        self.ePhi = ctk.CTkEntry(self, placeholder_text="DEFAULT = 1")
        self.ePhi.grid(row=5, column=1, padx=10, pady=10)

        self.phi_result = ctk.CTkLabel(self, text="")
        self.phi_result.grid(row=5, column=2, padx=10, pady=10)

        # CSV FILE NAME
        self.pathLabel = ctk.CTkLabel(self, text="OUTPUT CSV FILE NAME", font=("Arial", 16), text_color='white')
        self.pathLabel.grid(row=6, column =0, padx=10, pady=10)

        self.ePath = ctk.CTkEntry(self, placeholder_text='OUTPUT NAME')
        self.ePath.grid(row=6, column=1, padx=10, pady=10)

        self.path_result = ctk.CTkLabel(self, text="")
        self.path_result.grid(row=6, column=2, padx=10, pady=10)

        #BEGIN BUTTON
        self.begin_button = ctk.CTkButton(self, text="BEGIN", command=self.start_process)
        self.begin_button.grid(row=7, column=0, padx=10, pady=10)

        #KILL BUTTON
        self.kill_button = ctk.CTkButton(self, text='PANIC ABORT', command=self.kill)
        self.kill_button.grid(row=8, column=3, padx=10, pady=10)

        # DELETE WINDOW
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # TEXTBOX
        self.textbox = ctk.CTkTextbox(self, height=500, width=500, wrap="word")
        self.textbox.grid(row=0, column=4, padx=10, pady=10)

        #close button
        self.close_button = ctk.CTkButton(self, text='close', command=self.close)
        self.close_button.grid(row=9, column=4, padx=1, pady=1)

        self.abort_flag = threading.Event()
        self.process_thread = None

        self.kill_task = threading.Event()

    def start_process(self):
        global thread
        self.kill_task.clear()
        thread = threading.Thread(target=self.begin, daemon=True)
        thread.start()

    def read_steps(self):
        try:
            self.start = str(self.efStart.get())
            self.start_result.configure(text="START: " + self.start)
        except ValueError:
            self.start_result.configure(text="PLEASE ENTER A FLOATING POINT NUMBER")
            return
            # STOP VALUE
        try:
            self.stop = str(self.efStop.get())
            self.stop_result.configure(text="STOP: " + self.stop)
        except ValueError:
            self.stop_result.configure(text="PLEASE ENTER A FLOATING POINT NUMBER")
            return
            # STEP VALUE
        try:
            self.step = self.efStep.get()
            self.step_result.configure(text="STEP: " + str(self.step))
        except ValueError:
            self.step_result.configure(text="PLEASE ENTER A FLOATING POINT NUMBER")
            return
            # THETA VALUE
        try:
            self.theta = int(self.eTheta.get())
            self.theta_result.configure(text="THETA: " + str(self.theta))
        except ValueError:
            self.theta_result.configure(text="PLEASE ENTER A DECIMAL NUMBER")
            return
            # PHI VALUE
        try:
            self.phi = int(self.ePhi.get())
            self.phi_result.configure(text="PHI: " + str(self.phi))
        except ValueError:
            self.phi_result.configure(text="PLEASE ENTER A DECIMAL NUMBER")
            return
            # PATH
        try:
            self.path = str(self.ePath.get())
            self.path_result.configure(text="OUTPUT FILE NAME: " + str(self.path))
        except ValueError:
            self.path_result.configure(text="ENTER A PROPER PATH NAME")
            return
            # IF Bandwidth
        try:
            self.IFbandwidth = str(self.eIFB.get())
            self.IFB_result.configure(text="IF Bandwidth: " + self.IFbandwidth)
        except ValueError:
            self.IFB_result.configure(text="PLEASE ENTER A FLOATING POINT NUMBER")
            return

        # self.connect_to_controller()
        # time.sleep(0.1)
        # self.connect_to_vna()
        # time.sleep(0.1)
        # self.VNAwrite("STAR " + str(start) + "GHZ")
        # time.sleep(0.1)
        # self.VNAwrite("STOP " + str(stop) + "GHZ")
        # time.sleep(0.1)
        # self.VNAwrite("STEPSWP ON")
        # time.sleep(0.1)
        # # self.VNAwrite("IFBW " + str(self.IFbandwidth) + "HZ")
        # self.VNAwrite("STEP " + str(step))
        # time.sleep(0.1)
        #
        # for i in range(0, 300):
        #     if self.kill_task.is_set():
        #         print("ABORTED")
        #         return
        #     self.update_textbox("This is loop " + str(i))
        #     time.sleep(1)

        # for i in range(1, 361):
        # self.move_to_position(x=0, y=i)
        # time.sleep(3)
    def begin(self):
        self.read_steps()
        self.connect_to_controller()
        self.connect_to_vna()
        time.sleep(0.1)
        file_name = self.path

        with open(file=file_name, mode='w', newline='') as file:
            writer=csv.writer(file)
            writer.writerow(['Phi (degrees)', 'Theta (degrees)', 'Frequency (GHz)', 'S21 Magnitude (dB)'])
            self.move_to_position(x=0, y=0)
            time.sleep(20)
            phi_steps = 360 // self.phi + 1
            theta_steps = 90 // self.theta + 1

            for phi in range(phi_steps):
                current_position = self.get_position()
                self.update_textbox("MOVING TO POSITION: " + str(current_position[0]) + ", " + str(current_position[1] + self.phi))
                self.move_to_position(x=current_position[0], y=current_position[1] + self.phi)
                time.sleep(1)
                for theta in range(theta_steps):
                    current_position_1 = self.get_position()
                    self.update_textbox("MOVING TO POSITION: " + str(self.theta) + ", " + str(phi))
                    self.move_to_position(x=current_position_1[0] + self.theta, y=current_position_1[1])
                    time.sleep(1)
                    freqs=self.get_freq()
                    mags=self.get_mag()
                    for index in range(len(freqs)):
                        row = [current_position_1[1], current_position_1[0] + self.theta, freqs[index], mags[index]]
                        writer.writerow(row)
                    if theta == 89:
                        self.move_to_position(x=0, y=current_position_1)
                        time.sleep(20)




    def VNAwrite(self, msg):
        self.VNA.write(str(msg))

    def VNAread(self):
        return self.VNA.read()

    def VNAquery(self, msg):
        return self.VNA.query(str(msg) + "?")

    def connect_to_controller(self):
        try:

            self.serial_connection = serial.Serial(settings.COM_PORT, settings.BAUD_RATE, timeout=2)
            time.sleep(0.5)
            self.serial_connection.write(b'?')
            response = self.serial_connection.readline().decode('utf-8').strip()

            if response.startswith('<Idle|WPos:'):
                values = response.split(':')[1].split(',')
                if len(values) == 6:
                    x, y, z, a, b, c = values
                    self.update_textbox(f"Connected. Position at connection time is X{x} Y{y} A{a}\n")
                    #self.connect_button.configure(text='Connected', state=tk.DISABLED)

                else:
                    self.update_textbox("Invalid response format.")
            else:
                self.update_textbox("Failed to connect: Invalid response.")
        except serial.SerialException as e:
            self.update_textbox(f"Failed to connect: {str(e)}")

    def connect_to_vna(self):
        try:
            self.rm = pyvisa.ResourceManager()
            self.VNA = self.rm.open_resource("GPIB0::16::INSTR")
            self.update_textbox(self.VNA.query("*IDN?"))
        except pyvisa.VisaIOError:
            self.update_textbox("FAILED TO CONNECT TO VNA")

    def initialize_vna(self):
        self.VNA.write("S21")
        time.sleep(0.5)
        self.VNA.write("STAR " + str(self.start) + "GHZ")
        time.sleep(0.5)
        self.VNA.write("STOP " + str(self.stop) + "GHZ")
        time.sleep(0.5)
        self.VNA.write("STPSIZE " + str(self.step) + "HZ")
        time.sleep(0.5)
        self.VNA.write("IFBW "+ str(self.IFB_result) +"HZ")
        time.sleep(0.5)

    def move_to_position(self, x, y):
        self.serial_connection.write(f'G0 X{x} Y{y} Z0\n'.encode('utf-8'))  # Include default Z value




    def home(self):
        self.serial_connection.write(('$H\n').encode('utf-8'))

    def kill(self):
        self.serial_connection.close()
        self.VNA.close()
        self.update_textbox("PROCESS PANIC ABORTED")
        self.kill_task.set()

    def on_close(self):
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            print("Serial connection closed.")
        if self.VNA:
            self.VNA.close()
            print("VNA disconnected")

        self.destroy()

    def update_textbox(self, text):
        #self.textbox.delete("1.0", "end")  # Clear previous text
        #self.textbox.insert("end", text)  # Insert new text
        self.textbox.after(0, self.safe_update_textbox, text)

    def safe_update_textbox(self, text):
        if self.textbox.winfo_exists():
            self.textbox.delete("1.0", "end")  # Clear previous text
            self.textbox.insert("end", text)  # Insert new text

    def read_sparameters(self):
        return self.VNA.query("*IDN?")

    def close(self):
        self.destroy()

    def get_mag(self, chan="CHAN1"):
        """Returns a numpy array with the logarithmic magnitude values
        on the channel specified.

        Args:
            chan (str): String specifying the channel to get the values from
        """
        self.VNAwrite("FORM5;")  # Use binary format to output data
        self.VNAwrite(chan + ";")  # Select channel
        self.VNAwrite("LOGM;")  # Show logm values - TRY CALC:MEAS:FORM MLOG and CALC:MEAS:FORM PHAS
        # Might let you switch between the log mag and phase measurements. Should wrap this whole thing up ez pz!
        res = []



        aux = self.VNA.query_binary_values(
            "OUTPFORM;", container=tuple, header_fmt="hp"
        )  # Ask for the values from channel and format them as tuple
        for i in range(
                0, len(aux), 2
        ):  # Only get the first value of every data pair because the other is zero
            res.append(aux[i])
        return np.asarray(res)

    def get_freq(self):
        """Returns a numpy array with the values of frequency
        from the x-axis.
        """
        self.VNAwrite(
            "OUTPLIML;"
        )  # Asks for the limit test results to extract the stimulus components
        aux = []
        x = self.VNAread().split("\n")  # Split the string for each point



        for i in x:
            if i == "":
                break
            aux.append(
                float(i.split(",")[0])
            )  # Split each string and get only the first value as a float number
        return np.asarray(aux)

    def get_position(self):
        try:
            self.serial_connection.flushInput()
            self.serial_connection.write(('?').encode('utf-8'))
            time.sleep(0.1)
            response = self.serial_connection.readline().decode('utf-8').strip()

            if '<Idle|WPos:' in response:
                try:
                    values = response.split('|')[1].split(':')[1].split(',')
                    x, y, z, a = float(values[0]), float(values[1]), float(values[2]), float(values[3])
                    self.update_textbox(f"Current Position: X{x} Y{y} A{a}")
                    return float(x), float(y), float(a)
                except (IndexError, ValueError):
                    self.update_textbox("Invalid response format for position.")
                    return None, None, None
            else:
                self.update_textbox("Failed. Was the RESULTS file opened?")
                return None, None, None
        except serial.SerialException as e:
            self.update_textbox(f"Error in getting position: {str(e)}")
            return None, None, None



class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        #self.attributes("-fullscreen", True)

        self.geometry("3440x1440")
        self.title("ANTENNA TEST RANGE CONTROLLER ---- DEPARTMENT OF ELECTRONICS")
        self.attributes('-fullscreen', True)
        #BANNER IMAGE
        image_path = "Carleton_Logo.png"
        image = Image.open(image_path)
        self.ctk_image = ctk.CTkImage(light_image=image, size=(300, 200))
        self.label = ctk.CTkLabel(self, image=self.ctk_image, text="")
        self.label.grid(row=0, column=2, padx=10, pady=10)

        #VNA SOFT FRONT PANEL
        self.control_vna_button = ctk.CTkButton(self, text="VNA SOFT PANEL", command=self.SFP)
        self.control_vna_button.grid(row=1, column=0, padx=10, pady=10)

        #POSITIONER MANUAL CONTROL
        self.control_positioner = ctk.CTkButton(self, text="MANUAL POSITIONER CONTROL", command=self.positioner_manual_control)
        self.control_positioner.grid(row=1, column=2, padx=10, pady=10)

        #3d spherical pattern generation
        self.spherical_pattern = ctk.CTkButton(self, text="3D SPHERICAL PATTERN", command=self.three_d_spherical_pattern)
        self.spherical_pattern.grid(row=2, column=0, padx=10, pady=10)

        #TEXT BOX
        self.textbox = ctk.CTkTextbox(self, height=600, width=1500, wrap="word")
        self.textbox.grid(row=3, column=0, padx=10, pady=10)

        #close button
        self.close_button = ctk.CTkButton(self, text="CLOSE", command=self.close)
        self.close_button.grid(row=4, column=2, padx=10, pady=10)

    def SFP(self):
        sfp = SFP(self)

    def positioner_manual_control(self):
        manual_control_app = manual_control_App(self)

    def update_textbox(self, text):
        """Updates the textbox with new text."""
        self.textbox.delete("1.0", "end")  # Clear previous text
        self.textbox.insert("end", text)  # Insert new text

    def three_d_spherical_pattern(self):
        threeD = threeDpat(self)

    def close(self):
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()