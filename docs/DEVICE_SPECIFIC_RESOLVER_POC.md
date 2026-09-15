# Device Specific Resolver PoC

Issue: #176

Status: **GO for a separate production-integration issue.**

This document records the isolated Track C proof of concept for resolving
profile-specific Google Play version metadata after the normal Store path
reports a recognized Device Specific value.

Production UI integration remains out of scope for this PoC.

## Contract

Demonstrated contract:

`package + reference profile + auth context -> versionName + versionCode`

The existing public Store lookup remains the first pass and its raw result
remains authoritative evidence.

Resolver enrichment is eligible only when the ordinary Store path explicitly
returns one of the established Device Specific values:

- `Varies with device`
- `Varies by device`
- `Varies`

It does not run for ordinary versions, missing metadata, Unknown, Not Found,
transport failures or unrelated anomaly states.

Resolver evidence is additive. A failed attempt leaves the existing
Device Specific result unchanged.

## Reference matrix

| Profile | Android | API | Source |
| --- | ---: | ---: | --- |
| OnePlus 8 Pro EEA | 10 | 29 | Aurora-derived `Yc`, `goopdl==1.2.1` |
| Samsung Galaxy S20+ | 13 | 33 | Aurora-derived `1Z`, `goopdl==1.2.1` |
| Pixel 11 Pro `grizzly` | 17 | 37 | Sanitized physical-device-derived profile |

The committed API37 profile excludes locale, timezone, SIM/operator and
identifier/account context.

## Discovery evidence

On 2026-09-15 the normal public Store path was applied to 312 third-party
Google Play-installed packages using Store country CH and language `en`.

Results:

- 73 packages were recognized as Device Specific;
- 1 normal public Store lookup failed;
- 73 packages qualified for experimental resolver enrichment.

## Profile-sensitive evidence

The differential scan found three profile-sensitive cases within seven
candidates.

### Facebook

`com.facebook.katana`

- API29: `577.0.0.50.72`, versionCode `474426251`
- API33: `577.0.0.50.72`, versionCode `474426253`
- API37: `577.0.0.50.72`, versionCode `474426253`

This proves that versionCode must be preferred when available because the
visible versionName can remain identical while Play targets a different
versionCode.

### Adobe Scan

`com.adobe.scan.android`

- API29: `26.04.30`, versionCode `261562461`
- API33: `26.09.03`, versionCode `262843364`
- API37: `26.09.03`, versionCode `262843364`

### eBay

`com.ebay.mobile`

- API29: `6.242.0.2`, versionCode `6242002`
- API33: `6.273.0.1`, versionCode `6273001`
- API37: `6.273.0.1`, versionCode `6273001`

Differential scan summary:

- 7 candidates scanned;
- 6 fully resolved on all three profiles;
- 3 identical versionCode cases;
- 3 different versionCode cases;
- 1 availability/incomplete-evidence case;
- 20 resolved individual profile lookups;
- 1 malformed/incomplete metadata response.

**PROFILE-SENSITIVE VERSION GATE: PASS.**

## Authentication evidence

### Authenticated laboratory path

A temporary browser OAuth session was exchanged for an AAS token and used
to establish Play sessions for API29, API33 and API37.

No raw Google password was persisted.

### Anonymous client path

The official Aurora Dispenser source was tested from TEMP at commit:

`191ec8777c3925349223f0836d1ae3af472b64b8`

It was run only on `localhost:3000`.

The client process contained no Google email and no Google AAS token.

Three dispenser requests were made, exactly one per profile.

The anonymous path reproduced the same Facebook, Adobe Scan and eBay
profile-specific results.

No request was made to the public AuroraOSS dispenser.

The temporary account file was deleted and the local dispenser stopped
after the test.

**ANONYMOUS RESOLVER GATE: PASS.**

## Failure/fallback evidence

The offline matrix exercised:

- missing dispenser;
- dispenser HTTP 403;
- dispenser HTTP 429;
- dispenser HTTP 503;
- dispenser timeout;
- connection refusal;
- malformed JSON;
- missing auth token;
- expired/invalid Play bearer;
- Play HTTP 401;
- Play rate limiting;
- Play HTTP 503;
- Play timeout;
- package unavailable for profile;
- malformed Play metadata.

Every failure returned typed unresolved evidence with no fabricated
versionName or versionCode.

Every unresolved case preserved the existing Device Specific result.

Ordinary Store versions remained authoritative.

**TRACK C FAILURE/FALLBACK GATE: PASS.**

## Network and privacy boundaries

The tested resolver performs metadata-only Play detail requests.

It requires no:

- APK purchase;
- APK delivery;
- APK-byte download.

Safe result files contained no:

- Google email;
- AAS token;
- bearer token;
- GSF ID;
- dummy account identity.

## Repository implementation

`tools/device_specific_poc/` is experimental tooling only.

It is deliberately outside the production `playstore_app_audit` package.

`goopdl` is not added to production dependencies.

The live transport adapter imports `goopdl` lazily.

Anonymous mode has no default dispenser endpoint.

Plain HTTP is accepted only for loopback/local laboratory endpoints. Any remote dispenser context must use HTTPS.

Optional authenticated laboratory mode reads only:

- `STORE_APP_AUDIT_POC_GOOGLE_EMAIL`
- `STORE_APP_AUDIT_POC_GOOGLE_AAS_TOKEN`

There is no raw-password path.

## Future resolver cache identity

Persistent caching is not required by the PoC.

Any production cache should be separate from ordinary public Store cache
semantics and include at least:

`resolver schema + package + profile ID + profile hash + country + language + auth mode + auth context + protocol revision`

## Production recommendation

The evidence supports **GO** for a separate production-integration issue.

Recommended production flow:

1. keep the existing public Store first pass unchanged;
2. trigger resolver enrichment only for recognized Device Specific results;
3. preserve the raw Store Device Specific value;
4. prefer anonymous resolution only when an approved explicit dispenser
   context is available;
5. keep Google/AAS authentication optional and Advanced-only if promoted;
6. prefer versionCode/longVersionCode over versionName when available;
7. keep installed version, Play-deliverable version and raw Store evidence
   semantically separate;
8. on any resolver failure, fall back conservatively to Device Specific;
9. use a dedicated resolver cache;
10. do not add APK purchase or download to this feature.

## Not authorized by this PoC

This PoC does not itself authorize:

- production Qt/UI integration;
- production settings UI;
- persistent Google credential storage;
- a hardcoded third-party dispenser;
- production resolver cache migration;
- changes to the normal Store scraping semantics;
- APK purchase or download;
- CLI/headless work;
- screenshot work;
- release/version bump work.
