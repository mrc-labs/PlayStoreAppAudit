"""Install hash-bound pip using verified stdlib HTTPS, then offline pip only."""
from __future__ import annotations

import hashlib
import json
import ssl
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

VERSION = "26.3"
URL = "https://files.pythonhosted.org/packages/07/25/ee8c38ae72d66b844ce8eb9711ba905dba21ca1a8a0c960057c41cd23337/pip-26.3-py3-none-any.whl"
SHA256 = "f3b60b20ffaadd4415ed7957212a38ac63fa4c5fa375bd0f4a797777940fad13"


def download_wheel(destination: Path) -> Path:
    context = ssl.create_default_context()
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    wheel = destination / f"pip-{VERSION}-py3-none-any.whl"
    digest = hashlib.sha256()
    with urllib.request.urlopen(URL, context=context, timeout=90) as response:
        if not response.geturl().startswith("https://"):
            raise ValueError("pip bootstrap HTTPS downgrade rejected")
        with wheel.open("wb") as output:
            while block := response.read(1024 * 1024):
                digest.update(block)
                output.write(block)
    if digest.hexdigest() != SHA256:
        raise ValueError("pip bootstrap SHA256 mismatch; nothing installed")
    return wheel


def bootstrap(destination: Path) -> None:
    wheel = download_wheel(destination)
    # The old installer never contacts an index or dependency server. Only the
    # standard library downloads bytes; pip installs the verified local wheel.
    subprocess.run([
        sys.executable, "-m", "pip", "--isolated", "--disable-pip-version-check",
        "install", "--no-index", "--no-deps", "--no-cache-dir", "--no-input",
        "--upgrade", str(wheel),
    ], check=True)
    subprocess.run([sys.executable, "-c",
        "import pip,pip._vendor.urllib3,pip._vendor.certifi,json;"
        "assert pip.__version__=='26.3';assert pip._vendor.urllib3.__version__=='2.8.0';"
        "assert pip._vendor.certifi.__version__=='2026.10.23';"
        "print(json.dumps(dict(pip=pip.__version__,urllib3=pip._vendor.urllib3.__version__,"
        "certifi=pip._vendor.certifi.__version__,bootstrap='stdlib verified HTTPS/hash, offline install')))"
    ], check=True)
    print(json.dumps({"wheel": wheel.name, "url": URL, "sha256": SHA256}), flush=True)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="psaa-pip-bootstrap-") as directory:
        bootstrap(Path(directory))
