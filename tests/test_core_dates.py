from playstore_app_audit.services.audit_engine import _parse_updated_from_html


def test_date_modified_is_accepted() -> None:
    html = '<script type="application/ld+json">{"dateModified":"2026-08-01"}</script>'
    assert _parse_updated_from_html(html) == "2026-08-01"


def test_date_published_is_not_latest_update() -> None:
    html = '<script type="application/ld+json">{"datePublished":"2018-04-12"}</script>'
    assert _parse_updated_from_html(html) == ""


def test_explicit_updated_field_is_accepted() -> None:
    html = '<script>{"updated":"Aug 1, 2026"}</script>'
    assert _parse_updated_from_html(html) == "Aug 1, 2026"
