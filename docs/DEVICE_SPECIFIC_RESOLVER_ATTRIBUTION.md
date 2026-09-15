# Device Specific resolver attribution

The v2.1 Device Specific production resolver is a project-owned,
metadata-only implementation. The application does **not** depend on or
import `goopdl` at runtime.

The proof of concept in #176 / PR #178 used `goopdl==1.2.1` to validate the
Google Play metadata protocol. Production protocol behaviour was
cross-checked against that MIT-licensed upstream implementation:

- https://github.com/Villoh/goopdl/tree/v1.2.1

The production resolver intentionally implements only the subset required
for an explicit Aurora-compatible dispenser and Google Play `/fdfe/details`
version metadata. It contains no purchase, delivery or APK-download path.

## Reference profiles

The initial production profile set contains only the two public reference
profiles that were coherently exercised by the PoC and are suitable for
versioned project resources:

- `android10_api29_oneplus8pro`
  - upstream: `goopdl/profiles/Yc.properties`
  - source: https://github.com/Villoh/goopdl/blob/v1.2.1/goopdl/profiles/Yc.properties
- `android13_api33_s20plus`
  - upstream: `goopdl/profiles/1Z.properties`
  - source: https://github.com/Villoh/goopdl/blob/v1.2.1/goopdl/profiles/1Z.properties

The upstream profile headers identify:

- `SPDX-FileCopyrightText: 2020 AuroraOSS`
- `SPDX-License-Identifier: GPL-3.0-or-later`

Those provenance and license fields remain embedded in the corresponding
JSON resources.

The sanitized Android 17 / API 37 `grizzly` profile remains PoC evidence
only. It is not promoted to the production registry because the successful
live test used a fuller temporary device profile than the privacy-sanitized
committed snapshot.
