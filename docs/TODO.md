# Emulator work remaining

- [ ] Verify native mouse clicks at the visible button positions after the Cocoa fix.
  Coordinate conversion passes three scaled/offset Cocoa view tests; build passes.
- [ ] Activate and verify visible outlines for the native side buttons and knob controls.
- [ ] Run the original navigation engine and middleware, load compatible map data,
  and verify map display and navigation interaction. A loading screen is not success.
- [ ] Configure the original system to identify the vehicle as a SEAT Ibiza,
  model year 2017. Current diagnostic output incorrectly reports VW=true,
  SEAT=false. Verify brand/model coding and preserve unknown equipment values
  rather than guessing them from the visual skin.
- [ ] Enable the original SEAT Full Link entry and connect it to working services.
- [ ] Establish a real iPhone CarPlay session with display, touch and audio.
- [ ] Make Bluetooth usable inside the guest, including actual adapter transport
  and pairing. A running process alone is not success.
- [ ] Repair and verify fresh-process live snapshot restoration, including CPU,
  external graphics state and input connections; only then call warm startup working.
- [ ] Measure responsiveness after the packed graphics transport change.

## Current snapshot status

`./capture-mib.command` saved a standalone local QEMU image. The fresh-process
restore test failed, with the CPU at a prefetch-abort vector and no new graphics
or input connection. The starter skips this known failed capture and cold-boots.
Capture and run commands are documented in README.md. Snapshot files are private.

## Service findings

The original audio service crashes in the i.MX6 SDMA setup. Bluetooth and SAL were
not running in the normal service startup. A manual Bluetooth probe starts with
its common-library path but reports Bluetooth deactivated and missing MCP client
configuration. These are diagnostic results, not working connectivity.
