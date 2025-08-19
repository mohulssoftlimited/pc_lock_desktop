import sys, requests, shutil, os, csv, datetime, re, threading, json, random, os, platform
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QMessageBox, QFileDialog,
QListWidgetItem, QPushButton, QHBoxLayout, QWidget, QTableWidgetItem, QInputDialog,
QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QStyledItemDelegate)


from ui.main import Ui_MainWindow  # Import the generated Ui_MainWindow class
from ui.timer_window import Ui_TimerWindow


from auth.token_manager import TokenManager  # Import the TokenManager class
from PyQt6.QtCore import QTimer, QTime, QDateTime, QSize, Qt, QSystemSemaphore, QFile, QIODevice, qInstallMessageHandler, QUrl
from PyQt6.QtGui import QCursor, QStandardItem, QStandardItemModel, QFont, QIntValidator, QDoubleValidator, QIcon, QPixmap, QImage, QPainter, QPen, QBrush, QColor
from bs4 import BeautifulSoup
from configparser import ConfigParser
from PyQt6.QtGui import QBrush, QColor, QDesktopServices

# import worker class
import traceback
import resources_rc

# Gmail JSON API

def get_crash_log_path():
    """
    Get the crash log file path in the AppData directory.
    """
    appdata_dir = os.getenv('APPDATA', os.path.expanduser('~\\AppData\\Roaming'))
    crash_log_dir = os.path.join(appdata_dir, "MailBlade")
    os.makedirs(crash_log_dir, exist_ok=True)  # Ensure the directory exists
    return os.path.join(crash_log_dir, "crash.log")

