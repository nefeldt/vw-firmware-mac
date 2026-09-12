#!/bin/zsh
# Cross-compile the guest shim libraries with the QNX 6.5 toolchain in the Frida container.
set -eu
set -o pipefail
ROOT=${0:A:h}
mkdir -p "$ROOT/build"
tar -cf - -C "$ROOT/src" . | docker run --rm --network none --pull never -e MIB_GLES_IMPL="${MIB_GLES_IMPL:-stub}" -i ghcr.io/frida/qnx-tools:latest -lc '
set -e; mkdir -p /work/src /work/out && cd /work/src && tar -xf -
export QNX_HOST=/opt/qnx650/host/linux/x86 QNX_TARGET=/opt/qnx650/target/qnx6 PATH=/opt/qnx650/host/linux/x86/usr/bin:$PATH
CC="qcc -Vgcc_ntoarmv7le -shared -fPIC -O1 -Wc,-std=gnu99 -Wall -Wno-unused-variable -Wno-unused-function"
for lib in libscreen libEGL libGLESv2; do
  source=${lib}_stub.c
  if [ "$lib" = libGLESv2 ] && [ "$MIB_GLES_IMPL" = bridge ]; then source=libGLESv2_bridge.c; fi
  $CC -Wl,-soname,$lib.so.1 -o /work/out/$lib.so.1 "$source" -lsocket 1>&2
done
qcc -Vgcc_ntoarmv7le -Wc,-std=gnu99 -o /work/out/display-probe display_probe.c -L/work/out -l:libscreen.so.1 1>&2
cd /work/out && cp libGLESv2.so.1 libGLESv2.so && cp libEGL.so.1 libEGL.so && cp libscreen.so.1 libscreen.so
arm-unknown-nto-qnx6.5.0-readelf -d libGLESv2.so.1 | grep -E "SONAME|NEEDED" 1>&2
tar -cf - .' | tar -xf - -C "$ROOT/build"
ls -la "$ROOT/build"
