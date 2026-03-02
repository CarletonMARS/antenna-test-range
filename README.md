# antennaTestRange

**antennaTestRange** is a Python-based software suite developed by Miles Stillie and Alex Szabo as part of the [Metamaterials and Antenna Research Squad (MARS)](https://carleton.ca/mars/) at Carleton University. It enables automated spherical antenna measurement and visualization using a Vector Network Analyzer (VNA) and a dual-axis positioner.

This GUI-driven application allows users to configure, initiate, monitor, and store antenna radiation pattern data from spherical scans with real-time 3D visualization.

---

## Features

-  **Automated Spherical Scanning** -> Full 3D theta/phi sweep with VNA integration  
-  **Live 3D Radiation Plot** -> Realtime `matplotlib`-based spherical pattern preview  
-  **Abort Functionality** -> Safely stop measurements at any time  
-  **CSV Export** -> Automatic saving of data in standard format  
-  **GUI Interface** -> Intuitive controls built with `customtkinter`

---

## Requirements

- **Python** 3.10+
- **Dependencies:**

```bash
pip install customtkinter numpy matplotlib pyserial pandas
