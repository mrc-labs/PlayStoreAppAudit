"""Measure installed native providers; this never builds a release candidate."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib
import importlib.metadata as metadata
import json
import os
import platform
import re
import shutil
import ssl
import struct
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def loaded_images() -> list[Path]:
    if sys.platform == "win32":
        from ctypes import wintypes

        process = ctypes.windll.kernel32.GetCurrentProcess()
        handles = (ctypes.c_void_p * 4096)()
        needed = wintypes.DWORD()
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                            ctypes.POINTER(wintypes.DWORD)]
        psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                             wintypes.LPWSTR, wintypes.DWORD]
        if not psapi.EnumProcessModules(process, handles, ctypes.sizeof(handles), ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        if needed.value > ctypes.sizeof(handles):
            raise RuntimeError("Loaded module inventory buffer is insufficient")
        paths = []
        for handle in handles[:needed.value // ctypes.sizeof(ctypes.c_void_p)]:
            buffer = ctypes.create_unicode_buffer(32768)
            if not psapi.GetModuleFileNameExW(process, handle, buffer, len(buffer)):
                raise ctypes.WinError(ctypes.get_last_error())
            paths.append(Path(buffer.value))
        return sorted(set(paths))
    if sys.platform == "darwin":
        dyld = ctypes.CDLL(None)
        dyld._dyld_image_count.restype = ctypes.c_uint32
        dyld._dyld_get_image_name.argtypes = [ctypes.c_uint32]
        dyld._dyld_get_image_name.restype = ctypes.c_char_p
        return sorted({Path(os.fsdecode(dyld._dyld_get_image_name(i)))
                       for i in range(dyld._dyld_image_count())})
    paths = set()
    for line in Path("/proc/self/maps").read_text(encoding="utf-8").splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith("/"):
            paths.add(Path(fields[5]))
    return sorted(paths)


def run(command: list[str]) -> dict[str, Any]:
    executable = shutil.which(command[0])
    if not executable:
        return {"command": command, "unavailable": "not installed/on PATH"}
    result = subprocess.run([executable, *command[1:]], capture_output=True,
                            text=True, errors="replace", check=False, timeout=60)
    return {"command": command, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def inspect_binary(path: Path) -> dict[str, Any]:
    item: dict[str, Any] = {"path": str(path)}
    if not path.is_file():
        item["unavailable"] = "OS shared-cache or non-file image; not hashed"
        return item
    item["sha256"] = sha256(path)
    if sys.platform == "win32":
        from inspect_pe import describe_machine, read_pe_machine

        item["architecture"] = describe_machine(read_pe_machine(path))
        item["dependencies"] = run(["dumpbin", "/dependents", str(path)])
    elif sys.platform == "darwin":
        item["architecture"] = run(["lipo", "-archs", str(path)])
        item["dependencies"] = run(["otool", "-L", str(path)])
    else:
        item["architecture"] = run(["readelf", "-h", str(path)])
        item["dependencies"] = run(["ldd", str(path)])
    return item


def module_image(module: Any) -> dict[str, Any]:
    filename = getattr(module, "__file__", None)
    if filename is None:
        return {"provider": "built-in", "origin": module.__spec__.origin,
                "interpreter": str(Path(sys.executable))}
    return inspect_binary(Path(filename))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    actual_arch = platform.machine().lower()
    expected_arch = os.environ.get("EXPECTED_ARCH", "x64" if actual_arch in {"amd64", "x86_64"} else "arm64")
    if actual_arch not in ({"amd64", "x86_64"} if expected_arch == "x64" else {"arm64", "aarch64"}):
        raise RuntimeError(f"Non-native diagnostic Python: {actual_arch}, expected {expected_arch}")
    if struct.calcsize("P") != 8 or sysconfig.get_config_var("Py_GIL_DISABLED"):
        raise RuntimeError("Diagnostics require native 64-bit GIL-enabled Python")
    if sys.version_info[:2] != (3, 14) or sys.version_info.releaselevel != "final":
        raise RuntimeError("Diagnostics require stable Python 3.14")

    import decimal
    import pyexpat
    import sqlite3
    import zlib

    from cryptography.hazmat.backends.openssl.backend import backend
    from lxml import etree
    from PIL import features
    from PySide6 import QtCore, QtGui, QtNetwork

    app = QtCore.QCoreApplication([])
    QtNetwork.QSslSocket.supportsSsl()
    active = QtNetwork.QSslSocket.activeBackend()
    qt_backends = []
    for name in QtNetwork.QSslSocket.availableBackends():
        selected = QtNetwork.QSslSocket.setActiveBackend(name)
        item = {"name": name, "selected": selected}
        if selected:
            item.update({"supports_ssl": QtNetwork.QSslSocket.supportsSsl(),
                         "build_provider": QtNetwork.QSslSocket.sslLibraryBuildVersionString(),
                         "runtime_provider": QtNetwork.QSslSocket.sslLibraryVersionString()})
        qt_backends.append(item)
    if active:
        QtNetwork.QSslSocket.setActiveBackend(active)
    image = QtGui.QImage(2, 2, QtGui.QImage.Format.Format_ARGB32)
    image.fill(0xFF336699)
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG") or QtGui.QImage.fromData(bytes(buffer.data()), "PNG").isNull():
        raise RuntimeError("Qt PNG provider roundtrip failed")
    extensions = {}
    for name in ("_ssl", "_hashlib", "_sqlite3", "pyexpat", "zlib", "_bz2", "_lzma", "_ctypes",
                 "_zstd", "cryptography.hazmat.bindings._rust", "lxml.etree",
                 "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtNetwork"):
        module = importlib.import_module(name)
        extensions[name] = module_image(module)
    images = loaded_images()
    providers = []
    relevant = re.compile(r"(ssl|crypto|expat|sqlite|lzma|libffi|bz2|zstd|libz[.-]|xml2|xslt|libpng|pcre|harfbuzz|freetype)", re.I)
    for path in images:
        if not relevant.search(path.name):
            continue
        item = inspect_binary(path)
        if re.search(r"libcrypto", path.name, re.I) and path.is_file():
            library = ctypes.CDLL(str(path))
            library.OpenSSL_version.argtypes = [ctypes.c_int]
            library.OpenSSL_version.restype = ctypes.c_char_p
            item["openssl_version"] = library.OpenSSL_version(0).decode("ascii")
        if re.search(r"liblzma", path.name, re.I) and path.is_file():
            library = ctypes.CDLL(str(path))
            library.lzma_version_string.restype = ctypes.c_char_p
            item["lzma_version"] = library.lzma_version_string().decode("ascii")
        providers.append(item)
    qt_embedded_literals = []
    for path in images:
        if re.search(r"Qt[6]?(?:Gui|Core)(?:\.|$)", path.name) and path.is_file():
            data = path.read_bytes()
            candidates = sorted({match.decode("ascii") for match in re.findall(
                rb"(?<![0-9])(?:1\.6\.[0-9]{1,2}|10\.[0-9]{2} [0-9]{4}-[0-9]{2}-[0-9]{2})(?![0-9])", data)})
            qt_embedded_literals.append({"path": str(path), "sha256": hashlib.sha256(data).hexdigest(),
                                         "version_literals_not_runtime_api": candidates})
    qt_root = Path(QtCore.__file__).parent
    potential_ssl_files = []
    for directory in (Path(sys.base_prefix), qt_root):
        for path in directory.rglob("*"):
            if path.is_file() and re.search(r"(?:^lib(?:ssl|crypto)|(?:tls|ssl).*(?:\.dll|\.so|\.dylib)$)", path.name, re.I):
                potential_ssl_files.append({"path": str(path), "sha256": sha256(path)})
    report = {
        "scope": "non-release-installed-provider-diagnostic",
        "source_sha": os.environ.get("GITHUB_SHA"), "run_id": os.environ.get("GITHUB_RUN_ID"),
        "platform": sys.platform, "architecture": actual_arch, "python": platform.python_version(),
        "gil_disabled": False, "python_distribution": str(sys.base_prefix),
        "python_ssl": ssl.OPENSSL_VERSION, "cryptography_ssl": backend.openssl_version_text(),
        "sqlite": sqlite3.sqlite_version, "expat": pyexpat.EXPAT_VERSION,
        "mpdecimal": decimal.__libmpdec_version__,
        "zlib_api": zlib.ZLIB_VERSION, "zlib_runtime_api": zlib.ZLIB_RUNTIME_VERSION,
        "lxml": {"libxml_runtime": etree.LIBXML_VERSION, "libxml_compiled": etree.LIBXML_COMPILED_VERSION,
                 "libxslt_runtime": etree.LIBXSLT_VERSION, "libxslt_compiled": etree.LIBXSLT_COMPILED_VERSION},
        "pillow_development_only": {name: features.version(name) for name in features.get_supported()},
        "qt": {"version": QtCore.qVersion(), "build": QtCore.QLibraryInfo.build(),
               "default_tls_backend": active, "tls_backends": qt_backends,
               "png_roundtrip": "PASS", "embedded_binary_literals": qt_embedded_literals},
        "extensions": extensions, "loaded_relevant_images": providers,
        "installed_possible_ssl_files_not_package_inventory": potential_ssl_files,
        "loaded_image_paths": [str(path) for path in images],
        "python_distributions": sorted((dist.metadata["Name"], dist.version) for dist in metadata.distributions()),
        "runner": {key: os.environ.get(key) for key in ("RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion")},
        "tools": {name: run(command) for name, command in {
            "git": ["git", "--version"], "curl": ["curl", "--version"], "tar": ["tar", "--version"],
            "cmake": ["cmake", "--version"], "ninja": ["ninja", "--version"],
            "clang": ["clang", "--version"], "gcc": ["gcc", "--version"],
            "rust": ["rustc", "-vV"], "gh": ["gh", "--version"],
            "xcode": ["xcodebuild", "-version"], "dpkg": ["dpkg-query", "-W"],
        }.items()},
        "limits": ["Installed source environment; no Nuitka package was built.",
                   "Loaded images and installed possible TLS files do not prove final package closure.",
                   "Static dependency versions without a public query need source/SBOM/build evidence.",
                   "This inventory does not accept older providers or prove OpenSSL 4 uniformity."],
    }
    (output / "components.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    app.quit()
    print(json.dumps({key: report[key] for key in ("platform", "architecture", "python", "python_ssl",
                                                "cryptography_ssl", "sqlite", "expat", "zlib_runtime_api", "qt")}, indent=2))


if __name__ == "__main__":
    main()
