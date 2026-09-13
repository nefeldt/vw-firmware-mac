# Verified status

## Completed

- Original QNX CPU image boots on QEMU's SabreLite machine.
- Original SEAT P0480T J9/HMI starts with its own resources.
- Empty persistence responses and simulated power-on allow HMI initialization.
- Original GLES commands execute on the Mac GPU through a typed RPC bridge.
- The original radio UI renders, including labels and preset tiles.
- Browser displays actual renderer frames and distinguishes stale frames.
- Original firmware/eMMC backing files remain unchanged; guest writes use overlays.
- Native QEMU window displays the original radio and SEAT tile main menu.
- Emulator skin configuration selects the existing Grid menu at startup.
- Touch packet layout corrected to the original 32-bit boolean encoding;
  touch navigation to original Navigation and Sound screens observed.
- Native MENU button opens the main menu through the guest DSI input bridge.
  P0480T front-panel keys require keyboard group 13; group 1 has no MENU mapping.
- Unified startup and Ctrl+C cleanup, including QEMU and display services.
- Animated English loading screen, verified in an isolated QEMU display test.

## Implemented, awaiting end-to-end verification

- Complete touch, front-button, browser-control and encoder coverage. MENU is
  verified; working transport alone does not verify every control or service.
- Warm VM snapshot restoration with the external Mac graphics context.

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
