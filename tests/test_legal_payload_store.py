from pathlib import Path

from legal_payload_store import store_canonical_legal_payload


def test_identical_legal_payloads_are_stored_once(
    tmp_path: Path,
) -> None:
    licenses = tmp_path / "licenses"

    first_path, first_hash = store_canonical_legal_payload(
        licenses,
        b"same legal text\n",
    )

    second_path, second_hash = store_canonical_legal_payload(
        licenses,
        b"same legal text\n",
    )

    assert first_path == second_path
    assert first_hash == second_hash

    stored = list(
        (licenses / "qt-third-party").iterdir()
    )

    assert len(stored) == 1
    assert stored[0].read_bytes() == b"same legal text\n"


def test_different_legal_payloads_remain_distinct(
    tmp_path: Path,
) -> None:
    licenses = tmp_path / "licenses"

    first_path, first_hash = store_canonical_legal_payload(
        licenses,
        b"license A\n",
    )

    second_path, second_hash = store_canonical_legal_payload(
        licenses,
        b"license B\n",
    )

    assert first_path != second_path
    assert first_hash != second_hash

    stored = list(
        (licenses / "qt-third-party").iterdir()
    )

    assert len(stored) == 2


def test_legal_payload_is_preserved_byte_for_byte(
    tmp_path: Path,
) -> None:
    licenses = tmp_path / "licenses"

    payload = (
        b"\xef\xbb\xbfCopyright example\r\n"
        b"License text\r\n"
    )

    relative, _ = store_canonical_legal_payload(
        licenses,
        payload,
    )

    stored = tmp_path / relative

    assert stored.read_bytes() == payload