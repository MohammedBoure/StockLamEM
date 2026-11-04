# ui/hardware/raw_input_filter.py
"""
Multi-Scanner / Multi-Session Hardware Isolation Engine.
Provides:
1. MultiScannerHIDManager: Thread-safe, per-device character stream accumulator and
   Device-to-Session router preventing keystroke interleaving when multiple USB/Bluetooth
   barcode scanners operate simultaneously on the same PC.
2. WindowsRawInputFilter: PySide6 QAbstractNativeEventFilter wrapping Win32 RawInput API
   (user32.dll: RegisterRawInputDevices, GetRawInputData, GetRawInputDeviceInfoW).
"""

import ctypes
from ctypes import wintypes
import queue
import re
import sys
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

try:
    from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray, QObject, QTimer, Signal
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    QObject = object
    QAbstractNativeEventFilter = object

    class Signal:  # type: ignore
        def __init__(self, *args):
            self._callbacks = []

        def connect(self, cb):
            self._callbacks.append(cb)

        def emit(self, *args):
            for cb in list(self._callbacks):
                cb(*args)

# Windows Raw Input Constants
RIDEV_INPUTSINK = 0x00000100
RIDEV_DEVNOTIFY = 0x00002000
RIDEV_REMOVE = 0x00000001

RID_INPUT = 0x10000003
RID_HEADER = 0x10000005

RIDI_DEVICENAME = 0x20000007
RIDI_DEVICEINFO = 0x2000000B

RIM_TYPEKEYBOARD = 1
WM_INPUT = 0x00FF
WM_INPUT_DEVICE_CHANGE = 0x00FE

RI_KEY_MAKE = 0
RI_KEY_BREAK = 1

GIDC_ARRIVAL = 1
GIDC_REMOVAL = 2


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("VKey", wintypes.USHORT),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG),
    ]


class RAWINPUT(ctypes.Structure):
    class _RAWINPUTUNION(ctypes.Union):
        _fields_ = [("keyboard", RAWKEYBOARD)]

    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", _RAWINPUTUNION),
    ]


PRAWINPUT = ctypes.POINTER(RAWINPUT)


class MultiScannerHIDManager:
    """
    Thread-safe, device-isolated character buffering and session routing engine.
    Guarantees zero character interleaving across multiple concurrent barcode scanners
    connected to the same computer, and routes each scanner's output to its dedicated
    sales or dispatch session.
    """

    def __init__(self, burst_timeout_ms=500.0):
        self.burst_timeout_ms = float(burst_timeout_ms) if isinstance(burst_timeout_ms, (int, float)) else 500.0
        self.buffers: Dict[str, List[str]] = {}
        self.last_char_time: Dict[str, float] = {}
        self.locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self.completed_scans: "queue.Queue[Tuple[str, str]]" = queue.Queue()
        self.device_to_session: Dict[str, str] = {}
        self.session_callbacks: Dict[str, List[Callable[[str, str], None]]] = {}
        self.global_callbacks: List[Callable[[str, str, Optional[str]], None]] = []

    @staticmethod
    def sanitize_barcode(raw_code: str) -> str:
        """Strips non-printable ASCII characters and control sequences."""
        cleaned = "".join(ch for ch in str(raw_code or "") if 0x20 <= ord(ch) <= 0x7E).strip()
        return cleaned

    def bind_scanner_to_session(self, device_id: str, session_id: str) -> None:
        """Binds a physical scanner device handle/ID to an independent UI session."""
        with self._global_lock:
            self.device_to_session[str(device_id)] = str(session_id)

    def unbind_scanner(self, device_id: str) -> None:
        """Removes session binding for a scanner device."""
        with self._global_lock:
            self.device_to_session.pop(str(device_id), None)

    def get_session_for_device(self, device_id: str) -> Optional[str]:
        """Returns the session ID bound to the given scanner device_id, if any."""
        with self._global_lock:
            return self.device_to_session.get(str(device_id))

    def register_session_callback(self, session_id: str, callback: Callable[[str, str], None]) -> None:
        """Registers a listener callback(device_id, barcode) for a specific session."""
        with self._global_lock:
            self.session_callbacks.setdefault(str(session_id), []).append(callback)

    def register_global_callback(self, callback: Callable[[str, str, Optional[str]], None]) -> None:
        """Registers a listener callback(device_id, barcode, session_id) for all scans."""
        with self._global_lock:
            self.global_callbacks.append(callback)

    def _get_device_lock(self, device_id: str) -> threading.Lock:
        with self._global_lock:
            if device_id not in self.locks:
                self.locks[device_id] = threading.Lock()
            return self.locks[device_id]

    def receive_raw_keystroke(self, device_id: str, char: str) -> Optional[str]:
        """
        Appends a raw character from a specific hardware device handle into its isolated buffer.
        When a terminator (CR, LF, Tab, ETX) is received, flushes and dispatches the complete barcode.
        """
        dev_key = str(device_id)
        lock = self._get_device_lock(dev_key)
        dispatched_code: Optional[str] = None
        now = time.monotonic()

        with lock:
            buf = self.buffers.setdefault(dev_key, [])
            last_t = self.last_char_time.get(dev_key)
            if last_t is not None and buf and ((now - last_t) * 1000.0 > self.burst_timeout_ms):
                # Purge stale partial fragment from an interrupted scan
                buf.clear()

            self.last_char_time[dev_key] = now

            if char in ("\r", "\n", "\t", "\x03"):
                full_code = self.sanitize_barcode("".join(buf))
                self.buffers[dev_key] = []
                if full_code:
                    dispatched_code = full_code
                    self.completed_scans.put((dev_key, full_code))
            else:
                if 0x20 <= ord(char[0]) <= 0x7E:
                    buf.append(char[0])

        if dispatched_code:
            self._dispatch_to_listeners(dev_key, dispatched_code)
        return dispatched_code

    # Alias matching docs snippet
    on_raw_keystroke = receive_raw_keystroke

    def feed_device_character(self, device_id: str, vk_or_char) -> Optional[str]:
        """Feeds either an integer virtual-key/ASCII code or a character string for a device."""
        if isinstance(vk_or_char, int):
            ch = "\r" if vk_or_char in (0x0D, 0x0A) else chr(vk_or_char)
        else:
            ch = str(vk_or_char)
        return self.receive_raw_keystroke(device_id, ch)

    def simulate_scan(self, device_id: str, barcode: str) -> Optional[str]:
        """Simulates a full hardware barcode scan burst followed by a carriage return."""
        for ch in str(barcode):
            self.receive_raw_keystroke(device_id, ch)
        return self.receive_raw_keystroke(device_id, "\r")

    def _dispatch_to_listeners(self, device_id: str, barcode: str) -> None:
        session_id = self.get_session_for_device(device_id)
        with self._global_lock:
            s_cbs = list(self.session_callbacks.get(session_id, [])) if session_id else []
            g_cbs = list(self.global_callbacks)

        for cb in s_cbs:
            try:
                cb(device_id, barcode)
            except Exception:
                pass
        for gcb in g_cbs:
            try:
                gcb(device_id, barcode, session_id)
            except Exception:
                pass


