import ctypes
import logging
import os
import sys
import threading
import time
import winreg
from datetime import datetime, timedelta

import hid
import wx
from PIL import Image, ImageDraw, ImageFont
from wx.adv import NotificationMessage, TaskBarIcon

import models

ctypes.windll.shcore.SetProcessDpiAwareness(2)
logging.basicConfig(level=logging.INFO)

# Colors
RED = (255, 0, 0)
GREEN = (71, 255, 12)
BLUE = (91, 184, 255)
YELLOW = (255, 255, 0)

# Settings
poll_rate = 60
foreground_color = BLUE
background_color = (0, 0, 0, 0)
font = "consola.ttf"


def get_resource(relative_path):
    if hasattr(sys, "_MEIPASS"):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, relative_path)


def save_reg(data) -> None:
    soft = winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, "SOFTWARE")
    key = winreg.CreateKey(soft, "ATK_Tray")
    winreg.SetValueEx(key, "FullchargeDate", 0, winreg.REG_SZ, data)
    if key:
        winreg.CloseKey(key)


def get_reg(name, reg_path):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ)
        value = winreg.QueryValueEx(key, name)[0]
        winreg.CloseKey(key)
        return datetime.strptime(value, "%d.%m.%Y %H:%M:%S")
    except WindowsError:
        return None


def format_timedelta(delta: timedelta) -> str:
    """Format timedelta to string like '1 days, 23:59:59'"""
    days = delta.days
    total_seconds = int(delta.total_seconds()) - days * 86400  # 86400 seconds in one day
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days} days, {hours:02d}:{minutes:02d}:{seconds:02d}"


def detect_mouse():
    hid_devices: dict = hid.enumerate()
    for device in hid_devices:
        for mouse in models.atk_mice:
            if (
                device["vendor_id"] == mouse.vid
                and (device["product_id"] == mouse.pid_wireless or device["product_id"] == mouse.pid_wired)
                and device["usage_page"] == mouse.usage_page
                and device["usage"] == mouse.usage
            ):
                if device["product_id"] == mouse.pid_wireless:
                    mouse.wired = False
                else:
                    mouse.wired = True
                mouse.device_path = device["path"]
                logging.info(f"Detected model: {mouse.model}")
                return mouse


def get_battery(mouse: models.MouseClass):
    return models.get_battery(mouse)


def create_icon(text: str, color, font):
    def PIL2wx(image):
        """Convert PIL Image to wxPython Bitmap"""
        width, height = image.size
        return wx.Bitmap.FromBufferRGBA(width, height, image.tobytes())

    def get_text_pos_size(text):
        if len(text) == 3:
            return (0, 58), 150
        elif len(text) == 2:
            return (8, 32), 220
        elif len(text) == 1:
            return (70, 32), 220

    image = Image.new(mode="RGBA", size=(256, 256), color=background_color)
    # Call draw Method to add 2D graphics in an image
    I1 = ImageDraw.Draw(image)
    # Custom font style and font size
    text_pos, size = get_text_pos_size(text)
    myFont = ImageFont.truetype(font, size)
    # Add Text to an image
    I1.text(text_pos, text, font=myFont, fill=color)
    return PIL2wx(image)


class MyTaskBarIcon(TaskBarIcon):
    def __init__(self, frame):
        super().__init__()
        self.frame = frame
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.OnClick)

    def CreatePopupMenu(self):
        menu = wx.Menu()
        item_settings = wx.MenuItem(menu, wx.ID_ANY, "Settings")
        self.Bind(wx.EVT_MENU, self.OnTaskBarActivate, id=item_settings.GetId())
        item_reset_timer = wx.MenuItem(menu, wx.ID_ANY, "Reset timer")
        self.Bind(wx.EVT_MENU, self.OnResetTimer, id=item_reset_timer.GetId())
        item_exit = wx.MenuItem(menu, wx.ID_ANY, "Exit")
        self.Bind(wx.EVT_MENU, self.OnTaskBarExit, id=item_exit.GetId())
        # menu.Append(item_settings)
        menu.Append(item_reset_timer)
        menu.Append(item_exit)
        return menu

    def OnTaskBarActivate(self, event):
        if not self.frame.IsShown():
            self.frame.Show()

    def OnTaskBarExit(self, event):
        self.Destroy()
        self.frame.Destroy()

    def OnResetTimer(self, exent):
        self.frame.full_charge_date = datetime.now()
        save_reg(self.frame.full_charge_date.strftime("%d.%m.%Y %H:%M:%S"))
        logging.info(f"Reset full charge date to: {self.frame.full_charge_date}")

    def OnClick(self, event):
        if self.frame.battery_str == "Zzz" or self.frame.battery_str == "-":
            self.frame.show_battery()


