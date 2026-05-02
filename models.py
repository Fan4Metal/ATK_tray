from dataclasses import dataclass
import logging
import time
from typing import Optional

import hid

__all__ = ["atk_mice", "MouseClass", "get_battery", "get_battery_1", "get_battery_2"]


@dataclass
class MouseClass:
    model: str
    vid: int
    pid_wireless: int
    pid_wired: int
    usage_page: int
    usage: int
    protocol: int
    device_path: Optional[str] = None
    wired: Optional[bool] = None


def get_battery_1(mouse: MouseClass):
    """Read battery state using the first ATK HID protocol.

    Protocol 1 uses a 17-byte feature/output report with report ID 0x08.
    The request sets byte 1 to 0x04 and byte 16 to 0x49, then reads a
    17-byte response. In the response byte 6 contains the battery level
    and byte 7 contains the connection flag, where a non-zero value means
    the mouse is connected over wire.
    
    Used for ATK F1 Ultimate, ATK A9 Ultimate, ATK Zero, VXE MAD R,
    VXE MAD R Major Plus, VXE R1 Pro Max, and VXE R1 SE+ on Nordic 52840 MCU.
    
    Returns:
        tuple[int, int]: Battery percentage and raw wired flag from the
        device response.
    """
    device = hid.device()
    try:
        device.open_path(mouse.device_path)
        report = [0] * 17
        report[0] = 8  # Report ID
        report[1] = 4
        report[16] = 73
        logging.info(f"Sending report:  {report}")
        device.write(report)
        time.sleep(0.1)

        res = device.read(17)
        logging.info(f"Received report: {res}")

        battery = res[6]
        wired = res[7]
        logging.info(f"Battery: {battery}, Wired: {bool(wired)}")
        return battery, wired
    finally:
        try:
            device.close()
        except Exception as e:
            logging.exception(e)


def get_battery_2(mouse: MouseClass):
    """Read battery state using the second ATK HID protocol.

    Protocol 2 uses a 64-byte report with report ID 0x08 and command
    marker 0x72. The request differs by connection type: wired devices use
    byte 1 = 0x7C and byte 5 = 0x00, while wireless devices use byte 1 =
    0x7D and byte 5 = 0x01. Common request bytes are byte 2 = 0x72, byte 3
    = 0x02, byte 4 = 0x00, byte 6 = 0x07, and byte 7 = 0x01.

    A valid response is expected to contain byte 1 = 0x72 and byte 5 =
    0x07. Wireless responses report the battery level in byte 7. Wired
    protocol 2 responses do not provide a reliable battery level, so the
    function returns None for the battery in wired mode.
    
    Used for VXE Zero on Nordic 54L15 MCU.

    Returns:
        tuple[Optional[int], Optional[bool]]: Battery percentage, or None
        when it is unavailable, and the connection mode stored on the
        mouse object.
    """
    device = hid.device()
    try:
        device.open_path(mouse.device_path)

        report = [0] * 64
        report[0] = 0x08

        if mouse.wired:
            report[1] = 0x7C
            report[5] = 0x00
        else:
            report[1] = 0x7D
            report[5] = 0x01

        report[2] = 0x72
        report[3] = 0x02
        report[4] = 0x00
        report[6] = 0x07
        report[7] = 0x01

        logging.info(f"Sending report:  {report}")
        device.write(report)
        time.sleep(0.1)

        res = device.read(64)
        logging.info(f"Received report: {res}")

        if not res or len(res) < 8:
            logging.warning("No valid response from device")
            return None, mouse.wired

        if res[1] != 0x72 or res[5] != 0x07:
            logging.warning(f"Unexpected response: {res}")
            return None, mouse.wired

        if mouse.wired:
            logging.info("Protocol 2 wired connection does not report a reliable battery level")
            return None, mouse.wired

        battery = res[7]
        logging.info(f"Battery: {battery}, Wired: {bool(mouse.wired)}")
        return battery, mouse.wired
    finally:
        try:
            device.close()
        except Exception as e:
            logging.exception(e)


def get_battery(mouse: MouseClass):
    if mouse.protocol == 1:
        return get_battery_1(mouse)
    if mouse.protocol == 2:
        return get_battery_2(mouse)
    raise ValueError(f"Unsupported mouse protocol: {mouse.protocol}")


atk_f1_ultimate = MouseClass(
    model="ATK F1 Ultimate",
    vid=0x373B,
    pid_wireless=0x1031,
    pid_wired=0x102E,
    usage_page=0xFF02,
    usage=0x0002,
    protocol=1,
)
vxe_mad_r = MouseClass(
    model="VXE MAD R",
    vid=0x373B,
    pid_wireless=0x104D,
    pid_wired=0x103F,
    usage_page=0xFF02,
    usage=0x0002,
    protocol=1,
)
vxe_mad_r_major_plus = MouseClass(
    model="VXE MAD R Major Plus",
    vid=0x373B,
    pid_wireless=0x1040,
    pid_wired=0x104C,
    usage_page=0xFF02,
    usage=0x0002,
    protocol=1,
)
vxe_r1_pro_max = MouseClass(
    model="VXE R1 Pro Max",
    vid=0x3554,
    pid_wireless=0xF58A,
    pid_wired=0xF58C,
    usage_page=0xFF02,
    usage=0x0002,
    protocol=1,
)
vxe_r1_se_plus = MouseClass(
    model="VXE R1 SE+",
    vid=0x3554,
    pid_wireless=0xF58E,
    pid_wired=0xF58F,
    usage_page=0xFF02,
    usage=0x0002,
    protocol=1,
)
vgn_f1_pro = MouseClass(
    model="VGN F1 Pro",
    vid=0x3554,
    pid_wireless=0xF503,
    pid_wired=0xF502,
    usage_page=0xFF02,
    usage=0x0002,
    protocol=1,
)
atk_a9_ultimate = MouseClass(
    model="ATK A9 Ultimate",
    vid=0x373B,
    pid_wireless=0x11D9,
    pid_wired=0x11B6,
    usage_page=0xFF02,
    usage=0x0002,
    protocol=1,
)
atk_zero = MouseClass(
    model="ATK Zero",
    vid=0x373B,
    pid_wireless=0x1155,
    pid_wired=0x1154,
    usage_page=0xFF05,
    usage=0x0001,
    protocol=2,
)

atk_mice = [
    atk_f1_ultimate,
    atk_a9_ultimate,
    atk_zero,
    vxe_mad_r,
    vxe_mad_r_major_plus,
    vxe_r1_pro_max,
    vxe_r1_se_plus,
    vgn_f1_pro,
]
