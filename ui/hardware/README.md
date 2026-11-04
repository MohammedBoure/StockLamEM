# Peripheral Hardware Isolation Layer (`ui/hardware/`)

This directory contains low-level peripheral integration modules for multi-scanner / multi-session barcode routing on a single workstation.

## Files and Purpose

- **`__init__.py`**: Package initializer exposing `MultiScannerHIDManager`, `DeviceScanBuffer`, and `WindowsRawInputFilter`.
- **`raw_input_filter.py`**: Implements thread-safe per-device HID character buffering (`MultiScannerHIDManager`), inter-keystroke burst framing (`DeviceScanBuffer`), and Win32 RawInput API interception (`WindowsRawInputFilter`) so multiple USB/Bluetooth barcode scanners connected to the same PC route their scans to independent sales or dispatch sessions without character interleaving.
