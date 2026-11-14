"""Check rebuilt Qt locale data against the actual CLDR49 generator input."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path


def qualify(xml: Path) -> dict:
    from PySide6.QtCore import QDate, QLocale, QTimeZone

    root = ET.parse(xml).getroot()
    ids = {kind: {item.text: int(item.attrib['id']) for item in root.find(kind + 'List')}
           for kind in ('language', 'script', 'territory')}
    selected = {('Kako', 'Chad'), ('Kwasio', 'Equatorial Guinea'), ('Turkmen', 'Iran'),
                ('English', 'United States'), ('French', 'France'), ('Arabic', 'Egypt')}
    checked = []
    for row in root.find('localeList'):
        identity = (row.findtext('language'), row.findtext('territory'))
        if identity not in selected:
            continue
        locale = QLocale(QLocale.Language(ids['language'][identity[0]]),
                         QLocale.Script(ids['script'][row.findtext('script')]),
                         QLocale.Territory(ids['territory'][identity[1]]))
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
            assert locale.toDate(locale.toString(date, style), style) == date, identity
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
