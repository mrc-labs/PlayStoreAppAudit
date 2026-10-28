"""Verify the selected native source backend without compiling an app package."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import sysconfig
import tomllib
from pathlib import Path
from typing import Any

from inspect_pe import read_pe_machine

EXPECTED_OPENSSL = "4.0.3"
EXPECTED_SOURCE_SHA256 = "325b5c806167c13b40b1ffeadfe0248197c00eccc4cf123ec1e28d2d2fd216d9"


def validate_imports(text: str) -> None:
    """Reject dynamic OpenSSL or a missing dynamic MSVC runtime dependency."""
    if re.search(r"(?:libcrypto|libssl|ssleay|libeay)[^\s]*\.dll", text, re.IGNORECASE):
        raise ValueError("OpenSSL must be statically linked")
    if not re.search(r"(?:vcruntime\d+|ucrtbase|api-ms-win-crt-[^\s]+)\.dll", text, re.IGNORECASE):
        raise ValueError("Dynamic MSVC CRT import is missing")


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_source(evidence: Path) -> dict[str, Any]:
    source = json.loads((evidence / "source-provenance.json").read_text(encoding="utf-8-sig"))
    if source["version"] != EXPECTED_OPENSSL or source["source_sha256"] != EXPECTED_SOURCE_SHA256:
        raise ValueError("Unexpected OpenSSL source selection")
    url = f"https://github.com/openssl/openssl/releases/download/openssl-{EXPECTED_OPENSSL}/openssl-{EXPECTED_OPENSSL}.tar.gz"
    if source["source_url"] != url or source["linkage"] != "static" or source["crt"] != "dynamic":
        raise ValueError("Unexpected source provenance or linkage")
    archive = evidence / f"openssl-{EXPECTED_OPENSSL}.tar.gz"
    if file_sha256(archive) != EXPECTED_SOURCE_SHA256:
        raise ValueError("Retained OpenSSL source checksum mismatch")
    license_text = (evidence / "LICENSE.txt").read_text(encoding="utf-8")
    if "Apache License" not in license_text or "Version 2.0" not in license_text:
        raise ValueError("OpenSSL license evidence is missing")
    return source


def stage_material(evidence: Path, package_dir: Path, release_dir: Path) -> None:
    """Retain source evidence and ship the independently linked backend's notices."""
    validate_source(evidence)
    destination = package_dir / "third-party-build" / "openssl-cryptography"
    destination.mkdir(parents=True, exist_ok=False)
    for name in ("LICENSE.txt", "source-provenance.json", "cryptography-verification.json"):
        shutil.copyfile(evidence / name, destination / name)
    shutil.copytree(evidence / "cryptography-licenses", destination / "cryptography-licenses")
    # This permissive source is retained with CI legal material; mandatory Qt/MPL
    # corresponding-source selection and strict validation remain unchanged.
    shutil.copytree(evidence, release_dir / "prerequisites" / "openssl-cryptography")


def validate_install_report(evidence: Path, version: str) -> dict[str, Any]:
    report = json.loads((evidence / "cryptography-install.json").read_text(encoding="utf-8"))
    entries = [item for item in report["install"] if item["metadata"]["name"] == "cryptography"]
    if len(entries) != 1 or entries[0]["metadata"]["version"] != version:
        raise ValueError("Missing exact cryptography source installation report")
    download = entries[0]["download_info"]
    if not (download["url"].startswith("https://files.pythonhosted.org/") and
            download["url"].endswith(f"/cryptography-{version}.tar.gz")):
        raise ValueError("cryptography must be rebuilt from the official source archive")
    if not re.fullmatch(r"[0-9a-f]{64}", download["archive_info"]["hashes"]["sha256"]):
        raise ValueError("cryptography source hash is missing")
    return download


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path)
    parser.add_argument("--release-dir", type=Path)
    args = parser.parse_args()
    if bool(args.package_dir) != bool(args.release_dir):
        parser.error("--package-dir and --release-dir must be supplied together")
    evidence = args.evidence_dir
    source = validate_source(evidence)
    if platform.machine().upper() != "ARM64" or sysconfig.get_config_var("Py_GIL_DISABLED"):
        raise RuntimeError("A native GIL-enabled ARM64 runtime is required")

    from cryptography.hazmat.backends.openssl.backend import backend
    from cryptography.hazmat.bindings import _rust
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    expected_crypto = next(r.split("==")[1] for r in project["project"]["dependencies"]
                          if r.startswith("cryptography=="))
    if metadata.version("cryptography") != expected_crypto:
        raise RuntimeError("cryptography does not match the project pin")
    crypto_source = validate_install_report(evidence, expected_crypto)
    actual_backend = backend.openssl_version_text()
    if not actual_backend.startswith(f"OpenSSL {EXPECTED_OPENSSL} "):
        raise RuntimeError(f"Unexpected effective cryptography backend: {actual_backend}")
    extension = Path(_rust.__file__)
    tool = Path(os.environ["OPENSSL_DIR"]) / "bin" / "openssl.exe"
    for binary in (Path(sys.executable), extension, tool):
        if read_pe_machine(binary) != 0xAA64:
            raise RuntimeError(f"Non-ARM64 PE: {binary}")
    for name, binary in (("openssl", tool), ("cryptography", extension)):
        imports = subprocess.run(["dumpbin", "/imports", str(binary)], check=True,
                                 capture_output=True, text=True).stdout
        validate_imports(imports)
        (evidence / f"{name}-imports.txt").write_text(imports, encoding="utf-8")

    message = b"Store App Audit native ARM64 OpenSSL diagnostic"
    key = ec.generate_private_key(ec.SECP256R1())
    algorithm = ec.ECDSA(hashes.SHA256())
    signature = key.sign(message, algorithm)
    key.public_key().verify(signature, message, algorithm)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    key.public_key().verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
    cipher = AESGCM(AESGCM.generate_key(bit_length=256))
    nonce = os.urandom(12)
    assert cipher.decrypt(nonce, cipher.encrypt(nonce, message, None), None) == message

    licenses = evidence / "cryptography-licenses"
    licenses.mkdir(exist_ok=True)
    dist = metadata.distribution("cryptography")
    copied = []
    for path in dist.files or ():
        if path.name.startswith(("LICENSE", "NOTICE")):
            shutil.copyfile(dist.locate_file(path), licenses / path.name)
            copied.append(path.name)
    if not copied:
        raise RuntimeError("cryptography distribution license material is missing")
    report = {
        "scope": "openssl-cryptography-prerequisite", "source_sha": os.environ.get("GITHUB_SHA"),
        "python": platform.python_version(), "python_ssl_distinct_provider": ssl.OPENSSL_VERSION,
        "cryptography": dist.version, "cryptography_backend": actual_backend,
        "cryptography_source": crypto_source,
        "extension_sha256": file_sha256(extension),
        "pe_machine": "0xAA64", "openssl_linkage": "static", "msvc_crt": "dynamic",
        "source": source, "cryptography_license_files": sorted(copied),
        "functional_checks": ["ECDSA P-256/SHA-256", "RSA-2048/SHA-256", "AES-256-GCM roundtrip"],
    }
    (evidence / "cryptography-verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.package_dir:
        stage_material(evidence, args.package_dir, args.release_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
