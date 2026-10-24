"""Bounded native API feasibility probe; never patch or adopt a Python runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

from inspect_pe import read_pe_machine

SOURCE_URL = "https://raw.githubusercontent.com/python/cpython/v3.14.9/Modules/_ssl.c"
SOURCE_SHA256 = "429462fe513155551219d285a605a3849b15503dbbc5425c529ac4f728a4402a"
METHODS = ("TLSv1_method", "TLSv1_1_method", "TLSv1_2_method")


def classify_link(returncode: int, output: str) -> str:
    if returncode == 0:
        return "linkable"
    if "LNK2019" in output and any(re.search(r"\b" + name + r"\b", output) for name in METHODS):
        return "blocked-removed-legacy-method-api"
    raise RuntimeError("Unexpected compiler/link failure; this is not evidence of the expected API constraint")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if os.environ.get("VSCMD_ARG_HOST_ARCH") != "arm64" or os.environ.get("VSCMD_ARG_TGT_ARCH") != "arm64":
        raise RuntimeError("This probe requires native ARM64 MSVC host and target")
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
        source = response.read()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("CPython source provenance mismatch")
    (root / "cpython-3.14.9-ssl.c").write_bytes(source)
    for name in METHODS:
        if f"method = {name}();".encode() not in source:
            raise RuntimeError("The selected CPython source no longer has the expected API dependency")
    prefix = Path(os.environ["OPENSSL_DIR"])
    libraries = [str(prefix / "lib" / name) for name in ("libssl.lib", "libcrypto.lib")]
    common = ["cl", "/nologo", "/MD", f"/I{prefix / 'include'}"]
    link = ["/link", *libraries, "ws2_32.lib", "crypt32.lib", "advapi32.lib", "user32.lib", "gdi32.lib", "bcrypt.lib"]
    sources = {
        "control": '#include <openssl/ssl.h>\nint main(void) { return TLS_method() == 0; }\n',
        "legacy": "#include <openssl/ssl.h>\n" + "\n".join(
            f"extern const SSL_METHOD *{name}(void);" for name in METHODS
        ) + "\nint main(void) { const SSL_METHOD *m = 0;\n" + "\n".join(
            f"#if defined({version}_VERSION) && !defined(OPENSSL_NO_{version}) && !defined(OPENSSL_NO_{version}_METHOD)\n"
            f"m = {name}();\n#endif" for version, name in zip(("TLS1", "TLS1_1", "TLS1_2"), METHODS, strict=True)
        ) + "\nreturn m == 0; }\n",
    }
    outcomes = {}
    for name, code in sources.items():
        path = root / f"{name}.c"
        path.write_text(code, encoding="utf-8")
        command = [*common, path.name, f"/Fe{name}.exe", *link]
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
        text = result.stdout + result.stderr
        (root / f"{name}-link.txt").write_text(text, encoding="utf-8")
        outcomes[name] = {"command": command, "returncode": result.returncode,
                          "result": classify_link(result.returncode, text)}
    if outcomes["control"]["result"] != "linkable":
        raise RuntimeError("Modern OpenSSL control link failed")
    if read_pe_machine(root / "control.exe") != 0xAA64:
        raise RuntimeError("Probe control executable is not ARM64")
    subprocess.run([str(root / "control.exe")], check=True)
    if outcomes["legacy"]["result"] != "blocked-removed-legacy-method-api":
        raise RuntimeError("The bounded probe did not reproduce the documented CPython 3.14 API constraint")
    report = {
        "scope": "non-release-native-api-feasibility-not-a-python-build",
        "source_sha": os.environ.get("GITHUB_SHA"), "cpython_version": "3.14.9",
        "cpython_source_url": SOURCE_URL, "cpython_source_sha256": SOURCE_SHA256,
        "openssl": "4.0.3", "architecture": "ARM64", "outcomes": outcomes,
        "decision": "BLOCKED: unmodified CPython references removed OpenSSL methods; source adaptation requires scope/MINOR review.",
        "limits": "This tests the guarded method API dependency, not a full CPython build or _hashlib qualification. No runtime is adopted.",
        "upstream": "https://github.com/python/cpython/pull/146403",
    }
    (root / "feasibility.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
