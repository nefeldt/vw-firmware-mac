#!/bin/zsh
# Build an isolated native console. Does not replace the system QEMU.
set -eu
ROOT=${0:A:h}
SOURCE="$ROOT/qemu-11.1.0"
ARCHIVE="$ROOT/qemu-11.1.0.tar.xz"
JOBS=${MIB_BUILD_JOBS:-2}
if [[ ! -f "$ARCHIVE" ]]; then
  curl --fail --location https://download.qemu.org/qemu-11.1.0.tar.xz --output "$ARCHIVE"
fi
(cd "$ROOT" && shasum -a 256 -c source.sha256)
if [[ ! -f "$SOURCE/configure" ]]; then tar -xf "$ARCHIVE" -C "$ROOT"; fi
cp "$ROOT/mib-display.c" "$SOURCE/hw/display/mib-display.c"
python3 - "$SOURCE/hw/display/meson.build" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();line="system_ss.add(files('mib-display.c'))"
if line not in s:p.write_text(s+'\n'+line+'\n')
PY
mkdir -p "$ROOT/build"
cd "$ROOT/build"
if [[ ! -f build.ninja ]]; then
  "$SOURCE/configure" --python="$(command -v python3)" --target-list=arm-softmmu \
    --enable-cocoa --disable-docs --disable-guest-agent --disable-tools \
    --disable-werror --disable-gtk --disable-sdl --disable-vnc --enable-slirp \
    --disable-capstone --disable-curl --disable-gnutls --disable-plugins
fi
nice -n 15 ninja -j "$JOBS" qemu-system-arm
print "Built: $ROOT/build/qemu-system-arm"
