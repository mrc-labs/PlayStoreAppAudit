# Device Specific resolver PoC

This directory contains the isolated Track C proof of concept from issue
#176. It is experimental tooling and deliberately lives outside the
production `playstore_app_audit` package.

Contract:

`package + reference profile + auth context -> versionName + versionCode`

The ordinary public Store lookup remains the first authority.

## Safety boundaries

- no production UI integration;
- no production resolver cache;
- no production dependency on `goopdl`;
- no hardcoded anonymous dispenser endpoint;
- no raw Google password support;
- no APK purchase, delivery or download;
- failures produce typed unresolved results;
- raw public Store Device Specific evidence remains preserved.

## Reference profiles

- Android 10 / API 29 / OnePlus 8 Pro
- Android 13 / API 33 / Samsung Galaxy S20+
- Android 17 / API 37 / Pixel 11 Pro `grizzly`

API29 and API33 are snapshots of the exact Aurora-derived profiles used
during the live `goopdl==1.2.1` experiment.

API37 is an allowlist-sanitized snapshot of the coherent physical profile
used during the successful Track C probe. Personal locale, timezone,
SIM/operator and identifier/account fields are not retained.

## Inspect profiles

```text
python -m tools.device_specific_poc.runner --list-profiles
```

## Anonymous laboratory mode

Live transport testing requires `goopdl==1.2.1` in an isolated environment.

Anonymous mode deliberately requires an explicit dispenser endpoint.

Plain HTTP is accepted only for loopback endpoints such as the validated `localhost` PoC. Remote dispenser endpoints must use HTTPS.


```text
python -m tools.device_specific_poc.runner \
  --package com.facebook.katana \
  --profile android13_api33_s20plus \
  --auth-mode anonymous \
  --dispenser-url http://localhost:3000/api/auth \
  --country CH \
  --language en
```

## Optional authenticated laboratory mode

Only these environment variables are read:

- `STORE_APP_AUDIT_POC_GOOGLE_EMAIL`
- `STORE_APP_AUDIT_POC_GOOGLE_AAS_TOKEN`

The AAS token must start with `aas_et/`.

No raw-password path exists.

See `docs/DEVICE_SPECIFIC_RESOLVER_POC.md`.
