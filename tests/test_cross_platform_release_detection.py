from pathlib import Path

import prepare_release_legal_bundle as legal


def _touch(root: Path, *paths: str) -> None:
    for relative in paths:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"runtime")


def test_qt_component_detection_windows(tmp_path: Path) -> None:
    _touch(
        tmp_path,
        "PySide6/Qt6Core.dll",
        "PySide6/Qt6Svg.dll",
        "PySide6/plugins/imageformats/qwebp.dll",
        "shiboken6/Shiboken.pyd",
    )

    assert legal._detect_qt_components(tmp_path) == [
        "qtbase",
        "qtsvg",
        "qtimageformats",
        "pyside-setup",
    ]


def test_qt_component_detection_linux(tmp_path: Path) -> None:
    _touch(
        tmp_path,
        "libQt6Core.so.6",
        "libQt6Svg.so.6",
        "PySide6/QtCore.abi3.so",
        "plugins/imageformats/libqwebp.so",
        "libshiboken6.abi3.so",
    )

    assert legal._detect_qt_components(tmp_path) == [
        "qtbase",
        "qtsvg",
        "qtimageformats",
        "pyside-setup",
    ]


def test_qt_component_detection_macos(tmp_path: Path) -> None:
    _touch(
        tmp_path,
        "Contents/Frameworks/QtCore.framework/Versions/A/QtCore",
        "Contents/Frameworks/QtSvg.framework/Versions/A/QtSvg",
        "Contents/Resources/PySide6/QtCore.abi3.so",
        "Contents/PlugIns/imageformats/libqwebp.dylib",
        "Contents/Frameworks/libshiboken6.abi3.dylib",
    )

    assert legal._detect_qt_components(tmp_path) == [
        "qtbase",
        "qtsvg",
        "qtimageformats",
        "pyside-setup",
    ]


def test_qpdf_forbidden_on_all_desktop_platforms(
    tmp_path: Path,
) -> None:
    for index, name in enumerate(
        ("qpdf.dll", "libqpdf.so", "libqpdf.dylib")
    ):
        package = tmp_path / str(index)
        _touch(package, f"plugins/imageformats/{name}")

        matches = legal._forbidden_matches(package)

        assert len(matches) == 1
        assert matches[0]["path"].endswith(name)


def test_adb_detection_on_all_desktop_platforms(
    tmp_path: Path,
) -> None:
    _touch(
        tmp_path,
        "windows/adb.exe",
        "windows/AdbWinApi.dll",
        "windows/AdbWinUsbApi.dll",
        "unix/adb",
    )

    assert legal._bundled_adb_paths(tmp_path) == [
        "unix/adb",
        "windows/adb.exe",
        "windows/AdbWinApi.dll",
        "windows/AdbWinUsbApi.dll",
    ]
