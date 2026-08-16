from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Patch point not found in {relative}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Patch point not found in {relative}: {old[:120]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def patch_compact() -> None:
    rel = "playstore_app_audit/ui/compact_window.py"
    replace_once(rel, "\nbase_ui.audit_apps = audit_apps_multicountry\n", "\n")
    replace_once(rel, "\nbase_ui.classify_criticality = _classify_criticality_multicountry\n", "\n")
    replace_once(
        rel,
        '        self._set_run_mode("run")\n\n    # ---------- Layout ----------',
        '''        self._set_run_mode("run")\n\n    # ---------- Behaviour hooks ----------\n    def _classify_row(self, row: dict[str, object]) -> None:\n        _classify_criticality_multicountry(row)\n\n    def _load_fresh_cache(\n        self,\n        apps: list[dict[str, str]],\n        country: str,\n        language: str,\n        ttl_hours: int,\n    ) -> dict[str, dict[str, object]]:\n        return load_fresh_cache(apps, country, language, ttl_hours)\n\n    # ---------- Layout ----------''',
    )
    replace_once(
        rel,
        '        cached = load_fresh_cache(apps, country, language, ttl) if cache_enabled else {}',
        '        cached = self._load_fresh_cache(apps, country, language, ttl) if cache_enabled else {}',
    )
    replace_all(rel, "            base_ui.classify_criticality(row)\n", "            self._classify_row(row)\n")
    replace_once(rel, '            "Development assistance: OpenAI ChatGPT<br><br>"\n', "")


def patch_device() -> None:
    rel = "playstore_app_audit/ui/device_window.py"
    replace_once(
        rel,
        '''# Use the enhanced v8 audit path and merge-safe history writer.\ncompact_ui.audit_apps_multicountry = device_metadata.audit_apps_v8\ncompact_ui.save_history = device_metadata.save_history_merged\n\n_ORIGINAL_LOAD_FRESH_CACHE = compact_ui.load_fresh_cache\n_BYPASS_CACHE_ONCE = False\n\n\ndef _load_fresh_cache_proxy(*args, **kwargs):\n    if _BYPASS_CACHE_ONCE:\n        return {}\n    return _ORIGINAL_LOAD_FRESH_CACHE(*args, **kwargs)\n\n\ncompact_ui.load_fresh_cache = _load_fresh_cache_proxy\n\n\n''',
        "",
    )
    replace_once(
        rel,
        '        self._update_summary()\n\n    # ---------- Menus ----------',
        '''        self._update_summary()\n\n    # ---------- Behaviour hooks ----------\n    def _load_fresh_cache(\n        self,\n        apps: list[dict[str, str]],\n        country: str,\n        language: str,\n        ttl_hours: int,\n    ) -> dict[str, dict[str, object]]:\n        if self._force_refresh_next:\n            return {}\n        return super()._load_fresh_cache(apps, country, language, ttl_hours)\n\n    def _collect_device_metadata(self, adb: str, packages: list[str], cancel_event):\n        return device_metadata.collect_device_metadata(adb, packages, cancel_event)\n\n    def _enrich_rows_with_device_metadata(\n        self, rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]\n    ) -> None:\n        device_metadata.enrich_rows_with_device_metadata(rows, metadata)\n\n    # ---------- Menus ----------''',
    )
    replace_once(
        rel,
        '''    def _start_audit(self) -> None:\n        global _BYPASS_CACHE_ONCE\n        if self._audit_active:\n            super()._start_audit()\n            return\n        settings = state.load_settings()\n        selected_country = (self.country_edit.text().strip() or "").lower()\n        device_metadata.set_fallback_countries(\n            settings.get("fallback_countries", device_metadata.DEFAULT_FALLBACK_COUNTRIES),\n            selected_country,\n        )\n        _BYPASS_CACHE_ONCE = bool(self._force_refresh_next)\n        try:\n            super()._start_audit()\n        finally:\n            _BYPASS_CACHE_ONCE = False\n            self._force_refresh_next = False\n            self._apps_override = None\n''',
        '''    def _start_audit(self) -> None:\n        if self._audit_active:\n            super()._start_audit()\n            return\n        settings = state.load_settings()\n        selected_country = (self.country_edit.text().strip() or "").lower()\n        device_metadata.set_fallback_countries(\n            settings.get("fallback_countries", device_metadata.DEFAULT_FALLBACK_COUNTRIES),\n            selected_country,\n        )\n        try:\n            super()._start_audit()\n        finally:\n            self._force_refresh_next = False\n            self._apps_override = None\n''',
    )
    replace_once(
        rel,
        '''                    metadata_future = metadata_executor.submit(\n                        device_metadata.collect_device_metadata,\n                        adb,\n                        [app["package_name"] for app in all_apps],\n                        cancel_event,\n                    )''',
        '''                    metadata_future = metadata_executor.submit(\n                        self._collect_device_metadata,\n                        adb,\n                        [app["package_name"] for app in all_apps],\n                        cancel_event,\n                    )''',
    )
    replace_once(
        rel,
        "            device_metadata.enrich_rows_with_device_metadata(rows, metadata)\n",
        "            self._enrich_rows_with_device_metadata(rows, metadata)\n",
    )
    replace_all(rel, "            base_ui.classify_criticality(row)\n", "            self._classify_row(row)\n")


def patch_insights() -> None:
    rel = "playstore_app_audit/ui/insights_window.py"
    replace_once(
        rel,
        "import playstore_app_audit.services.device_insights as device_insights\n",
        "import playstore_app_audit.services.device_insights as device_insights\nimport playstore_app_audit.services.presentation as presentation\n",
    )
    replace_once(
        rel,
        '''# v8 imports the feature module object, so replacing these functions upgrades\n# its existing background worker without duplicating the audit engine.\ndevice_ui.device_metadata.collect_device_metadata = device_insights.collect_device_metadata_v9\ndevice_ui.device_metadata.enrich_rows_with_device_metadata = (\n    device_insights.enrich_rows_with_device_metadata_v9\n)\n\n_original_classify = base_ui.classify_criticality\n\n\ndef _classify_with_health(row: dict[str, Any]) -> None:\n    _original_classify(row)\n    device_insights.apply_health_score(row)\n\n\nbase_ui.classify_criticality = _classify_with_health\n\n\n''',
        "",
    )
    replace_once(
        rel,
        '        device_insights.log_event("Qt6 v9 started")\n\n    # ---------- Column/view presets ----------',
        '''        device_insights.log_event("Qt6 insights layer started")\n\n    # ---------- Behaviour hooks ----------\n    def _collect_device_metadata(self, adb: str, packages: list[str], cancel_event):\n        return device_insights.collect_device_metadata_v9(adb, packages, cancel_event)\n\n    def _enrich_rows_with_device_metadata(\n        self, rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]\n    ) -> None:\n        device_insights.enrich_rows_with_device_metadata_v9(rows, metadata)\n\n    def _classify_row(self, row: dict[str, Any]) -> None:\n        super()._classify_row(row)\n        device_insights.apply_health_score(row)\n\n    # ---------- Column/view presets ----------''',
    )
    replace_all(rel, "device_insights.VIEW_PRESETS", "presentation.VIEW_PRESETS")
    replace_all(rel, "device_insights.CSV_EXPORT_GUIDE", "presentation.CSV_EXPORT_GUIDE")
    replace_once(rel, '            "Development assistance: OpenAI ChatGPT<br>"\n', "")


def patch_preferences() -> None:
    rel = "playstore_app_audit/ui/preferences_window.py"
    replace_once(
        rel,
        '''device_insights.VIEW_PRESETS = presentation.VIEW_PRESETS\ndevice_insights.CSV_EXPORT_GUIDE = presentation.CSV_EXPORT_GUIDE\ndevice_insights.APP_VERSION = presentation.APP_VERSION\n\n\n''',
        "",
    )


def patch_tests() -> None:
    rel = "tests/test_architecture.py"
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    marker = "\ndef test_no_runtime_cross_module_monkey_patching() -> None:\n"
    if marker in text:
        return
    text += '''\n\ndef test_no_runtime_cross_module_monkey_patching() -> None:\n    root = Path(__file__).resolve().parents[1]\n    forbidden = (\n        "base_ui.audit_apps =",\n        "base_ui.classify_criticality =",\n        "compact_ui.audit_apps_multicountry =",\n        "compact_ui.load_fresh_cache =",\n        "device_ui.device_metadata.collect_device_metadata =",\n        "device_insights.VIEW_PRESETS =",\n        "Development assistance: OpenAI ChatGPT",\n    )\n    for path in (root / "playstore_app_audit").rglob("*.py"):\n        source = path.read_text(encoding="utf-8")\n        for snippet in forbidden:\n            assert snippet not in source, f"{snippet!r} reintroduced in {path.relative_to(root)}"\n'''
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_compact()
    patch_device()
    patch_insights()
    patch_preferences()
    patch_tests()
    print("Behaviour-hook refactor applied.")


if __name__ == "__main__":
    main()
