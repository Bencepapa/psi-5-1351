# Psi-5 Trading Company

Psi-5 Trading Company (Accolade, 1986) on an EasyFlash cartridge, with 1351 mouse support.

**[Play in the browser](https://bencepapa.github.io/psi-5-1351/)**

- [Full game cartridge](docs/psi5_ef.crt)
- [Bridge cartridge](docs/psi5_ef_bridge.crt)

Run the full game in VICE:

```text
x64sc -controlport2device 3 -cartcrt psi5_ef.crt
```

The mouse is in port 2; press `Alt+Q` to grab the mouse.

## Mouse controls

- Click a course or candidate portrait; in personnel files click Welcome or Exit.
- On the crew summary, click Accept or Reselect. Joystick and keyboard selection still work.
- Move the pointer; the item under it is highlighted white.
- Click menus and list items.
- Drag an item to rank it in priority lists.
- On the bridge, use the right button to go back; during a drag it cancels the drag.

## Build notes

`python ef/efbuild.py` needs the original disk `PSI-5 +4D 101% ATA.d64`, the snapshot files under `tools/`, and the `asm6502` assembler from the sibling `mousegui` project at `C:\dev\c64\mousegui\tools`. It reads the D64 directly in Python; `c1541.exe` is not needed for building. The original disk is not in this repository.

### Generating snapshot files

The snapshot files (`snap_ram.bin`, `snap_io.txt`, `snap_cpu.txt`, `snap_col.bin`, and their `snapb_*` bridge counterparts) are captured from VICE running with remote monitor enabled:
- Full game snapshot: run `python tools/snap.py` (boots the D64, answers trainer prompt, and captures state at the first loader call).
- Bridge snapshot: run `python tools/snap_bridge.py` (captures state directly at the bridge menu loop getkey `$3EE9`).

See [ef/efbuild.py](ef/efbuild.py) and the [reverse-engineering notes](RE-NOTES.md).

More details: [MOUSE-SUPPORT.md](MOUSE-SUPPORT.md), [RE-NOTES.md](RE-NOTES.md), [NEXT-STEPS.md](NEXT-STEPS.md), and [js/README.md](js/README.md).

This is an unofficial fan project, not affiliated with the rights holders. The game itself remains the work of its authors.
