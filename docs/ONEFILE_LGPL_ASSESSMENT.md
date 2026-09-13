# Nuitka onefile and LGPLv3 assessment

Status: release engineering decision for the v2.0 line.

## Conclusion

Nuitka `--mode=onefile` is not categorically prohibited by LGPLv3.

The current public release process uses Nuitka standalone mode and separate
Qt/PySide shared libraries. That is the compliance path already implemented,
documented and validated by the release tooling. It lets a recipient replace
compatible Qt libraries directly in the installed runtime.

LGPLv3 also permits a Combined Work through the alternative relink/recombine
path in section 4(d)(0). In principle, a onefile build can therefore be
acceptable if the distribution supplies all material and installation
information required for a recipient to reproduce the Combined Work using a
modified compatible version of the LGPL library and to run that modified
result.

This project is GPL-3.0-only and publishes its application source and build
logic, which makes that alternative path materially more practical than it
would be for a closed-source application. It does not make a onefile artifact
automatically compliant.

## Current v2.0 release rule

Do not replace the accepted standalone public package with onefile until an
end-to-end compliance proof exists.

A public onefile candidate must demonstrate all of the following before it can
replace standalone packaging:

1. The exact application source, Nuitka/build configuration and other
   Corresponding Application Code needed to reproduce the Combined Work are
   available for the released version.
2. The exact corresponding source for the distributed Qt/PySide/Shiboken
   LGPL components remains available under project control as required by the
   release legal process.
3. A documented rebuild/relink procedure can substitute a compatible modified
   Qt/PySide library version and produce a runnable modified Combined Work.
4. Installation information is sufficient to run that recombined result on the
   intended target system.
5. The legal validator is extended to test this relink/rebuild path rather than
   merely assuming that onefile extraction satisfies LGPLv3.
6. Third-party notices and license texts remain accessible to the recipient.
7. The resulting package is re-audited for every runtime component and license
   mapping exactly as the standalone package is today.

Until those gates pass, standalone remains the public distribution format.
Onefile may be investigated as an engineering candidate without being promoted
to a public release artifact.

## File-count reduction without changing the compliance model

The existing standalone pipeline already removes or avoids several unnecessary
runtime components, including Qt translations, the platform input-context
plugin, PIL runtime inclusion and the unused qpdf Qt plugin.

The legal bundle also already de-duplicates repeated Qt third-party license
payloads by SHA-256 under `licenses/qt-third-party/`. The remaining separate
community license texts, notices and source-availability documents are explicit
provenance/compliance inputs to the current validator. They should not be
blindly concatenated merely to reduce the visible file count.

Further standalone reduction should therefore focus first on demonstrably
unused runtime modules/plugins and on packaging presentation, while preserving
replaceable Qt shared libraries and the validated legal mappings.

## Primary references

- GNU LGPLv3: https://www.gnu.org/licenses/lgpl-3.0.html
- Qt LGPL text: https://doc.qt.io/qt-6/lgpl.html
- Qt open-source obligations: https://www.qt.io/development/open-source-lgpl-obligations
- Qt open-source download/licensing guidance: https://www.qt.io/development/download-open-source
- Nuitka onefile documentation: https://nuitka.net/doc/user-manual

This engineering assessment is not legal advice. A public switch in packaging
model remains a release gate requiring fresh legal/compliance validation.
