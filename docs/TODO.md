# Emulator work remaining

- [x] Restore native input after the failed navigation experiment. User confirmed
  controls work again; original tile menu verified in reports/recovery-menu.png.
- [ ] Verify native mouse clicks at the visible button positions across window sizes after the Cocoa fix.
  Coordinate conversion passes three scaled/offset Cocoa view tests; build passes.
- [x] Activate and verify visible outlines for the native side buttons and knob controls.
- [ ] Run the original navigation engine and middleware, load compatible map data,
  and verify map display and navigation interaction. A loading screen is not success.
- [ ] Configure the original system to identify the vehicle as a SEAT Ibiza,
  model year 2017. Current diagnostic output incorrectly reports VW=true,
  SEAT=false. Verify brand/model coding and preserve unknown equipment values
  rather than guessing them from the visual skin.
- [ ] Enable the original SEAT Full Link entry and connect it to working services.
- [ ] Establish a real iPhone CarPlay session with display, touch and audio.
- [ ] Run the original telephone service: pairing, contacts, incoming/outgoing
  calls, call audio and HMI controls. Verify with a real connected phone.
- [ ] Make Bluetooth usable inside the guest, including actual adapter transport
  and pairing. A running process alone is not success.
- [ ] Measure responsiveness after the packed graphics transport change.

## Service findings

The original audio service crashes in the i.MX6 SDMA setup. Bluetooth and SAL were
not running in the normal service startup. A manual Bluetooth probe starts with
its common-library path but reports Bluetooth deactivated and missing MCP client
configuration. These are diagnostic results, not working connectivity.

## Navigation experiment

The separate navigation test image was built and the original engine and
middleware IFS images were mounted successfully. The session subsequently
stopped producing HMI frames and UART responses; engine startup was not verified.
The known working transfer image was restored. Do not run the navigation probe
on the interactive session until this regression is isolated. Map data has now been supplied and verified as described below.

## Navigation data and persistence

The local FAT32 map card contains ECE1 2026 / version 2510. An isolated QNX
probe mounted `/dev/sd10t12` and read its database metadata successfully.
The original navigation engine now stays running under the CPU service manager
with the persistence connection pair, but reports persistence configuration
errors and immediately fails to open the database. No working map is verified.

The eMMC persistence vault contains 53 length-delimited records; hardware-info
namespace `0x80000001`, key `4`, is absent. The user confirms that only the eMMC
dump is available, with no separate J5/MAIN root dump. Continue analyzing the
MAIN update and native persistence protocol; do not substitute invented vehicle
coding or treat an empty persistence response as a working navigation service.

Static analysis of the original navigation crypto frontend also identifies a request
for namespace `0x8000000a`, key `400`; that record is absent from this vault too.
The meaning and required contents of this request still need to be established.
