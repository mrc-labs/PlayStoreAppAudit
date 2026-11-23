"""Select the approved portable Python PEM for the packaged macOS runtime."""
from __future__ import annotations

import os
import ssl
import sys
from pathlib import Path


def configure_packaged_python_trust(*, packaged: bool) -> None:
    # The controlled OpenSSL build has a build-prefix default PEM. The packaged
    # application deliberately uses its shipped certifi PEM at the runtime path.
    # Windows keeps its OS roots; Linux keeps its qualified OS CA directories.
    if not packaged or sys.platform != "darwin":
        return
    if "SSL_CERT_FILE" in os.environ or "SSL_CERT_DIR" in os.environ:
        return  # Preserve explicit operator trust configuration; never bypass it.
    import certifi

    bundle = Path(certifi.where()).resolve(strict=True)
    if not bundle.is_file():
        raise RuntimeError("Packaged HTTPS certificate bundle is missing")
    # Reject missing/malformed data before selecting it as the process default.
    ssl.create_default_context(cafile=str(bundle))
    os.environ["SSL_CERT_FILE"] = str(bundle)
