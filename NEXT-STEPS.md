# Psi-5 EasyFlash: where things stand (2026-10-30)

`psi5_ef.crt` is the full game with the mouse; `psi5_ef_bridge.crt` is the test cartridge that starts on the bridge with a crew chosen. Details: `MOUSE-SUPPORT.md`, `RE-NOTES.md`.

## Done

- Bridge test cartridge: `python ef/efbuild.py --bridge`, boot with `tools/crt_bridge.sh`, retake the snapshot with `tools/snap_bridge.py`. Its crash was the game's copy protection (see `RE-NOTES.md`); the boot code now sets the CIA2 alarm.
- Sprite pointer (sprite 7, multiplexed, white with black outline), list clicks in all departments, grey drag row and rank flash.

## To test

- Real mouse with this version: pointer, top-view ships while sprite 7 is multiplexed.
- Simulated so far: Navigation select, Engineering toggle, Engineering drag.
- Not exercised at all: Scanning examine, Repair assign, drag on the Weapons, Repair and Scanning lists, row clicks during a prompt. They need a situation with targets, damage or firing orders.

## Open

- Mouse on the crew selection screen (front-end key queue `$CF00`, count `$62`; the pointer code doesn't run there yet).
- QUIT/restart (it loads from disk).
- Mouse in port 1.

## Free memory: test reads as well

A marker test only sees writes. `$5780-$57BF` survived one but holds the keyboard table. Check with `watch` (load and store) as well, and with ships on screen: the renderer reads shapes at `$EA4D`.

## Always test the normal cartridge too

The bridge cartridge skips all loading. `tools/crt_tobridge.sh` then `tools/crt_finish.sh` run the real path. This caught `$0334-$03F2` being overwritten by loads, which the marker test on the bridge can't see.

## VICE tips

- Test runs use `-config tools/vicetest.ini`, which needs a `[Version]` header, or VICE shows a warning.
- A checkpoint left armed when the client disconnects opens VICE's own monitor window. Delete checkpoints before disconnecting.
- A breakpoint hit shows as `#1 (Stop on  exec ff48)` (two spaces); the echo of the `break` command also contains the address, so match carefully.
- `chis N` (CPU history) is the best tool. Break on the first address that shouldn't run, for example `$FF48` (KERNAL IRQ entry, never used by the game), then read backwards.
- Debug builds: `HOLD=1` spins at `$03C4` with IRQs off, `r pc=03c7` in the monitor resumes. `KEEPRAM=1` keeps the snapshot's own RAM part.
