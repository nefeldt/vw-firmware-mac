# Licensing and third-party components

Project code is licensed under **GPL-2.0-or-later**. See [LICENSE](LICENSE).
You may redistribute and modify it under version 2 of the GNU General Public
License or, at your option, any later version. It is provided without warranty.

The QEMU display extension is compiled into QEMU, which is distributed under
GPL version 2 with individual files permitting later versions or other
compatible terms. QEMU is downloaded separately; its source notices remain intact.
The extension uses QEMU's existing VGA font for its surrounding controls.

The generated EGL/GLES entry-point declarations describe the public Khronos API.
SDK headers are obtained from the user's local toolchain and are not bundled.
QNX/J9 JNI headers and all proprietary firmware content must be supplied locally.
The build container is an external dependency with its own licensing terms;
this repository does not provide a QNX SDK license.

SEAT, Volkswagen, QNX, and other product names identify compatible software and
hardware. This is an independent research project and is not affiliated with
or endorsed by their owners. Firmware, fonts, screenshots, extracted binaries,
vehicle dumps, and third-party repository checkouts are not part of this release.