class DeviceScanBuffer:
    """Buffers rapid keystroke bursts from a specific hardware device with Qt timer fallback."""

    def __init__(self, device_handle: int, device_name: str, on_scan_complete: Callable[[str, str], None]):
        self.device_handle = device_handle
        self.device_name = device_name
        self.on_scan_complete = on_scan_complete
        self.char_buffer: List[str] = []
        self.burst_timer = None
        if HAS_PYSIDE6:
            try:
                self.burst_timer = QTimer()
                self.burst_timer.setSingleShot(True)
                self.burst_timer.setInterval(65)
                self.burst_timer.timeout.connect(self._flush_buffer)
            except Exception:
                self.burst_timer = None

    def append_char(self, char: str) -> None:
        self.char_buffer.append(char)
        if self.burst_timer is not None:
            self.burst_timer.start()

    def handle_terminator(self) -> None:
        if self.burst_timer is not None:
            self.burst_timer.stop()
        self._flush_buffer()

    def _flush_buffer(self) -> None:
        if self.char_buffer:
            payload = MultiScannerHIDManager.sanitize_barcode("".join(self.char_buffer))
            self.char_buffer.clear()
            if len(payload) >= 3:
                self.on_scan_complete(str(self.device_handle), payload)


class WindowsRawInputFilter(QObject, QAbstractNativeEventFilter):
    """
    Native Event Filter hooked into QCoreApplication on Windows.
    Intercepts WM_INPUT events directly from user32.dll and routes each physical
    scanner's barcode stream to its assigned session via MultiScannerHIDManager.
    """

    scanReceived = Signal(str, str)               # device_id, barcode_text
    sessionScanReceived = Signal(str, str, str)   # session_id, device_id, barcode_text
    deviceConnected = Signal(str, str)            # device_id, device_path
    deviceDisconnected = Signal(str)              # device_id

    def __init__(self, hid_manager: Optional[MultiScannerHIDManager] = None, parent=None):
        if HAS_PYSIDE6:
            super().__init__(parent)
        self.hid_manager = hid_manager or MultiScannerHIDManager()
        self._user32 = getattr(ctypes, "windll", None).user32 if sys.platform == "win32" else None
        self._device_names: Dict[int, str] = {}
        self._shift_state_by_device: Dict[int, bool] = {}

        self.hid_manager.register_global_callback(self._on_manager_scan)

    def _on_manager_scan(self, device_id: str, barcode: str, session_id: Optional[str]) -> None:
        self.scanReceived.emit(device_id, barcode)
        if session_id:
            self.sessionScanReceived.emit(session_id, device_id, barcode)

    def register_devices(self, hwnd: int) -> bool:
        """Registers the target window handle to receive raw keyboard events on Windows."""
        if not self._user32 or not hwnd:
            return False
        rid = RAWINPUTDEVICE()
        rid.usUsagePage = 0x01  # Generic Desktop Controls
        rid.usUsage = 0x06      # Keyboard
        rid.dwFlags = RIDEV_INPUTSINK | RIDEV_DEVNOTIFY
        rid.hwndTarget = int(hwnd)

        success = self._user32.RegisterRawInputDevices(
            ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)
        )
        return bool(success)

    def _get_device_name(self, hDevice: int) -> str:
        if hDevice in self._device_names:
            return self._device_names[hDevice]
        if not self._user32:
            return f"SIM_DEVICE_{hDevice}"

        size = wintypes.UINT(0)
        self._user32.GetRawInputDeviceInfoW(hDevice, RIDI_DEVICENAME, None, ctypes.byref(size))
        if size.value == 0:
            return f"HID_DEVICE_{hDevice}"

        buf = ctypes.create_unicode_buffer(size.value)
        self._user32.GetRawInputDeviceInfoW(hDevice, RIDI_DEVICENAME, buf, ctypes.byref(size))
        dev_name = buf.value or f"HID_DEVICE_{hDevice}"
        self._device_names[hDevice] = dev_name
        return dev_name

    def nativeEventFilter(self, eventType: QByteArray, message: int) -> Tuple[bool, int]:
        if eventType != b"windows_generic_MSG" or not self._user32:
            return False, 0

        msg = wintypes.MSG.from_address(int(message))

        if msg.message == WM_INPUT_DEVICE_CHANGE:
            change_type = msg.wParam
            hDevice = msg.lParam
            if change_type == GIDC_ARRIVAL:
                dev_name = self._get_device_name(hDevice)
                self.deviceConnected.emit(str(hDevice), dev_name)
            elif change_type == GIDC_REMOVAL:
                self.deviceDisconnected.emit(str(hDevice))
                self._device_names.pop(hDevice, None)
                self._shift_state_by_device.pop(hDevice, None)
            return False, 0

        if msg.message == WM_INPUT:
            dwSize = wintypes.UINT(0)
            self._user32.GetRawInputData(
                msg.lParam, RID_INPUT, None, ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER)
            )
            if dwSize.value == 0:
                return False, 0

            raw_buffer = ctypes.create_string_buffer(dwSize.value)
            res = self._user32.GetRawInputData(
                msg.lParam, RID_INPUT, raw_buffer, ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER)
            )
            if res != dwSize.value:
                return False, 0

            raw = ctypes.cast(raw_buffer, PRAWINPUT).contents
            if raw.header.dwType == RIM_TYPEKEYBOARD:
                self._process_keyboard_input(raw.header.hDevice, raw.data.keyboard)

        return False, 0

    def _process_keyboard_input(self, hDevice: int, kbd: RAWKEYBOARD) -> None:
        is_break = bool(kbd.Flags & RI_KEY_BREAK)
        vkey = kbd.VKey

        if vkey in (0x10, 0xA0, 0xA1):  # VK_SHIFT
            self._shift_state_by_device[hDevice] = not is_break
            return

        if is_break:
            return

        if vkey in (0x0D, 0x09):  # VK_RETURN, VK_TAB
            self.hid_manager.receive_raw_keystroke(str(hDevice), "\r")
            return

        shift = self._shift_state_by_device.get(hDevice, False)
        char = self._vkey_to_char(vkey, shift)
        if char:
            self.hid_manager.receive_raw_keystroke(str(hDevice), char)

    @staticmethod
    def _vkey_to_char(vkey: int, shift: bool) -> Optional[str]:
        if 0x30 <= vkey <= 0x39:
            num = chr(vkey)
            if shift:
                symbols = {
                    "1": "!", "2": "@", "3": "#", "4": "$", "5": "%",
                    "6": "^", "7": "&", "8": "*", "9": "(", "0": ")",
                }
                return symbols.get(num, num)
            return num
        if 0x41 <= vkey <= 0x5A:
            char = chr(vkey)
            return char if shift else char.lower()
        if 0x60 <= vkey <= 0x69:
            return chr(vkey - 0x60 + ord("0"))
        if vkey == 0xBD:
            return "_" if shift else "-"
        if vkey == 0xBF:
            return "?" if shift else "/"
        if vkey == 0xBA:
            return ":" if shift else ";"
        return None
