from __future__ import annotations

import pytest
from probe_adb_linux_arm64 import within_floor


@pytest.mark.parametrize('versions', [['GLIBC_2.39'], ['GLIBCXX_3.4.33']])
def test_native_adb_rejects_dependency_floor_increases(versions):
    with pytest.raises(ValueError, match='exceeds accepted ARM64 ABI floor'):
        within_floor(versions)


def test_native_adb_accepts_the_existing_arm64_floors():
    within_floor(['GLIBC_2.17', 'GLIBC_2.38', 'GLIBCXX_3.4.32', 'CXXABI_1.3.13'])
