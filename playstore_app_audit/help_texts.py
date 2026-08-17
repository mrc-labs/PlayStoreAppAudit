from __future__ import annotations

ADB_SETUP_GUIDE = """ADB setup guide

1. On the Android phone, enable Developer options and USB debugging.
2. Connect the phone with a data-capable USB cable.
3. In Play Store App Audit choose Scan phone.
4. If ADB is missing, managed Platform-Tools availability depends on the desktop:
   - Windows: managed Platform-Tools are available where supported by the app.
   - macOS: managed Platform-Tools are available where supported by the app.
   - Linux x64: the app supports Google's managed Linux Platform-Tools download.
   - Linux ARM64: Google does not provide the managed Linux archive used by this app;
     install a native ADB from the system, distribution or an ARM64-compatible Android SDK.
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

ADB_SETUP_GUIDE_HTML = r"""
<h1>Connect an Android phone with ADB</h1>
<p class="lead">Set up Android Debug Bridge once, then Play Store App Audit can read the
installed-package inventory and optional device metadata directly from your phone.</p>

<h2>1. Prepare the phone</h2>
<ol>
  <li>Open <b>Settings → About phone</b> and tap <b>Build number</b> seven times to enable
      <a href="https://developer.android.com/studio/debug/dev-options">Developer options</a>.</li>
  <li>Open Developer options and enable <b>USB debugging</b>.</li>
  <li>Connect the phone with a <b>data-capable USB cable</b>. A charge-only cable cannot carry ADB data.</li>
  <li>Keep the phone unlocked. When Android shows the RSA prompt, approve
      <b>Allow USB debugging?</b>. “Always allow from this computer” is optional.</li>
</ol>

<h2>2. Scan in Play Store App Audit</h2>
<ol>
  <li>Choose <b>Scan phone</b> in the source card or <b>File → Scan phone with ADB</b>.</li>
  <li>If ADB is already on <code>PATH</code>, or installed under an Android SDK named by
      <code>ANDROID_SDK_ROOT</code> / <code>ANDROID_HOME</code>, the app uses it.</li>
  <li>If ADB is missing and a managed download is supported, the app can fetch Google’s official
      <a href="https://developer.android.com/tools/releases/platform-tools">Android Platform-Tools</a>.</li>
</ol>

<div class="note"><b>Release note:</b> v1.1.0 is distributed as a prebuilt Windows x64 application.
The shared source still supports Windows, macOS and Linux, and the ADB rules below also apply to
source builds on those platforms.</div>

<h2>Platform-Tools availability</h2>
<ul>
  <li><b>Windows:</b> managed Google Platform-Tools are supported by the application where available.
      A manufacturer USB driver can occasionally be required.</li>
  <li><b>macOS:</b> managed Platform-Tools are supported where available; a separate Android USB
      driver is normally unnecessary.</li>
  <li><b>Linux x64:</b> the app supports Google’s managed Linux Platform-Tools archive.</li>
  <li><b>Linux ARM64 and unsupported host architectures:</b> install a native/system ADB from the
      distribution or an architecture-compatible Android SDK. Google does not provide the managed
      Linux archive used by this app for Linux ARM64.</li>
</ul>

<h2>Troubleshooting</h2>
<ol>
  <li>Try another cable and USB port, then select <b>File transfer / Data</b> as the phone’s USB mode.</li>
  <li>Revoke USB debugging authorisations on the phone, reconnect, and accept the RSA prompt again.</li>
  <li>Close other tools that may be holding ADB, then run <code>adb devices</code> in PowerShell or a shell:</li>
</ol>
<pre><code>adb devices</code></pre>
<p>An <code>unauthorized</code> device needs approval on the unlocked phone. An <code>offline</code> device
usually needs reconnecting. Linux may also require a suitable udev rule or USB-device permission.</p>

<div class="warning"><b>Read-only use:</b> Play Store App Audit uses ADB only for inventory and metadata
inspection. It does not install, uninstall, disable, enable or modify apps on the phone.</div>
"""

IMPORT_APP_LIST_GUIDE_HTML = r"""
<h1>Import an Android app list</h1>
<p class="lead">Load package IDs from a reusable file, drop that file onto the window, choose a recent
source, or scan a connected phone directly.</p>

<h2>Fastest option: scan the phone</h2>
<p>Choose <b>Scan phone</b>, or use <b>File → Scan phone with ADB</b>. This avoids creating a file and can
also collect optional device metadata. See the ADB setup guide if the phone is not detected.</p>

<h2>Supported files</h2>
<p>Play Store App Audit accepts <b>CSV, TSV and TXT</b>. The simplest format is one Android package ID
per line:</p>
<pre><code>com.example.firstapp
com.example.secondapp
org.example.thirdapp</code></pre>
<p>For CSV, use a column named <code>package_name</code>:</p>
<pre><code>package_name
com.example.firstapp
com.example.secondapp</code></pre>
<p>Where supported, a CSV may include optional system-app metadata such as an <code>is_system</code> column.
Use values such as <code>true</code>/<code>false</code> or <code>1</code>/<code>0</code>.</p>

<h2>Load and reuse a file</h2>
<ol>
  <li>Click <b>Choose file</b> and select a CSV, TSV or TXT file.</li>
  <li>Alternatively, drag one supported file onto the main window.</li>
  <li>Files loaded successfully appear under the arrow beside Choose file and under
      <b>File → Recent sources</b>. Files that no longer exist are omitted.</li>
  <li>Choose <b>Run Play Store audit</b> when the source status says the file is ready.</li>
</ol>

<h2>Create a reusable CSV with ADB</h2>
<h3>PowerShell on Windows</h3>
<pre><code>"package_name" | Set-Content packages.csv
.\adb.exe shell pm list packages -3 |
  ForEach-Object { $_ -replace "^package:", "" } |
  Sort-Object -Unique |
  Add-Content packages.csv</code></pre>
<h3>macOS / Linux shell</h3>
<pre><code>printf 'package_name\n' &gt; packages.csv
adb shell pm list packages -3 |
  sed 's/^package://' |
  sort -u &gt;&gt; packages.csv</code></pre>
<p><code>-3</code> requests third-party apps only. Remove it to include system packages. You can later import
the resulting file with Choose file, drag-and-drop, or Recent sources.</p>

<h2>Phone-only alternatives</h2>
<p>Android has no standard built-in “export every package ID to CSV” button. A package-manager app may
export package IDs, but output formats and access vary. An advanced Shizuku/local-ADB capable shell can
create a file in Downloads:</p>
<pre><code>sh -c 'echo package_name &gt; /sdcard/Download/packages.csv;
pm list packages -3 | sed "s/^package://" &gt;&gt; /sdcard/Download/packages.csv'</code></pre>
<div class="warning"><b>Limitation:</b> an ordinary terminal app may not have shell-level package access.
The command can require Shizuku, local ADB or equivalent authorised access. Root is not required when an
authorised shell-level method is available.</div>
"""