def log_exception(exc_type, exc_value, exc_traceback):
    """
    Log unhandled exceptions to a crash log file.
    """
    crash_log_path = get_crash_log_path()
    with open(crash_log_path, "a") as log_file:
        log_file.write("Unhandled Exception:\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=log_file)
    print(f"Crash log written to: {crash_log_path}")

def qt_message_handler(mode, context, message):
    """
    Custom handler for Qt messages to log them.
    """
    crash_log_path = get_crash_log_path()
    with open(crash_log_path, "a") as log_file:
        log_file.write(f"Qt Message ({mode}): {message}\n")


class TimerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = Ui_TimerWindow()  # Instantiate the UI class
        self.ui.setupUi(self)  # Set up the UI on this QWidget
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        
        
        # Variable to track mouse position for dragging
        self.old_pos = None

        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        
    def update_timer_label(self, time_text):
        self.ui.TimerWindowLabel.setText(time_text)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
    
    def mouseMoveEvent(self, event):
        if self.old_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None  # Reset when the mouse is released

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # Set up the UI
        
        self.app_version = "PC Lock V1.0"  # Define your application version
        self.setWindowTitle(self.app_version)  # Set the window title
        # self.check_for_updates()  # Chec
        
        ###################################
        # Active menu style
        ###################################
        
        ### sidebar page changes
        self.default_style = """
            color: white;
            text-align: left;
            padding-left: 18px;
            border: none;
        """
        self.active_style = """
            color: white;
            background-color: rgb(56, 64, 70);
            text-align: left;
            padding-left: 18px;
            border-left: 7px solid rgb(0, 170, 255);
            border: none;
        """

        ### sidebar page changes end
        
        
        ###################################
        # Active menu style end
        ###################################
        
        
        ### authentication
        self.token_manager = TokenManager()  # Create an instance of TokenManager
        self.load_tokens_on_startup() # load tokens on startup
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.periodic_refresh_token)
        self.refresh_timer.start(60000 * 45)  # Check every 30 minutes
        
        # login
        self.loginButton.clicked.connect(self.get_token)

        ### Logout
        self.actionLogout.triggered.connect(self.confirm_logout)
        self.sidebarLogoutButton.clicked.connect(self.confirm_logout)
        ### Authentication end
        
        ### Exit application
        self.actionExit.triggered.connect(self.confirm_exit)
        
        
        # Connect the button click event
        self.TimerWindowButton.clicked.connect(self.open_timer_window)
        self.DimTimerWindow.clicked.connect(self.dim_timer_window)
        
        self.timer_window = None  # Initialize as None
        
        
        self.end_at = None  # Store last known end time
        self.status = None  # Store last known status
        self.was_running = False  # Track if the timer was running before

        # Timer to update countdown every second
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)  # Update every second

        # Timer to fetch API data every 10 seconds
        self.api_timer = QTimer(self)
        self.api_timer.timeout.connect(self.fetch_timer_from_api)
        self.api_timer.start(10000)  # Fetch API every 10 seconds


        
        # timer reset
        self.ResetTimerButton.clicked.connect(self.reset_timer)


    

    def fetch_timer_from_api(self):
        from datetime import datetime, timezone
        tokens = self.token_manager.load_tokens()
        if not tokens or "access" not in tokens:
            self.MainTimerCounter.setText("Not Set")
            return

        headers = {"Authorization": f"Bearer {tokens['access']}"}

        try:
            response = requests.get("https://sync.swingtheory.golf/account/api/check_info/", headers=headers)
            response.raise_for_status()
            data = response.json()

            new_status = data.get("status", "")
            new_end_at = data.get("end_at")

            # Handle cases when is_running is False
            if not data["is_running"]:
                if new_status == "ended":
                    new_time_text = "Ended"
                elif new_status == "paused":
                    new_time_text = "Paused"
                else:
                    new_time_text = "Not Set"

                # **Only lock PC if it was previously running**
                if self.was_running and new_status == "ended":
                    
                    response = requests.post("https://sync.swingtheory.golf/account/api/time_request/", headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    
                    self.lock_windows_pc()

                # If status changed, update UI
                if self.status != new_status:
                    self.MainTimerCounter.setText(new_time_text)
                    if self.timer_window is not None:
                        self.timer_window.update_timer_label(new_time_text)

                self.status = new_status
                self.end_at = None  # Stop countdown
                self.was_running = False  # Reset running state
                return

            # If running and end_at has changed, update the timer
            if new_end_at and new_end_at != self.end_at:
                self.end_at = datetime.fromisoformat(new_end_at.replace("Z", "+00:00"))
                self.status = "running"
                self.was_running = True  # Mark as running

        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch timer data: {e}")
            self.MainTimerCounter.setText("Error")

        
    
    def update_countdown(self):
        from datetime import datetime, timezone
        if self.end_at is None:
            return  # No active countdown

        current_time = datetime.now(timezone.utc)
        remaining_seconds = max(0, int((self.end_at - current_time).total_seconds()))  # Ensure non-negative

        if remaining_seconds == 0:
            self.MainTimerCounter.setText("Ended")
            if self.timer_window is not None:
                self.timer_window.update_timer_label("Ended")

            # **Lock Windows PC only if it was running**
            if self.was_running:
                tokens = self.token_manager.load_tokens()
                if not tokens or "access" not in tokens:
                    self.MainTimerCounter.setText("Not Set")
                    return

                headers = {"Authorization": f"Bearer {tokens['access']}"}
            
                response = requests.post("https://sync.swingtheory.golf/account/api/time_request/", headers=headers)
                response.raise_for_status()
                data = response.json()
                
                
                self.lock_windows_pc()
                # print("Lockedddd!!!!")

            self.end_at = None  # Stop countdown
            self.was_running = False  # Reset running flag
            return

        # Format as HH:MM:SS
        hours, remainder = divmod(remaining_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_text = f"{hours:02}:{minutes:02}:{seconds:02}"

        # Update UI
        self.MainTimerCounter.setText(time_text)
        if self.timer_window is not None:
            self.timer_window.update_timer_label(time_text)

    def lock_windows_pc(self):
        if platform.system() == "Windows":
            self.was_running = False
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

    
    def reset_timer(self):
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "Do you really want to reset the timer?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            tokens = self.token_manager.load_tokens()
            if not tokens or "access" not in tokens:
                QMessageBox.warning(self, "Authentication Error", "You need to log in first.")
                return

            headers = {"Authorization": f"Bearer {tokens['access']}"}

            try:
                response = requests.post("https://sync.swingtheory.golf/account/api/time_request/", headers=headers)
                response.raise_for_status()

                QMessageBox.information(self, "Success", "Timer reset successfully!")

                # Immediately fetch new timer data from the API after reset
                self.fetch_timer_from_api()

            except requests.exceptions.RequestException as e:
                QMessageBox.critical(self, "Error", f"Failed to reset timer: {e}")


    def open_timer_window(self):
        if self.timer_window is None:  # Ensure only one instance is created
            self.timer_window = TimerWindow()
            self.timer_window.show()
        else:
            self.timer_window.close()  # Close if already open
            self.timer_window = None
    
    def dim_timer_window(self):
        if self.timer_window is not None:  # Ensure window is open
            self.timer_window.setWindowOpacity(0.6)  # Set transparency to 50%
    
    
    def update_timer(self):
        """ Updates the countdown timer in MainTimerCounter and TimerWindowLabel """
        remaining_time = self.end_time.toSecsSinceEpoch() - QDateTime.currentDateTime().toSecsSinceEpoch()
        if remaining_time <= 0:
            time_text = "00:00:00"
            self.timer.stop()
            if platform.system() == "Windows":
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            
        else:
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            seconds = remaining_time % 60
            time_text = f"Ending in: {hours:02}:{minutes:02}:{seconds:02}"

        # Update Main Window label
        self.MainTimerCounter.setText(time_text)

        # Update Timer Window label if it's open
        if self.timer_window is not None:
            self.timer_window.update_timer_label(time_text)

    ### Authentication
    def get_token(self):
        username = self.login_email_input.text()
        password = self.login_password_input.text()
        if not username or not password:
            QMessageBox.warning(self, "Input Error", "Please enter both username and password.")
            return

        # Call the API to get tokens
        self.loginButton.setText("Logging In...")

        try:
            response = requests.post("https://sync.swingtheory.golf/api/token/", data={"username": username, "password": password})
            response.raise_for_status()
            tokens = response.json()
            self.token_manager.save_tokens(tokens)
            
            # Show user info to UI
            self.greet_label.setText(f"Welcome, {tokens['user_info']['username']}!")
            # set action menu text
            self.menuMy_Account.setTitle(f"My Account ({tokens['user_info']['username']})")
            QMessageBox.information(self, "Success", "Login successful")
            self.login_email_input.clear()
            self.login_password_input.clear()
            
            # go to stackwidget index 1
            self.stackedWidgetScreens.setCurrentIndex(1)
            
        except requests.exceptions.RequestException as e:
            self.login_password_input.clear()
            QMessageBox.critical(self, "Error", f"Invalid Email or Password.")
        
        self.loginButton.setText("Login")
    
    def load_tokens_on_startup(self):
        tokens = self.token_manager.load_tokens()
        print(tokens)
        if tokens and "access" in tokens:
            # Validate the token using the verify endpoint
            user_info = self.token_manager.verify_token(tokens["access"])
            if user_info:
                self.greet_label.setText(f"Welcome, {tokens['user_info']['username']}!")
                self.menuMy_Account.setTitle(f"My Account ({user_info['user_info']['username']})")
                self.stackedWidgetScreens.setCurrentIndex(1)  # Home screen
            else:
                # try refreshing the token
                new_tokens = self.token_manager.refresh_tokens(tokens["refresh"])
                if new_tokens:
                    # self.userGreetingsLabel.setText(f"{new_tokens['user_info']['greeting']}")
                    self.menuMy_Account.setTitle(f"My Account ({new_tokens['user_info']['username']})")
                    self.token_manager.save_tokens(new_tokens)
                    self.stackedWidgetScreens.setCurrentIndex(1)  # Home screen
                else:
                    self.stackedWidgetScreens.setCurrentIndex(2)  # Login screen
        else:
            self.stackedWidgetScreens.setCurrentIndex(2)  # Login screen
    
    def periodic_refresh_token(self):
        tokens = self.token_manager.load_tokens()
        if not tokens or "refresh" not in tokens:
            self.stackedWidgetScreens.setCurrentIndex(2)  # Login screen
            return

        # Validate the access token first
        if not self.token_manager.verify_token(tokens["access"]):
            # If access token is invalid, refresh the tokens
            new_tokens = self.token_manager.refresh_tokens(tokens["refresh"])
            if new_tokens:
                self.greet_label.setText(f"Welcome, {tokens['user_info']['username']}!")
                self.menuMy_Account.setTitle(f"My Account ({new_tokens['user_info']['username']})")
                self.token_manager.save_tokens(new_tokens)
            else:
                QMessageBox.warning(self, "Session Expired", "Please log in again.")
                self.stackedWidgetScreens.setCurrentIndex(2)  # Login scree
    
    ### Logout
    def confirm_logout(self):
        reply = QMessageBox.question(
            self,
            "Confirm Logout",
            "Are you sure you want to logout?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.token_manager.clear_tokens()  # Physically remove the token file
            self.stackedWidgetScreens.setCurrentIndex(2)  # Redirect to login/error page
    
    ### Exit application
    def confirm_exit(self):
        """Confirm exit"""
        reply = QMessageBox.question(self, 'Exit', 'Are you sure you want to exit?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            sys.exit()
        else:
            pass
    
    def closeEvent(self, event):
        # Show a warning box
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Do you really want to close?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            event.accept()  # Allow the window to close
        else:
            event.ignore()  # Prevent the window from closing
            

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Set up global exception and Qt message handlers
    sys.excepthook = log_exception
    qInstallMessageHandler(qt_message_handler)

    # Initialize and show the main window
    window = MainWindow()

    # Show the main window
    window.show()

    # Execute the application
    sys.exit(app.exec())