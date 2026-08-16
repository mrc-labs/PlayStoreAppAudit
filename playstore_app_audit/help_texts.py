from __future__ import annotations

ADB_SETUP_GUIDE = """ADB setup guide

1. On the Android phone, enable Developer options and USB debugging.
2. Connect the phone with a data-capable USB cable.
3. In Play Store App Audit choose Scan phone.
4. If ADB is missing, the app can download the current Android Platform-Tools archive
   directly from Google's official endpoint for Windows, macOS or Linux.
5. Keep the phone unlocked and accept the 'Allow USB debugging?' RSA prompt.
   You can optionally choose 'Always allow from this computer'.
6. If the phone is not detected, try another cable/USB port and switch the phone USB mode
   to File transfer/Data if required.

Platform notes
- Windows: a manufacturer USB driver can occasionally be required.
- macOS: no separate Android USB driver is normally required.
- Linux: some distributions require an appropriate udev rule or user permission for the USB device.

You can also install Android Platform-Tools yourself and put 'adb' on PATH, or point
ANDROID_SDK_ROOT / ANDROID_HOME to an Android SDK installation.

Play Store App Audit uses ADB read-only for inventory and metadata inspection.
It does not uninstall or disable apps.
"""
