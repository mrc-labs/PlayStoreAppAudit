import pytest
from inspect_macos_package import validate_commands


def test_package_deployment_measures_dependencies_and_rejects_build_origin():
    commands = {'minimum_os': ['14.4'], 'rpaths': ['@loader_path'],
                'install_names': ['@rpath/libQt6Core.dylib'], 'dependencies': ['/usr/lib/libSystem.B.dylib']}
    validate_commands(commands, '15.0')
    with pytest.raises(RuntimeError, match='deployment ceiling'):
        validate_commands({**commands, 'minimum_os': ['16.0']}, '15.0')
    with pytest.raises(RuntimeError, match='absolute library origin'):
        validate_commands({**commands, 'rpaths': ['/Users/runner/private-sdk/lib']}, '15.0')
    vendor = {**commands, 'dependencies': ['@rpath/libssl.3.dylib']}
    validate_commands(vendor, '15.0')
    validate_commands(vendor, '15.0', expected_openssl_major=3)
    with pytest.raises(RuntimeError, match='provider contract mismatch'):
        validate_commands(vendor, '15.0', expected_openssl_major=4)
    with pytest.raises(RuntimeError, match='provider contract mismatch'):
        validate_commands({**commands, 'dependencies': ['@rpath/libcrypto.4.dylib']},
                          '15.0', expected_openssl_major=3)
