"""Check rebuilt Qt locale data against the actual CLDR49 generator input."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path


def locale_identifiers(root: ET.Element) -> dict[str, dict[str, int]]:
    ids = {kind: {item.text: int(item.attrib['id']) for item in root.find(kind + 'List')}
           for kind in ('language', 'script', 'territory')}
    # Qt's XML uses CLDR display names in the naming lists, but its enum
    # sentinel spellings in locale rows. These are explicit zero IDs,
    # not unknown-locale fallbacks.
    for kind, code, sentinel in [('script', 'Zzzz', 'AnyScript'),
                                 ('territory', 'ZZ', 'AnyTerritory')]:
        zero = root.find(kind + 'List/naming[@id="0"]')
        assert zero is not None and zero.attrib['code'] == code
        ids[kind][sentinel] = 0
    return ids


def qualify(xml: Path) -> dict:
    from PySide6.QtCore import QDate, QLocale, QTimeZone

    root = ET.parse(xml).getroot()
    ids = locale_identifiers(root)
    selected = {('Kako', 'Chad'), ('Kwasio', 'Equatorial Guinea'), ('Turkmen', 'Iran'),
                ('English', 'United States'), ('French', 'France'), ('Arabic', 'Egypt')}
    checked = []
    for row in root.find('localeList'):
        identity = (row.findtext('language'), row.findtext('territory'))
        if identity not in selected:
            continue
        locale = QLocale(QLocale.Language(ids['language'][identity[0]]),
                         QLocale.Script(ids['script'][row.findtext('script')]),
                         QLocale.Country(ids['territory'][identity[1]]))
        assert locale.language().value == ids['language'][identity[0]], identity
        assert locale.territory().value == ids['territory'][identity[1]], identity
        for field, actual in [('decimal', locale.decimalPoint()), ('group', locale.groupSeparator()),
                              ('am', locale.amText()), ('pm', locale.pmText()),
                              ('shortDateFormat', locale.dateFormat(QLocale.ShortFormat)),
                              ('longDateFormat', locale.dateFormat(QLocale.LongFormat)),
                              ('shortTimeFormat', locale.timeFormat(QLocale.ShortFormat))]:
            assert actual == (row.findtext(field) or ''), (identity, field, repr(actual), row.findtext(field))
        date = QDate(2026, 11, 14)
        for style in (QLocale.ShortFormat, QLocale.LongFormat):
            # Short formats may contain yy: Qt defaults to the 1900 century.
            # The fixture's explicit 2000 base makes its 2026 year unambiguous.
            rendered = locale.toString(date, style)
            parsed = locale.toDate(rendered, style, 2000)
            assert parsed == date, (identity, locale.dateFormat(style), rendered, parsed)
        checked.append({'language': identity[0], 'territory': identity[1],
                        'script': locale.script().value, 'name': locale.name()})
    assert {(item['language'], item['territory']) for item in checked} == selected
    zones = {}
    for name in ('Alberta Standard Time', 'British Columbia Standard Time', 'Manitoba Standard Time'):
        target = bytes(QTimeZone.windowsIdToDefaultIanaId(name.encode())).decode()
        assert target, ('Missing CLDR49 Windows zone', name)
        zones[name] = target
    return {'source_sha': os.environ.get('GITHUB_SHA'), 'xml_sha256': hashlib.sha256(xml.read_bytes()).hexdigest(),
            'locales': checked, 'windows_zones': zones,
            'result': 'PASS actual rebuilt Qt locale fields/date roundtrips/new Windows zone mappings'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = qualify(args.xml)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
