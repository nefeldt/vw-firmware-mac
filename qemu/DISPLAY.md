# Native QEMU display (experimental)

The custom `mib-display` device creates a Cocoa QEMU window with an 800 × 480
original HMI display inside a 1000 × 600 control panel. It receives real GPU
readback from the Mac backend. It does not replace the HMI or implement a
Vivante GPU. End-to-end verification is tracked in [STATUS](../docs/STATUS.md).

Build the isolated QEMU binary (defaults to two low-priority compiler jobs):

```sh
make native-qemu
```

With `make viewer` and `make renderer` running, launch from the repository root:

```sh
export MIB_QEMU_BIN="$PWD/runtime/qemu-display/build/qemu-system-arm"
export MIB_QEMU_NATIVE_DISPLAY=1
python3 scripts/probe_qemu.py \
  --commands-file qemu/seat-native-input-probe.commands \
  --report reports/native-guest.log \
  --command-timeout 240 --keep-running
```

The window is named **SEAT MIB2**. Click the HMI for touch, use the surrounding
buttons for hardware keys, and scroll over the left/right knob zones for volume
or tuning. F1–F8 select the eight side buttons. These mappings are experimental;
service availability determines the original HMI's response.

Stop the launcher with Ctrl-C. It terminates its guest process. Close the
renderer/viewer terminals separately. Runtime communication uses localhost
ports 8767–8769 and Unix sockets `/tmp/mib-qemu-display.sock` and
`/tmp/mib-qmp.sock`. Run only one interactive guest at a time.
