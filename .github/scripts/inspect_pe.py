from __future__ import annotations

import argparse
import struct
from pathlib import Path

MACHINE_NAMES = {
    0x014C: "IMAGE_FILE_MACHINE_I386",
    0x01C0: "IMAGE_FILE_MACHINE_ARM",
    0x01C4: "IMAGE_FILE_MACHINE_ARMNT",
    0x0200: "IMAGE_FILE_MACHINE_IA64",
    0x8664: "IMAGE_FILE_MACHINE_AMD64",
    0xAA64: "IMAGE_FILE_MACHINE_ARM64",
}


def read_pe_machine(path: Path) -> int:
    """Read the COFF machine field from a Windows PE image."""
    with path.open("rb") as executable:
        dos_header = executable.read(64)
        if len(dos_header) != 64 or dos_header[:2] != b"MZ":
            raise ValueError("missing or truncated DOS header")

        pe_offset = struct.unpack_from("<I", dos_header, 0x3C)[0]
        if pe_offset > path.stat().st_size - 6:
            raise ValueError("PE header offset is outside the file")

        executable.seek(pe_offset)
        if executable.read(4) != b"PE\0\0":
            raise ValueError("missing PE signature")

        machine_bytes = executable.read(2)
        if len(machine_bytes) != 2:
            raise ValueError("truncated COFF header")
        return struct.unpack("<H", machine_bytes)[0]


def describe_machine(machine: int) -> str:
    name = MACHINE_NAMES.get(machine, "UNKNOWN_PE_MACHINE")
    return f"{name} (0x{machine:04X})"


def machine_value(value: str) -> int:
    aliases = {name: machine for machine, name in MACHINE_NAMES.items()}
    normalised = value.strip().upper()
    if normalised in aliases:
        return aliases[normalised]
    try:
        machine = int(normalised, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid PE machine value: {value}") from exc
    if not 0 <= machine <= 0xFFFF:
        raise argparse.ArgumentTypeError(f"PE machine value is outside UInt16: {value}")
    return machine


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and optionally assert a PE machine type.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--expect", type=machine_value)
    args = parser.parse_args()

    try:
        actual = read_pe_machine(args.path)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{args.path}: {exc}\n")

    description = describe_machine(actual)
    if args.expect is not None and actual != args.expect:
        parser.exit(
            1,
            f"{args.path}: expected {describe_machine(args.expect)}, found {description}\n",
        )

    print(description)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
