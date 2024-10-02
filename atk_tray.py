import sys
import os
import logging
import time
import threading
from dataclasses import dataclass

import hid
from PIL import Image, ImageDraw, ImageFont
import wx
from wx.adv import TaskBarIcon

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


@dataclass
class MouseClass:
    model: str
    vid: int
    pid_wireless: int
    pid_wired: int
    usage_page: int
    usage: int


atk_f1_ultimate = MouseClass(model="ATK F1 Ultimate", vid=0x373B, pid_wireless=0x1031, pid_wired=0x102E, usage_page=0xFF02, usage=0x0002)
vxe_r1_pro_max = MouseClass(model="VXE R1 Pro Max", vid=0x3554, pid_wireless=0xF58A, pid_wired=0xF58C, usage_page=0xFF02, usage=0x0002)
vxe_r1_se_plus = MouseClass(model="VXE R1 SE+", vid=0x3554, pid_wireless=0xF58E, pid_wired=0xF58F, usage_page=0xFF02, usage=0x0002)
vgn_f1_pro = MouseClass(model="VGN F1 Pro", vid=0x3554, pid_wireless=0xF503, pid_wired=0xF502, usage_page=0xFF02, usage=0x0002)

mouse = vxe_r1_pro_max


def get_resource(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_battery(mouse: MouseClass):
    device = hid.device()
    try:
        device_path = get_device_path(mouse.vid, mouse.pid_wireless, mouse.pid_wired, mouse.usage_page, mouse.usage)
    except RuntimeError:
        return None
    device.open_path(device_path)
    report = [0] * 17
    report[0] = 8  # Report ID
    report[1] = 4
    report[16] = 73
    logging.info(f"Sending report:  {report}")
    device.write(report)
    time.sleep(0.1)
    res = device.read(17)
    logging.info(f"Recieved report: {res}")
    device.close()
    battery = res[6]
    wired = res[7]
    logging.info(f"Battery: {battery}")
    return battery, wired


def get_device_path(vid, pid_wireless, pid_wired, usage_page, usage):
    device_list = hid.enumerate(vid, pid_wireless)
    if not device_list:
        device_list = hid.enumerate(vid, pid_wired)
        if not device_list:
            raise RuntimeError(f"The specified device ({vid:X}:{pid_wireless:X} or {vid:X}:{pid_wired:X}) cannot be found.")
    for device in device_list:
        if device['usage_page'] == usage_page and device['usage'] == usage:
            return device['path']


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
        item_exit = wx.MenuItem(menu, wx.ID_ANY, "Exit")
        self.Bind(wx.EVT_MENU, self.OnTaskBarExit, id=item_exit.GetId())
        # menu.Append(item_settings)
        menu.Append(item_exit)
        return menu

    def OnTaskBarActivate(self, event):
        if not self.frame.IsShown():
            self.frame.Show()

    def OnTaskBarExit(self, event):
        self.Destroy()
        self.frame.Destroy()

    def OnClick(self, event):
        if self.frame.battery_str == "Zzz" or self.frame.battery_str == "-":
            self.frame.show_battery()


class MyFrame(wx.Frame):

    def __init__(self, parent, title):
        super().__init__(parent, title=title, pos=(-1, -1), size=(290, 280))
        self.SetSize((350, 250))
        self.tray_icon = MyTaskBarIcon(self)
        self.tray_icon.SetIcon(create_icon(" ", foreground_color, font), "")
        self.battery_str = ""
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Centre()

        self.animation_thread = threading.Thread(target=self.charge_animation, daemon=True)
        self.thread = threading.Thread(target=self.thread_worker, daemon=True)
        self.thread.start()

    def OnClose(self, event):
        if self.IsShown():
            self.Hide()

    def thread_worker(self):
        while True:
            self.show_battery()
            if self.battery_str == "-" or self.wired:
                time.sleep(1)
            else:
                time.sleep(poll_rate)

    def show_battery(self):
        result = get_battery(mouse)

        if result is None:
            self.stop_animation = True
            self.battery_str = "-"
            if self.animation_thread.is_alive():
                self.animation_thread.join()
            self.tray_icon.SetIcon(create_icon(self.battery_str, foreground_color, font), "No Mouse Detected")
            return

        battery, wired = result
        self.battery_str = str(battery)
        self.wired = wired

        if wired and battery < 100:
            self.stop_animation = False
            if not self.animation_thread.is_alive():
                self.animation_thread.start()
            return

        if battery == 100 and wired:
            self.stop_animation = True
            if self.animation_thread.is_alive():
                self.animation_thread.join()
            self.tray_icon.SetIcon(wx.Icon(get_resource(R".\icons\battery_100_green.ico")), mouse.model)
            return

        if battery == 100 and not wired:
            self.stop_animation = True
            self.battery_str = str(battery)
            if self.animation_thread.is_alive():
                self.animation_thread.join()
            self.tray_icon.SetIcon(wx.Icon(get_resource(R".\icons\battery_100.ico")), mouse.model)
            return

        self.stop_animation = True
        if self.animation_thread.is_alive():
            self.animation_thread.join()
        self.tray_icon.SetIcon(create_icon(self.battery_str, foreground_color, font), mouse.model)

    def charge_animation(self):
        while not self.stop_animation:
            self.tray_icon.SetIcon(wx.Icon(get_resource(R".\icons\battery_0.ico")), mouse.model)
            time.sleep(0.5)
            self.tray_icon.SetIcon(wx.Icon(get_resource(R".\icons\battery_50.ico")), mouse.model)
            time.sleep(0.5)
            self.tray_icon.SetIcon(wx.Icon(get_resource(R".\icons\battery_100.ico")), mouse.model)
            time.sleep(0.5)


class MyApp(wx.App):

    def OnInit(self):
        frame = MyFrame(None, title='ATK Tray settings')
        frame.Show(False)
        self.SetTopWindow(frame)
        return True


def main():
    app = MyApp()
    app.MainLoop()


if __name__ == "__main__":
    main()