class MyFrame(wx.Frame):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, pos=(-1, -1), size=(290, 280))
        self.SetSize((350, 250))
        self.tray_icon = MyTaskBarIcon(self)
        self.tray_icon.SetIcon(create_icon(" ", foreground_color, font), "")
        self.full_charge_date = get_reg("FullchargeDate", R"SOFTWARE\ATK_Tray")
        self.battery_str = ""
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Centre()

        self.icon_battery_0 = wx.Icon(get_resource(R"icons\battery_0.ico"))
        self.icon_battery_50 = wx.Icon(get_resource(R"icons\battery_50.ico"))
        self.icon_battery_100 = wx.Icon(get_resource(R"icons\battery_100.ico"))
        self.icon_battery_100_green = wx.Icon(get_resource(R"icons\battery_100_green.ico"))

        self.mouse = detect_mouse()

        self.notification = NotificationMessage(title=self.mouse.model, message="Charged 100%")
        self.notification.SetFlags(wx.ICON_INFORMATION)
        self.notification.UseTaskBarIcon(self.tray_icon)
        self.animation_thread = threading.Thread(target=self.charge_animation, daemon=True)
        self.thread = threading.Thread(target=self.thread_worker, daemon=True)
        self.thread.start()

    def get_tooltip(self):
        if self.full_charge_date:
            delta = datetime.now() - self.full_charge_date
            logging.info("Since last full charge: " + format_timedelta(delta))
            return self.mouse.model + f"\n{format_timedelta(delta)}"
        else:
            logging.info("No full charge date")
            return self.mouse.model

    def OnClose(self, event):
        if self.IsShown():
            self.Hide()

    def thread_worker(self):
        self.fullcharged = False
        while True:
            self.show_battery()
            if self.battery_str == "-" or self.wired:
                time.sleep(1)
            else:
                time.sleep(poll_rate)

    def show_battery(self):
        result = get_battery(self.mouse)

        if result is None:
            self.stop_animation = True
            self.battery_str = "-"
            if self.animation_thread.is_alive():
                self.animation_thread.join()
            self.tray_icon.SetIcon(create_icon(self.battery_str, foreground_color, font), "No Mouse Detected")
            return

        battery, wired = result
        self.wired = wired

        if battery is None:
            if wired:
                self.battery_str = ""
                self.fullcharged = False
                self.stop_animation = False
                if not self.animation_thread.is_alive():
                    self.animation_thread.start()
                return

            self.fullcharged = False
            self.stop_animation = True
            self.battery_str = "-"
            if self.animation_thread.is_alive():
                self.animation_thread.join()
            self.tray_icon.SetIcon(create_icon(self.battery_str, foreground_color, font), self.get_tooltip())
            return

        self.battery_str = str(battery)

        if wired and (battery < 100 or self.mouse.protocol == 2):
            self.fullcharged = False
            self.stop_animation = False
            if not self.animation_thread.is_alive():
                self.animation_thread.start()
            return

        if battery == 100 and wired:
            self.stop_animation = True
            if self.animation_thread.is_alive():
                self.animation_thread.join()
            self.tray_icon.SetIcon(self.icon_battery_100_green, self.get_tooltip())
            if not self.fullcharged:
                self.fullcharged = True
                self.notification.Show(timeout=wx.adv.NotificationMessage.Timeout_Auto)
            return

        if battery == 100 and not wired:
            if self.fullcharged:
                self.full_charge_date = datetime.now()
                save_reg(self.full_charge_date.strftime("%d.%m.%Y %H:%M:%S"))
                logging.info(f"Reset full charge date to: {self.full_charge_date}")
            self.fullcharged = False
            self.stop_animation = True
            self.battery_str = str(battery)
            if self.animation_thread.is_alive():
                self.animation_thread.join()
            self.tray_icon.SetIcon(self.icon_battery_100, self.get_tooltip())
            return

        self.fullcharged = False
        self.stop_animation = True
        if self.animation_thread.is_alive():
            self.animation_thread.join()
        self.tray_icon.SetIcon(create_icon(self.battery_str, foreground_color, font), self.get_tooltip())

    def charge_animation(self):
        while not self.stop_animation:
            self.tray_icon.SetIcon(self.icon_battery_0, self.get_tooltip())
            time.sleep(0.5)
            self.tray_icon.SetIcon(self.icon_battery_50, self.get_tooltip())
            time.sleep(0.5)
            self.tray_icon.SetIcon(self.icon_battery_100, self.get_tooltip())
            time.sleep(0.5)


class MyApp(wx.App):
    def OnInit(self):
        frame = MyFrame(None, title="ATK Tray settings")
        frame.Show(False)
        self.SetTopWindow(frame)
        return True


def main():
    app = MyApp()
    app.MainLoop()


if __name__ == "__main__":
    main()
