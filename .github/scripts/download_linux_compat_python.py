#!/usr/bin/env python3
"""Fetch the official x64 Ubuntu 22 distribution of the already-resolved patch.

The build host remains Ubuntu 24.04. Never select a different Python patch or
accept an unofficial distribution to lower the target ABI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path

MANIFEST_URL = "https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json"


def select_distribution(manifest: list[dict], version: str) -> dict:
    if not re.fullmatch(r"3\.14\.\d+", version):
        raise ValueError("Compatibility Python must be a stable, full 3.14 patch")
    matches = [
        file
        for release in manifest
        if release["version"] == version and release["stable"]
        for file in release["files"]
        if file["platform"] == "linux"
        and file["platform_version"] == "22.04"
        and file["arch"] == "x64"
        and file["filename"] == f"python-{version}-linux-22.04-x64.tar.gz"
    ]
    if len(matches) != 1:
        raise ValueError("Exactly one official same-patch Ubuntu 22 x64 distribution is required")
    file = matches[0]
    prefix = "https://github.com/actions/python-versions/releases/download/"
    if not file["download_url"].startswith(prefix):
        raise ValueError("Unofficial Python distribution URL")
    return file


def request(url: str) -> urllib.request.Request:
    headers = {"User-Agent": "Store-App-Audit-release", "Accept": "application/vnd.github+json"}
    if url.startswith("https://api.github.com/"):
        headers["X-GitHub-Api-Version"] = "2026-03-10"
        if os.environ.get("GH_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    return urllib.request.Request(url, headers=headers)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    with urllib.request.urlopen(request(MANIFEST_URL), timeout=120) as response:
        manifest = json.load(response)
    file = select_distribution(manifest, args.version)
    tag = file["download_url"].split("/download/", 1)[1].split("/", 1)[0]
    api = "https://api.github.com/repos/actions/python-versions/releases/tags/" + tag
    with urllib.request.urlopen(request(api), timeout=120) as response:
        release = json.load(response)
    assets = [asset for asset in release["assets"] if asset["name"] == file["filename"]]
    if len(assets) != 1 or assets[0]["browser_download_url"] != file["download_url"]:
        raise RuntimeError("Official release asset does not match the manifest")
    asset = assets[0]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or ""):
        raise RuntimeError("Official Python asset SHA-256 is missing")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive = args.output_dir / "python.tar.gz"
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request(file["download_url"]), timeout=120) as response, archive.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    if "sha256:" + digest.hexdigest() != asset["digest"] or size != asset["size"]:
        raise RuntimeError("Official Python archive checksum/size mismatch")
    evidence = {"version": args.version, "manifest": MANIFEST_URL, "asset": asset,
                "observed_sha256": digest.hexdigest(), "source_sha": os.environ.get("GITHUB_SHA")}
    (args.output_dir / "python-distribution.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(file["download_url"], digest.hexdigest())


if __name__ == "__main__":
    main()
