# Native QEMU display (experimental)

The custom `mib-display` device creates a Cocoa QEMU window with an 800 × 480
original HMI display inside a 1000 × 600 control panel. It receives real GPU
readback from the Mac backend. It does not replace the HMI or implement a
Vivante GPU. End-to-end verification is tracked in [STATUS](../docs/STATUS.md).

Build the isolated QEMU binary (defaults to two low-priority compiler jobs):

```sh
make native-qemu
```

Launch all services and QEMU from the repository root:

```sh
./start-mib.command
```

Fullscreen and a visible mouse pointer are enabled by default. Use
`MIB_FULLSCREEN=0 ./start-mib.command` for a window.

The window is named **SEAT MIB2**. Click the HMI for touch, use the surrounding
buttons for hardware keys, and scroll over the left/right knob zones for volume
or tuning. F1–F8 select the eight side buttons. These mappings are experimental;
service availability determines the original HMI's response.

Press Ctrl+C in the startup terminal to stop all managed services, including
QEMU. Repeated Ctrl+C leaves cleanup running. Alternatively use
`./stop-mib.command`, which also discovers orphaned project MIB processes.
Runtime communication uses localhost ports 8766–8769 and Unix sockets
`/tmp/mib-qemu-display.sock` and `/tmp/mib-qmp.sock`.
Run only one interactive guest at a time.

The renderer buffers logs and reuses the browser PNG when pixels are unchanged;
frame timestamps and native QEMU updates continue on every guest swap. For
individual GLES command traces, start with `MIB_GL_TRACE=1 ./start-mib.command`.
These settings apply when starting a new session.
