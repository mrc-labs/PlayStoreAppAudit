from playstore_app_audit.services import presentation
from playstore_app_audit.services.audit_engine import _parse_updated_from_html


def test_date_modified_is_accepted() -> None:
    html = '<script type="application/ld+json">{"dateModified":"2026-08-01"}</script>'
    assert _parse_updated_from_html(html) == "2026-08-01"


def test_date_published_is_not_latest_update() -> None:
    html = '<script type="application/ld+json">{"datePublished":"2018-04-12"}</script>'
    assert _parse_updated_from_html(html) == ""


def test_structured_update_wins_over_localized_visible_date() -> None:
    html = (
        '<div>Aggiornata il 23 ago 2026</div>'
        '<script type="application/ld+json">{"dateModified":"2026-08-23"}</script>'
    )
    updated = _parse_updated_from_html(html)
    assert updated == "2026-08-23"
    assert presentation.format_date_value(updated) == "2026-08-23"


def test_localized_visible_update_uses_configured_default_format() -> None:
    html = '<div>Aggiornata il 23 ago 2026</div>'
    updated = _parse_updated_from_html(html)
    assert updated == "23 ago 2026"
    assert presentation.format_date_value(updated) == "2026-08-23"


def test_explicit_updated_field_is_accepted() -> None:
    html = '<script>{"updated":"Aug 1, 2026"}</script>'
    assert _parse_updated_from_html(html) == "Aug 1, 2026"
