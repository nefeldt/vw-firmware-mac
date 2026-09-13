# Native navigation persistence investigation

Navigation is not operational. The original engine starts in an isolated guest
and fails its persistence configuration. A separate shell check in QNX reads
the attached map card's metadata successfully.
The CPU configuration proxies persistence to `J5e.PersMaster`; that service is
not present in the currently prepared guest. The user has only an eMMC dump,
not a separate MAIN root dump.

## Verified static interface

The local P0480T navigation crypto library has no ELF section headers. The
analysis script uses its program headers, dynamic symbol table and SysV hash
instead. ARM PLT calls are resolved through relocation targets:

```sh
build/analysis-venv/bin/python scripts/inspect_persistence_client.py \
  extracted/P0480T/navigation-unpacked/libtsd.mibstd2.nav.crypto.so \
  --match persistence > reports/persistence-protocol-disassembly.txt
```

`MibStd2PersistenceFrontend::initPersClient` calls `PersClient::syncConfigure`
at virtual address `0x2ac10`. Its single request contains:

| Native member offset | Value | Interpretation |
| --- | --- | --- |
| 0x00 | 0x8000000a | Namespace |
| 0x04 | 400 | Key |
| 0x08 | 2 | Unsigned 16-bit member; meaning unresolved |
| 0x0c | 17 | 32-bit member; meaning unresolved |
| 0x10 | 596 | Unsigned 16-bit member; meaning unresolved |

The serializer at `0x76214` writes all five members as 32-bit integers.
`RpcBuffer::storeInt` in the original common library copies four native bytes
through `storeBlob`, so this ARM little-endian payload uses little-endian words.
`syncConfigure` writes three zero words followed by a vector count and its
20-byte entries. Its expected response has three header words, a vector count,
and 12 bytes per `ConfAck` (three integer fields). These are payload layouts,
not a complete description of the underlying QNX IPC transport.

`PersClient::init` resolves an IPC object through `getNamedObject`. The
synchronous transaction subsequently calls an object virtual method at vtable
offset 0x10 with outgoing and incoming `Transfer` objects. A functional server
still needs compatible transport registration and valid backing values.

The vault inspected from the eMMC contains neither namespace `0x8000000a` /
key `400`, nor hardware information `0x80000001` / key `4`. Do not equate
successful request decoding with a valid service response or working navigation.

## Offline payload decoding

```sh
python3 scripts/decode_persistence_request.py path/to/configure-payload.bin
python3 -m unittest discover -s tests
```

The decoder only consumes a payload supplied by the caller. Its navigation test
fixture is reconstructed from the instructions above; it is not a captured live
transaction. No successful persistence responses or vehicle data are fabricated.
The next runtime step is observing the original IPC transaction and implementing
or recovering the missing service with its genuine data sources.
