from ui.main_app import MainApp
"""
Entry point for the antenna test range GUI application.

This script initializes and starts the main GUI event loop by instantiating
the `MainApp` class defined in `ui.main_app`.

Usage:
    Run this script directly to launch the application:
    $ python main.py
"""
if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
