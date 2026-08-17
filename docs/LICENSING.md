# Licensing model

## Project code

Play Store App Audit's own code is licensed to the public under the GNU
General Public License version 3 only (`GPL-3.0-only`).

The complete GPLv3 text is in the repository root [LICENSE](../LICENSE).

GPLv3 permits commercial use. A business does not need a separate commercial
license simply because it uses the software commercially. The GPL's conditions
apply when GPL-covered copies or modified versions are conveyed.

## Alternative commercial licensing

The project owner may also offer Play Store App Audit's own code under
separate proprietary or commercial terms.

The commercial option is intended for organisations or products that need
rights beyond GPLv3, for example proprietary redistribution or integration
where GPLv3 obligations are not acceptable.

See [COMMERCIAL-LICENSING.md](../COMMERCIAL-LICENSING.md).

## Contributions

The project uses a Contributor License Agreement for material contributions.
Contributors retain copyright, while granting the project owner the rights
needed to continue both GPLv3 and alternative commercial licensing.

See [CLA.md](../CLA.md) and [CONTRIBUTING.md](../CONTRIBUTING.md).

## Third-party software

Third-party components are not relicensed under Play Store App Audit's GPL or
commercial license. They remain under their respective licenses.

The Windows standalone package can include LGPL-, GPL-, MPL-, Apache-, MIT-,
BSD- and PSF-licensed components. Release packages therefore include
third-party notices and corresponding-source material where required.

Qt/PySide shared libraries and plugins remain separate files in the standalone
distribution. The packaging validator excludes unused or unwanted components
including Qt Virtual Keyboard and validates the release runtime contents.

## Corresponding source

For public binary releases, corresponding-source obligations for distributed
third-party copyleft components must be satisfied using the exact versions
included in the release. Release publication is blocked until the required
source assets and license notices have been validated against the final CI
artifact.

## Commercial license boundaries

An alternative commercial license from the Play Store App Audit copyright
holder applies only to rights that the copyright holder can grant. It does not
grant alternative rights to Qt, PySide6, Shiboken6, CPython, OpenSSL or any
other third-party component.

Organisations using a commercially licensed edition remain responsible for
complying with the licenses of third-party components shipped with that
edition.

## Trademarks and affiliation

Third-party product names and trademarks are used descriptively. Play Store
App Audit is not affiliated with or endorsed by Google, Android, Google Play,
The Qt Company or other third-party vendors whose products or services are
referenced by the application.
