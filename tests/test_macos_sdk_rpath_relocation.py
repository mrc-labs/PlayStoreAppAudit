import pytest
from inspect_macos_package import validate_commands
from relocate_macos_sdk_rpaths import sdk_install_name, sdk_rpaths


def test_only_exact_qualified_sdk_library_rpaths_are_removed():
    prefix = '/Users/runner/work/_temp/native-sdk/prefix'
    values = [prefix + '/qt/lib', prefix + '/lib', '@loader_path',
              '/opt/homebrew/lib', '/System/Library/Frameworks',
              prefix + '-foreign/qt/lib', prefix + '/../foreign/lib']
    removed = sdk_rpaths(values, prefix)
    assert removed == values[:2]
    remaining = [value for value in values if value not in removed]
    assert '/opt/homebrew/lib' in remaining
    with pytest.raises(RuntimeError, match='absolute library origin'):
        validate_commands({'minimum_os': ['14.4'], 'rpaths': remaining,
                           'install_names': [], 'dependencies': []}, '15.0')


def test_supported_relocation_preserves_relative_load_paths_and_strict_origin_gate():
    prefix = '/Users/runner/sdk/prefix'
    values = [prefix + '/qt/lib', '@loader_path', '@executable_path/../Frameworks']
    removed = sdk_rpaths(values, prefix)
    commands = {'minimum_os': ['14.4'], 'rpaths': [p for p in values if p not in removed],
                'install_names': ['@rpath/libQt6Core.6.dylib'],
                'dependencies': ['/System/Library/Frameworks/Security.framework/Security']}
    validate_commands(commands, '15.0')
    with pytest.raises(RuntimeError, match='absolute library origin'):
        validate_commands({**commands, 'dependencies': [prefix + '/lib/libcrypto.4.dylib']}, '15.0')


def test_rpath_normalization_never_expands_removal_to_other_directories():
    prefix = '/Users/runner/sdk/prefix'
    assert sdk_rpaths([prefix + '/qt/bin/../lib', prefix + '/qt/lib'], prefix) == [prefix + '/qt/bin/../lib', prefix + '/qt/lib']
    assert sdk_rpaths([prefix + '/qt/lib/../../../../foreign/lib'], prefix) == []


def test_only_owned_same_library_install_id_becomes_portable():
    prefix = '/Users/runner/sdk/prefix'
    assert sdk_install_name([prefix + '/openssl/lib/libcrypto.4.dylib'], prefix, 'libcrypto.4.dylib') == '@rpath/libcrypto.4.dylib'
    assert sdk_install_name(['@rpath/libcrypto.4.dylib'], prefix, 'libcrypto.4.dylib') is None
    assert sdk_install_name(['/opt/homebrew/lib/libcrypto.4.dylib'], prefix, 'libcrypto.4.dylib') is None
    with pytest.raises(RuntimeError, match='differs from packaged library'):
        sdk_install_name([prefix + '/lib/libffi.8.dylib'], prefix, 'libffi.7.dylib')
