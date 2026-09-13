#!/bin/zsh
set -eu
set -o pipefail
ROOT=${0:A:h}/../..
mkdir -p "$ROOT/build/audio-probe/shim"
docker --context "${DOCKER_CONTEXT:-colima-x86}" run --rm --network none --pull never -i ghcr.io/frida/qnx-tools:latest -lc '
set -e
cat > /tmp/dma_trace.c
export QNX_HOST=/opt/qnx650/host/linux/x86 QNX_TARGET=/opt/qnx650/target/qnx6
export PATH=$QNX_HOST/usr/bin:$PATH
qcc -Vgcc_ntoarmv7le -shared -fPIC -Wall -Werror -I/opt/sabrelite/assets/usr/include /tmp/dma_trace.c -o /tmp/libdma-trace.so
cat /tmp/libdma-trace.so
' < "$ROOT/guest/audio/dma_trace.c" > "$ROOT/build/audio-probe/shim/libdma-trace.so"
