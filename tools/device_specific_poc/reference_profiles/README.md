# Reference profile provenance

The Android 10 / API 29 `Yc` and Android 13 / API 33 `1Z`
profile snapshots in this directory are transformed snapshots of
AuroraOSS device-profile data distributed with `goopdl==1.2.1`.

Sources:

- `Yc.properties`
  - https://github.com/Villoh/goopdl/blob/v1.2.1/goopdl/profiles/Yc.properties
- `1Z.properties`
  - https://github.com/Villoh/goopdl/blob/v1.2.1/goopdl/profiles/1Z.properties

Upstream file headers identify:

- SPDX-FileCopyrightText: 2020 AuroraOSS
- SPDX-License-Identifier: GPL-3.0-or-later

The snapshots are retained only for the isolated Device Specific
resolver proof of concept.

`android17_api37_grizzly.json` is an allowlist-sanitized,
physical-device-derived reference profile captured for this PoC.
Personal locale, timezone, SIM/operator and account/device
identifiers intentionally excluded by the sanitizer are not retained.
