#!/bin/zsh
set -eu
ROOT=${0:A:h}/..
IMAGE=${MIB_CPU_IMAGE:-$ROOT/extracted/P0480T/cpu-qemu-debug.ifs}
EMMC_IMAGE=${MIB_EMMC_IMAGE:-$ROOT/qemu/emmc-overlay.qcow2}
if [[ ! -f "$IMAGE" ]]; then
  print -u2 'Run scripts/prepare_qemu_cpu.py with --debug-shell first.'
  exit 1
fi
QEMU_BIN=${MIB_QEMU_BIN:-qemu-system-arm}
DISPLAY_ARGS=(-display none)
# Temporary disk writes protect the prepared inputs; no VM state is restored.
MAP_ARGS=()
if [[ -n ${MIB_MAP_IMAGE:-} ]]; then
  [[ -f "$MIB_MAP_IMAGE" ]] || { print -u2 "Missing map card: $MIB_MAP_IMAGE"; exit 1; }
  MAP_ARGS=(-drive "file=$MIB_MAP_IMAGE,if=none,id=navmaps,format=raw,snapshot=on" -device sd-card,drive=navmaps,bus=/mib-sdhc1/sd-bus)
fi
SERIAL_ARGS=(-serial stdio)
if [[ -n ${MIB_SERIAL_SOCKET:-} ]]; then
  SERIAL_ARGS=(-chardev "socket,id=mibserial,path=$MIB_SERIAL_SOCKET,server=on,wait=off" -serial chardev:mibserial)
fi
if [[ ${MIB_QEMU_NATIVE_DISPLAY:-0} == 1 ]]; then
  DISPLAY_ARGS=(-display cocoa,zoom-to-fit=on,show-cursor=on,left-command-key=off -name 'SEAT MIB2' -chardev socket,id=mib,path=/tmp/mib-qemu-display.sock,server=on,wait=off -device mib-display,id=seat-screen,chardev=mib -qmp unix:/tmp/mib-qmp.sock,server=on,wait=off)
  if [[ ${MIB_FULLSCREEN:-1} == 1 ]]; then DISPLAY_ARGS+=(-full-screen); fi
fi
exec nice -n 10 "$QEMU_BIN" -M sabrelite \
  -cpu cortex-a9,reset-cbar=0x00a00000 -smp 2 -m 1024M \
  "${DISPLAY_ARGS[@]}" "${SERIAL_ARGS[@]}" -monitor none \
  -drive "file=$EMMC_IMAGE,if=none,id=emmc,format=qcow2,snapshot=on" \
  -device emmc,drive=emmc "${MAP_ARGS[@]}" \
  -device "loader,file=$IMAGE,addr=0x10800000,force-raw=on" \
  -device loader,addr=0x10805fb4,cpu-num=0
