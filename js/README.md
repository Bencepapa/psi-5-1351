# Psi-5 Trading Company JS

The Avatar +4D 101% release of Psi-5 Trading Company, as EasyFlash cartridges with 1351 mouse
support, running unchanged on a JS 6502 core with a debugger. The browser defaults to
`ref/psi5_ef_bridge_tested.crt` and starts directly on the bridge. The full game is
`ref/psi5_ef_tested.crt` and is used by the trainer-to-bridge playthrough.

`dist/psi5.html` is one self-contained file (it opens directly, and links the cartridge for download).
`index.html` loads `src/*.js` and needs a server: `python -m http.server` in `js/`.

| Part | How it is handled |
|---|---|
| 6502 | `src/cpu6502.js`, with the NMOS undocumented opcodes: the game jumps into the middle of an instruction that decodes as `ISC $CC,X` |
| Cartridge | `loadCrt` reads the CRT (EasyFlash, 23 banks); `$DE00` = bank, `$DE02` = mode (16K / 8K / Ultimax / off), 256 bytes of RAM at `$DF00`; `startCart` resets through the ROMH vector in Ultimax mode, as the hardware does |
| CIA | timers A and B with interrupts (CIA1 IRQ, CIA2 NMI), one-shot, B counting A; time of day with the alarm: the game's copy protection checks that CIA2's alarm interrupt fires (the page would wipe the stack otherwise) |
| KERNAL | there is no ROM. `m.standInKernal` shows a stand-in while `$01` has the KERNAL in: the IRQ / NMI entries and vectors, `SETLFS`, `SETNAM`, `READST`, `SETMSG` (the cartridge loader reads the file name from `$B7/$BB/$BC`). Any other jump-table entry jams |
| VIC-II, SID, 1351 | line-by-line VIC from logged register and VIC-bank RAM writes, SID replayed in an AudioWorklet, 1351 on the port 2 pots (pointer lock on desktop, drag on touch) |
| Timing | `m.dma = true` adds the cycles the VIC takes (bad lines, sprites). The page has it on ("Real-machine timing"); the cartridge's file copies run at full speed |
| Fonts | no character ROM: an original font stands in (the game has its own) |

## Limits

- Quit / Oops-continue returns to play. Actual Replay / restart still loads from disk (KERNAL `LOAD`, which is not there).
- The full-game cartridge starts at the trainer prompt; the bridge cartridge starts on the bridge.
- Checked only against the screenshots and game state described below, not against VICE frame by frame.

## Build and test

```text
python js/build.py          # embeds the bridge ref by default; a .crt argument selects another cartridge
python js/bundle.py         # js/index.html and js/dist/psi5.html
node js/test/run.js         # headless checks, PNG snapshots in js/test/out
```

The generated download name comes from the selected cartridge filename. Mouse labels in
`psi5-symbols.txt` follow `ef/mouse_ram.asm`; the screen pointer table is `$53F8`.

## What the tests cover

- the CRT, EasyFlash banking and modes, the reset vector, the KERNAL stand-in, CIA timers and
  interrupts, the TOD alarm, the undocumented opcodes
- both cartridges at page speed and with `m.dma = true`: bridge boot/getkey, CIA2 TOD alarm and
  3000-frame copy-protection survival, plus the full trainer-to-bridge playthrough
- mouse movement, pointer snapshots, menu clicks, device clicks, blank cells, back/right-button paths,
  and Engineering Display drag feedback
- left/right joystick regression with held and tapped presses, mouse present and absent, on both carts
- the debugger: a write watch, and a saved state that runs the same 50 frames after loading

The suite also checks Navigation Status selection without flash, Navigation Display click-to-first
with a single yellow course flash and exclusive white hover on a black base, cleanup when
entering Repair, overlapping generic rank-flash cleanup after a row disappears,
list-hover column bounds across joystick polls, and visual-update completion before the next
top raster split. Game-address breakpoints exclude the overlapping mouse ROM bank.
Menu checks trace cursor writes for direct 1-to-9 and 9-to-1 hover, verify the
activated command, and observe individual colour writes through both native
paint loops to ensure `priority_` never receives white.
Replay shows a shared question above short Same / New / Back choices. Both native
replay destinations and Oops-continue are checked with the debugger event profile enabled.
The restart pause is at
`$89D5`, after the Oops-continue branch; RAM-only game events ignore overlapping cartridge code.
