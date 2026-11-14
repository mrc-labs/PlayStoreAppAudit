#!/usr/bin/env bash
# Shared native Intel prerequisite for package builds and non-release inventory.
set -euo pipefail
echo "DEVELOPER_DIR=$DEVELOPER_DIR" >> "$GITHUB_ENV"
echo "MACOSX_DEPLOYMENT_TARGET=$MACOSX_DEPLOYMENT_TARGET" >> "$GITHUB_ENV"
# Homebrew's current rustup has no Intel macOS bottle. Use the
# official native installer in an isolated runner tool directory.
export CARGO_HOME="$RUNNER_TEMP/cryptography-cargo"
export RUSTUP_HOME="$RUNNER_TEMP/cryptography-rustup"
rust_installer="$RUNNER_TEMP/rustup-init"
curl --fail --location --retry 3 --output "$rust_installer" \
  https://static.rust-lang.org/rustup/archive/1.29.2/x86_64-apple-darwin/rustup-init
echo "b9610730ddeef52765723847866fd1e3540b2bf7d5ab0c324aa143a5edf25ba0  $rust_installer" | shasum -a 256 -c -
chmod +x "$rust_installer"
"$rust_installer" -y --no-modify-path --profile minimal --default-toolchain 1.99.1
export PATH="$CARGO_HOME/bin:$PATH"
echo "CARGO_HOME=$CARGO_HOME" >> "$GITHUB_ENV"
echo "RUSTUP_HOME=$RUSTUP_HOME" >> "$GITHUB_ENV"
echo "$CARGO_HOME/bin" >> "$GITHUB_PATH"
rustup --version
rustc --version
cargo --version
[[ "$(rustup --version)" == "rustup 1.29.2 "* ]]
[[ "$(rustc --version)" == "rustc 1.99.1 "* ]]
# Build static OpenSSL with the existing deployment target rather
# than import a host-OS-specific Homebrew binary into the package.
work="$RUNNER_TEMP/openssl-4.0.3-source"
prefix="$RUNNER_TEMP/openssl-4.0.3-static"
mkdir -p "$work"
cd "$work"
curl --fail --location --retry 3 --output openssl-4.0.3.tar.gz \
  https://github.com/openssl/openssl/releases/download/openssl-4.0.3/openssl-4.0.3.tar.gz
echo '325b5c806167c13b40b1ffeadfe0248197c00eccc4cf123ec1e28d2d2fd216d9  openssl-4.0.3.tar.gz' | shasum -a 256 -c -
tar -xzf openssl-4.0.3.tar.gz
cd openssl-4.0.3
./Configure darwin64-x86_64-cc no-shared --prefix="$prefix" \
  "-mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET"
make -j "$(sysctl -n hw.ncpu)"
make install_sw
"$prefix/bin/openssl" version
test "$(lipo -archs "$prefix/bin/openssl")" = x86_64
echo "OPENSSL_DIR=$prefix" >> "$GITHUB_ENV"
echo 'OPENSSL_STATIC=1' >> "$GITHUB_ENV"
echo 'OPENSSL_NO_VENDOR=1' >> "$GITHUB_ENV"
echo 'PIP_NO_BINARY=cryptography' >> "$GITHUB_ENV"
echo 'PIP_NO_CACHE_DIR=1' >> "$GITHUB_ENV"
