# Verified status

## Completed

- Original QNX CPU image boots on QEMU's SabreLite machine.
- Original SEAT P0480T J9/HMI starts with its own resources.
- Empty persistence responses and simulated power-on allow HMI initialization.
- Original GLES commands execute on the Mac GPU through a typed RPC bridge.
- The original radio UI renders, including labels and preset tiles.
- Browser displays actual renderer frames and distinguishes stale frames.
- Original firmware/eMMC backing files remain unchanged; guest writes use overlays.

## Implemented, awaiting end-to-end verification

- JNI input receiver for DSIKeyPanel touch, buttons, and encoders.
- Browser input controls and local input hub.
- Native QEMU display device with side buttons and wheel-operated knob zones.
- Persistent interactive guest launcher.

## Limitations

The Screen/EGL adapter is not a full QNX compositor or GPU emulator. Several GLES
entry points are unsupported and explicitly fail. Texture packing and client
vertex arrays have limitations. Many vehicle-service startup requests time out.
The radio screen does not prove actual reception, sound, navigation, CarPlay,
Bluetooth, or communication with a car. Performance is experimental.

The tested storage layout and binary patches are version-specific. Do not use
an emulator-patched image in a vehicle. The workflow has no flashing step.

Internal logs and screenshots are deliberately not distributed. Host-only
renderer checks must not be described as guest success. Update this file only
after observing the relevant guest behavior.
