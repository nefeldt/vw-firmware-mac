# Local inputs and build

This is a research snapshot, not a universal firmware installer. Start with the
exact P0480T train linked in the README. Independently extract your authorized
firmware archive, HMI archive, system IFS, and QNX filesystems. The repository
does not download proprietary inputs. A compatible extracted tree is a prerequisite;
automatic extraction of every supported archive is not implemented.

Expected paths relative to the repository:

```text
firmware/P0480T/cpu/cpuimage_sec_stdNavi/24/default/mibstd2_cpu.boot
extracted/P0480T/hmi/tsd/tmp/hmi/
    runHMI.sh
    fonts.conf
    tsd.mibstd2.hmi.ifs
    libtsd.mibstd2.hmi.dsi.native.so
    Resources/                 # complete original SEAT resources
    ...                        # complete original HMI directory
extracted/eMMC/emmc.img
extracted/eMMC/system-ifs/tsd/bin/root/tsd.mibstd2.cpu.root
extracted/eMMC/system-ifs/tsd/bin/displaymanager/tsd.mibstd2.system.displaymanager
extracted/eMMC/filesystems/p1/j9/bin/include/jni.h
extracted/eMMC/filesystems/p1/j9/bin/include/jniport.h
```

The original experiment used a 3,833,593,856-byte community eMMC image with
three MBR QNX6 partitions and an unused fourth partition. `stage_seat_partition.py`
adds data at offset `0xe5000000` in a **4 GiB qcow2 overlay**, with assertions on
layout and bounds. A different disk layout needs analysis, not blind execution.

Useful independent extraction projects include
[QNX mount tools](https://github.com/NetherlandsForensicInstitute/qnxmount) and
[MIB STD2 Toolbox](https://github.com/olli991/mib-std2-pq-zr-toolbox).
`scripts/extract_emmc.py` expects a local checkout at `vendor/qnxmount`; that
checkout is deliberately excluded from this repository. It extracts files
read-only and records symlink targets in a local manifest.

Install Docker and make the toolchain image available under your own license:

```sh
docker pull ghcr.io/frida/qnx-tools:latest
export DOCKER_CONTEXT=colima-x86  # use your actual context
make doctor
make guest
```

All compile containers use `--network none --pull never`; the build never
implicitly pulls a toolchain. The image's `latest` tag can change. The original
research used image ID
`sha256:65f1864ebbff521bcc6b2afd234d5679920b9466b4ba1d57be5d8f131993bfe2`.
This is a local image ID, not a guaranteed pullable registry manifest digest.

`make guest` copies originals into ignored build directories, prepares the CPU
image, builds GLES/Screen/EGL and DSI adapters, imports local JNI headers,
patches the copied clock worker/font root, and stages the transfer IFS. It keeps
the original eMMC as a read-only backing file. Do not run image staging while a
guest is using the same overlay.

The setup expects ports 8766–8769 to be free. The host CGL renderer is macOS-only.
Start viewer and renderer before the guest. See the README for launch commands.

The native QEMU build downloads only open-source QEMU and build dependencies.
Its SHA-256 is pinned in `runtime/qemu-display/source.sha256`; this records the
source archive used by the project, not an independent signature verification.
It defaults to two compiler jobs and reduced scheduling priority.
