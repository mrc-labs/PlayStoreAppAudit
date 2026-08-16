from playstore_app_audit.platform import runtime


def test_platform_tools_url_is_official_google_endpoint() -> None:
    assert runtime.platform_tools_url().startswith(
        "https://dl.google.com/android/repository/platform-tools-latest-"
    )
    assert runtime.platform_tools_url().endswith(".zip")


def test_adb_name_matches_platform() -> None:
    if runtime.platform_key() == "windows":
        assert runtime.adb_executable_name() == "adb.exe"
    else:
        assert runtime.adb_executable_name() == "adb"


def test_store_country_has_two_letters() -> None:
    country = runtime.detect_store_country()
    assert len(country) == 2
    assert country.isalpha()
