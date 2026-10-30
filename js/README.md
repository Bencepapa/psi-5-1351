# Psi-5 Trading Company JS

The Avatar +4D 101% release of Psi-5 Trading Company, as the EasyFlash cartridge with 1351 mouse
support (`../psi5_ef.crt`), running unchanged on a JS 6502 core with a debugger. The page goes from the
trainer prompt through the title, course list and crew selection to the bridge. The emulator is a
copy of the one in the Sentinel project, extended for what Psi-5 needs.

`dist/psi5.html` is one self-contained file (it opens directly, and links the cartridge for download).
`index.html` loads `src/*.js` and needs a server: `python -m http.server` in `js/`.

| Part | How it is handled |
|---|---|
| 6502 | `src/cpu6502.js`, with the NMOS undocumented opcodes: the game jumps into the middle of an instruction that decodes as `ISC $CC,X` |
| Cartridge | `loadCrt` reads the CRT (EasyFlash, 23 banks); `$DE00` = bank, `$DE02` = mode (16K / 8K / Ultimax / off), 256 bytes of RAM at `$DF00`; `startCart` resets through the ROMH vector in Ultimax mode, as the hardware does |
| CIA | timers A and B with interrupts (CIA1 IRQ, CIA2 NMI), one-shot, B counting A; time of day with the alarm: the game's copy protection checks that CIA2's alarm interrupt fires (the page would wipe the stack otherwise) |
| KERNAL | there is no ROM. `m.standInKernal` shows a stand-in while `$01` has the KERNAL in: the IRQ / NMI entries and vectors, `SETLFS`, `SETNAM`, `READST`, `SETMSG` (the cartridge loader reads the file name from `$B7/$BB/$BC`). Any other jump-table entry jams |
| VIC-II, SID, 1351 | as in the Sentinel runtime: line-by-line VIC from logged register writes, SID replayed in an AudioWorklet, 1351 on the port 2 pots (pointer lock on desktop, drag on touch) |
| Timing | `m.dma = true` adds the cycles the VIC takes (bad lines, sprites). The page has it on ("Real-machine timing"); the cartridge's file copies run at full speed |
| Fonts | no character ROM: an original font stands in (the game has its own) |

## Limits

- QUIT / restart loads from disk (KERNAL `LOAD`, which is not there) and does not work.
- The game always starts at the trainer prompt (the cartridge restores a snapshot taken there).
- Checked only against the screenshots and game state described below, not against VICE frame by frame.

## Build and test

```text
python js/build.py          # embeds ref/psi5_ef_tested.crt (or the .crt given as argument) and psi5-symbols.txt in js/programs.js
python js/bundle.py         # js/index.html and js/dist/psi5.html
node js/test/run.js         # headless checks, PNG snapshots in js/test/out
```

The page is pinned to `ref/psi5_ef_tested.crt`, the cartridge the tests and labels match. For a newer `../psi5_ef.crt` (the sprite-pointer build has another RAM layout) pass it to `build.py` and update the mouse labels in `psi5-symbols.txt` first, then run both scripts again. Labels for the
debugger and the profile (`src/profiles.js`) are in `psi5-symbols.txt`.

## What the tests cover

- the CRT, EasyFlash banking and modes, the reset vector, the KERNAL stand-in, CIA timers and
  interrupts, the TOD alarm, the undocumented opcodes
- the game at page speed and with `m.dma = true`: boot to the trainer prompt, N, the title (music
  reaches the SID), fire, the course list, course 1, five candidates, accept, the bridge (getkey
  reached, raster IRQ, `$01 = $35`), the mouse (detected, pointer moves, a click begins the mission,
  a click on `Eng.` and on `Status`, a click on a device row cancels it)
- the debugger: a write watch, and a saved state that runs the same 50 frames after loading
