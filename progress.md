# Psi-5 UI debugging handoff

## Verified Navigation / Quit fixes after d19f9e5 (2026-11-02)

- The direct-selection / priority-label fixes were committed first as requested: `d19f9e5 Select mouse menu targets directly and prevent priority label flashes`.
- Navigation Display now rebuilds its five fixed course rows from black every update, paints only the newly selected first course yellow during its feedback timer, and paints exactly one hovered row white. No blue shifted-row feedback or saved generic hover colours are used there. All five course rows remain hoverable during the flash.
- Nav colour ownership is tracked at unused colour-RAM cell `$DBE9` (bit 0 active, bit 1 last first row yellow); the builder initializes it to zero. On exit, only the white/yellow cells in the rows actually highlighted by Nav are cleared. Newly drawn red/cyan headers are preserved. Repair's native colours are unchanged; the reported white text was addressed as Navigation colour carryover.
- Replay is reworded per the latest user request: header `QUIT - Replay with Same crew & course?`, choices `Same New` plus Back. The builder shortens the verified native record at `$BF54`, relocating its FF/count/keys/pointers inside the same record footprint; original S/N shortcuts, replay destinations and other node addresses stay intact. A guarded main-loop header writer supplies the 40-column explanation. Both Same and New are tested through the real restart event, including native same/new mode `$0755` values 0/1.
- The general menu parser also preserves underscores as internal choice separators (the font displays them as spaces), so grouped labels are no longer fragmented or selectively recoloured. Lowercase prompt prefixes such as `priority_` remain non-interactive.
- JS debugger fix: `$89C1` is the Quit dispatcher, including Oops-continue; the actual restart path starts at `$89D5`. The RESTART label/pause now uses `$89D5`. Native game events are RAM-only and ignore temporarily mapped cartridge code at the same addresses. Oops-continue returns normally; actual disk-based Replay remains unsupported and still pauses before disk loading.
- Added UI regressions for every Nav course hover, hover while flashing, black non-selected rows, Nav-to-Status heading preservation, Nav-to-Repair cleanup, short Replay layout and both native replay choices, and Oops-continue with debugger events enabled. Additional debugger fixtures check bank filtering and the actual restart pause. Transition tests wait for actual titles because native Status/Display redraws can be delayed; Replay activation includes button release before waiting for the native action.
- Verification log for the final full run: `js/test/out/ui-final-regression.log`; targeted Replay check: `js/test/out/replay-short-targeted.log`; visual preview: `js/test/out/replay-short-preview.png`. Both CRT variants and browser outputs are rebuilt; these new changes have not been checked in VICE by the agent.
- Final results: the full JS suite passed in both timing modes; visuals peaked at 3338 cycles with zero late updates across 5700 / 5659 measured calls. All 5 D64 reader tests pass. The short Replay layout was visually inspected, Same/New reach native modes 0/1, and Back was separately checked to return to Oops-continue / Replay. Distributed CRT copies match the final builds.
- Latest user verification: "Working super!" The user confirmed this build and requested committing and pushing these fixes.

## Committed checkpoint d19f9e5 (2026-11-02)

- Menu hover now directly sets native endpoint `$0774`, word start `$4D`, and choice ordinal `$3D`. It clears deeper remembered choices as the native navigation code does. Mouse movement no longer synthesizes intermediate left/right presses; native fire still executes the selected command, and physical joystick directions retain precedence.
- The priority-label source hooks are at **`$9B85` and `$86AD`**, verified by disassembly of the actual game instructions (`STA $DA31,Y`). The older analysis below named addresses two bytes too late. Both sites now call `WPMENU`, which skips the `priority_` prefix while preserving X/Y. Interactive lowercase suffixes such as `At-will` are unaffected. The builder asserts that both hooks were applied.
- `LABELS` is now only a safety net in main-loop `VIS`, outside the split IRQ. Direct menu repainting uses the shared native highlight; it does not add a second overlay.
- The RAM part still fits `$0210-$02FF`, with all mouse variable addresses unchanged. Space was recovered by returning the ROM result through X (all trampoline callers consume A), compact ACT dispatch, and moving command-record restoration into the `MREST` ROM entry. Updated trampoline symbols: `TPOST=$023F`, `TKEY=$0248`; `WPMENU=$0275`.
- Verification: the full `node js/test/run.js` suite passed in both timing modes. Cursor-write traces show exactly one selection write for each 1-to-9 / 9-to-1 jump, and clicks execute the correct numeric choice. Both native paint loops were exercised (88 forward / 2 backward paint calls per mode), with **zero white writes** to priority-label cells at instruction granularity. Main-loop visuals peaked at 3347 cycles with zero late calls (4545 / 4504 measured updates). All 5 D64 reader tests also pass. Log: `js/test/out/direct-selection.log`.
- Both CRT variants and browser outputs were rebuilt and distributed CRT copies matched the verified builds byte for byte. This follow-up was committed as `d19f9e5`; subsequent user reports are addressed in the newer section above.

## Committed checkpoint 5b210da (2026-11-02)

This section supersedes the experimental state below; the earlier analysis is retained as history.

- Navigation Status clicks select the pressed course without starting rank flashes. Per the latest user request, Display is also click-to-first, with yellow feedback on the moved course and blue on shifted rows. Navigation has no drag preview; other departments retain drag ranking.
- Native `$8AE7` begins with `LDA #'1'` and forces every Navigation operation to the front. This is now the intended behaviour; mouse actions retain the original native entry point.
- Additional verified raster/colour cause: `MJOY` reset `HOVE` unconditionally, although that variable is a list's end column outside menu targeting. Subsequent hover restoration could paint 256 cells rather than 40. Resetting the pulse phase is now restricted to `HOVR == 14`.
- `VIS` (list hover, drag preview and flash painting) moved from `MPRE` to the main-loop `MKEY` path. `INTXT` bit 0 marks a pending frame. Since `ROMCALL` masks IRQs while ROML is mapped, updates start only in PAL lines 240-295, leaving time before the next `$2D` split. The high/low raster read rejects frame-wrap races. Menu labels/native targeting remain in the IRQ; removing old list overlays does not.
- Flash setup and restoration paint one row per visual update. `ROWADR` uses fixed row-offset tables instead of multiplying on each cell probe.
- Fixed persistent blue rows when ranks overlap: do not capture temporary flash colours as `BASEC`; merge previous and new flash ranges so earlier painted rows still get restored. An actual mouse regression performs two overlapping Engineering ranks and removes a rendered row during the flash, then checks that all earlier rows return to their base colour.
- This is still screen-text recognition, not renderer-registered hot areas. A renderer-integrated rectangle table would require hooks at the original game's table/menu draw paths and explicit invalidation on screen changes. It is a separate refactor; the fixes here remove expensive list work from the split IRQ without replacing all draw paths.
- RAM code remains `$0210-$02FF`, with unchanged variable/trampoline addresses. `js/psi5-symbols.txt` now also exports hover row/start/end for regression checks.
- Tests now actually enter Nav Status, observe the real EasyFlash `efRam[$FC]` throughout the click, verify the native rank arguments, and check Display click-to-first plus both feedback colours. Game-address survival breakpoints ignore the overlapping mouse ROM bank. New checks cover hover column bounds and main-loop visual duration against the next split deadline.
- After a reported c1541.exe crash, the builder now reads PRG directory entries and sector chains directly with `tools/d64read.py`. Rebuilding both CRT variants produced identical SHA-256 hashes to the preceding c1541 builds. No c1541 process or extraction temporary file is required.
- Final verification: `node js/test/run.js` passed completely in both page-speed and DMA timing modes. Visual work peaked at 2367 cycles, with zero late updates in 4180 / 4147 measured calls. `python tools/test_d64read.py` passed all 5 tests. Final log: `js/test/out/regression.log`. Both CRT variants and browser outputs are rebuilt. VICE visual validation remains separate; the user has confirmed Navigation Status highlighting works.
- Latest user verification: everything they tested in this CRT works. Two known follow-ups remain: menu hover still steps through intermediate choices (e.g. 1 through 9), and the `priority` label occasionally flashes. Direct menu selection and source-level paint suppression have not yet been implemented; preserve this tested checkpoint before starting them.

## Stable checkpoint

- Branch: `crash_fix_attempt`
- Commit: `38ce351 Unify mouse and native menu highlighting`
- The commit was built and its JavaScript headless test suite passed before the reports below. It makes menu-row hover drive the game's native selection (`$0774`) and uses the game's fire input on click, instead of painting a second menu highlight or translating a menu word into its first-character shortcut.
- `MOUSE-SUPPORT.md` documents that behavior.

## User reports still to debug (latest test)

1. `priority` briefly turns white for one frame when the first priority is selected.
2. Navigation / Display drag-and-drop does not reorder directly: it still needs a first click plus a second click to rank, and it tends to move the last element even if it was already ranked.
3. Clicking a Navigation / Status course selects it correctly but flashes unrelated rows as if a rank operation occurred.
4. "Raster interrupt cannot finish on time": highlighting a list item while ships are on screen (mostly Aft view) garbles the fore/aft view, flashes, and lags the game. No crash.

Also observed (design note, not a bug): menu-row hover now steps the native cursor through intermediate choices one word at a time instead of jumping. That is inherent to driving the game cursor with synthetic left/right pulses (one step per press/release pair, ~2 frames per word). Instant positioning would mean writing `$0774` and painting the cursor ourselves again — a design decision to make.

## Current uncommitted experiments (worktree, not committed)

- `ef/mouse_rom.asm`:
  - `RANKABLE` now jumps to an `RKNAV` extension (placed near the end of the file, after the time-critical code) that reports Navigation as rankable only when `TITLE+12` is `'-'` — i.e. `" NAVIGATION - POSSIBLE COURSES"` (Display), not `" NAVIGATION STATUS REPORT"`. This makes the drag preview (grey source row / yellow drop row) appear on Display and stay off Status.
  - `MKNAV` currently handles only a same-row click: `SAMEROW` equal → `MOLD=1`, rank the course to position `'1'` via `RANK`. A drag release (`RROW != PROW`) falls out via `BNE MKX3` and does **nothing** — this is exactly the observed "first click, second click" behavior.
  - `DRAG` sets `MOLD=0`; `RANK` checks `MOLD==1` after `RN2` and, if set, stores `ACT=2` and returns before the `FLT/FLLO/FLHI/FLTGT` flash setup. Intended to suppress the false rank-row flash on Navigation Status selections. Unverified, because the new Navigation test does not reliably reach the Status view.
  - `LABELS` is still called every frame from `VIS` (raster IRQ path).
- `js/test/run.js`: adds single-native-highlight checks, cyan/non-selectable `priority` checks, clickable Priority 1, and a tentative Navigation Status/Display block that currently fails (see test reliability below). Debug `console.log` lines were removed.
- Generated CRT/browser outputs (`docs/`, `js/ref/`, `js/programs.js`, `js/dist/`) are modified and must be rebuilt after any further source edit.

## Root-cause analysis (from disassembling `plus4d/mx.bin`)

### Report 1: the one-frame white flash on `priority`

Verified facts about the game's menu cursor:

- The game indexes the menu row with `Y = column - 1`: screen at `$5231,Y`, colour at `$DA31,Y`. `$0774` stores that index, so `$0774 = 9` means screen column 10 (the `1` in `" priority_1  "`).
- Joy-right handler `$8657..`: moves to the next word and calls `$9B7C`, which paints white forward from the word start to the first space (`LDA #$01; STA $DA31,Y` at `$9B85/$9B87`, loop `$9B7E-$9B92`).
- Wrap path (moving left from the first word) `$86A0-$86BA`: scans back from `Y=$27` to the last non-space character, stores `$0774`, then paints white backwards through the **whole word** until a space (`LDA #$01; STA $DA31,Y` at `$86AD/$86AF`, loop).
- For `" priority_1  "` the game treats `priority_1` as one word (the `_` is not a space), so the wrap path paints columns 1-10 white — the entire `priority` label, the `_`, and the `1`. Our `LABELS` routine then repaints the label/separator cyan on the next raster IRQ → the visible one-frame white flash. The prompt's steady state has `$0774=9` (column 10, the `1`), which matches our hover target `HOVD2-2`.

Proposed fix (not yet implemented): prevent the paint at its source instead of correcting it one frame later.

- Hook the two white-paint sites `$9B87` and `$86AF` (both are `STA $DA31,Y`, bytes `99 31 DA`) the same way the existing `WRC`/`WRX` sprite-store hooks work: replace the 3 bytes with `JSR` to a small RAM-part routine.
- The routine: read the menu character at `$5231,Y`; if it is lower-case (`'a'..'z'`) or `_`, skip the store (just RTS); otherwise perform `STA $DA31,Y`. Preserve Y; A can be clobbered (both sites reload `LDA #$01` per iteration — still use PHA/PLA to be safe); flags are safe because the following `CMP #$20` re-establishes them before the loop's branch.
- The game's own restore path (writes colour 3, cyan, around `$94B3`) already matches `COLLABEL`, so no other correction is needed once the white paint is blocked.
- The game's selectable words never start lower-case (`Status`, `At-will`, digits, `?`, `<-`), so skipping lower-case/`_` cells cannot hide a real choice.
- Caution: only hook verified instruction sites — a `99 31 DA` byte pattern that is an operand of another instruction would corrupt code. Disassemble around each candidate before adding it to `HOOKS` in `ef/efbuild.py`. The two sites above were verified by disassembly; also check whether the trainer bridge (`dx`, shifted addresses) has equivalent sites — the hook mechanism only patches files where the original bytes appear at that address.

### Report 2: Navigation Display drag-and-drop

`MKNAV` ignores drags today. Concrete fix plan:

```asm
MKNAV:  LDA TITLE+12    ; '-' = Display, other = Status
        CMP #'-'
        BNE MNAVSEL     ; Status: any click/drag selects the pressed course
        LDA RROW
        CMP PROW
        BEQ MNAVCLICK   ; Display same-row click: select to position 1 (with flash)
        CMP #LIST0
        BCC MNAVX       ; released above the list: ignore
        LDA #'N'
        LDX #0
        JMP DRAG        ; drag: DRAG computes the position from RROW, sets MOLD=0
MNAVCLICK:
        LDA #0          ; the list is visible on Display, keep the flash feedback
        STA MOLD
        LDA #'N' / LDX #0 / LDY #'1' / JMP RANK
MNAVSEL:
        LDA #1 / STA MOLD / LDA #'N' / LDX #0 / LDY #'1' / JMP RANK   ; Status: no flash
MNAVX:  RTS
```

- `DRAG` already: checks `RROW != PROW`, requires `RROW >= LIST0`, computes the target position from the release row, sets `MOLD=0` (flash on). Use `JMP`, not `BNE`, for the long jump — branch range was an assembler failure earlier.
- The "moves the last element even if already ranked" symptom is consistent with the current no-op drag path: the drag does nothing, then the follow-up clicks rank whatever row happens to be clicked (and the game's wrap/scan behaviour re-paints the whole word). Fixing the drag routing should remove it; re-test after.
- `MOLD` is safe to share between the IRQ path (`VPRE` uses it as preview-row scratch) and `MKEY` because `MKEY` runs through `ROMCALL` with `SEI` — the raster IRQ cannot interleave inside it.

### Report 3: Navigation Status rank flash on unrelated rows

- The flash comes from `RANK`'s shared feedback setup (`FLT`, `FLLO`, `FLHI`, `FLTGT` painting rows `FLLO..FLHI`). On Status those rows are status-table rows, not the priority list, so the flash paints unrelated content.
- The `MOLD=1` marker in the worktree makes `RANK` skip that setup (store `ACT=2`, return before `RN3`). Verify with a reliable Status-screen test: after clicking a course row, `$DFFC` (FLT) must stay 0 and the course must become selected (command record shows the rank, `$8AE7` ran).
- The drag preview is already suppressed on Status by the `RANKABLE`/`RKNAV` change.

### Report 4: raster interrupt overrun while highlighting

- `TPRE` (→ `MPRE` → `VIS`) runs **inside the game's split raster IRQ handler**, before the handler completes its `$D011/$D018/$D012` switch for the next split.
- Per-frame costs added inside that IRQ by our code: `LABELS` scans ~40 menu cells every frame (~600 cycles ≈ 1.5 raster lines); while the pointer is on a list row, `HOVER` re-runs the `ITEM` scan every frame (~300 cycles); `HVSET`/`HVPNT`/`PAINT` add ~40-cell colour writes on each change, and the rank-flash start frame paints up to `FLLO..FLHI` rows (worst case several thousand cycles in a single frame).
- If the added work pushes the split writes past the intended raster line, the split lands a frame late — matching the "lost raster IRQ settings" garble. In Aft view with ships the game's own handler is heavier (sprite multiplexing), so the timing headroom is smallest exactly there.
- Proposed fix, in order of impact:
  1. Remove `JSR LABELS` from `VIS`. With the `$9B87/$86AF` paint-prevention hooks from report 1, `LABELS` becomes a safety net only; run it from `TPOST` instead (main-loop context, interrupts enabled, once per frame, outside the raster-critical window).
  2. If more headroom is needed, cache the hover scan: skip re-running `ITEM` while the pointer cell (`CCOL`/`CROW`) is unchanged. Staleness is cosmetic (the preview colour lags a redraw until the pointer moves); the click path re-runs `ITEM` fresh in `MKL`, and the menu-row word scan is cheap, so correctness is unaffected.
  3. The rank-flash start frame (`VFL1`) paints multiple rows in one IRQ — if a single-frame glitch during the post-rank flash is unacceptable, spread the row paints across frames.
- Measure, don't guess: `tools/p4d.py` + the VICE remote monitor (port 6511) can watch the split registers; compare handler entry/exit cycles with and without hover before moving more code.

## Test reliability problem (run.js)

- The Navigation block in `playthrough` loads `idleBridgeState` (saved right after departure) and clicks the `Nav.` tab. The content area can still show the departure letter at that moment, and the block does not verify that each click actually landed: after clicking the tab it must assert the row-15 title (`NAVIGATION STATUS REPORT`) before clicking a course, and after clicking `Display` it must assert `NAVIGATION - POSSIBLE COURSES` before dragging. Without those assertions the checks fail for the wrong reasons and cannot validate the fixes.
- Suggested assertions once the flow is reliable:
  - Status: click a course row → `$DFFC` (FLT) stays 0, the course is selected.
  - Display: drag course A (row 17) onto row 20 → drag colour 12 on the source, 7 on the drop row while held; after release, row 20 column 2 shows `A` and the rows changed order.
  - Display: single click on a course → it moves to position 1 with the flash feedback.

## How verification was done so far

- **Only the JavaScript headless emulator was used; VICE was not run during this work.** The user's VICE testing is the only visual/raster confirmation so far — the raster-timing report in particular has not been reproduced in the JS emulator at all.
- Build/test cycle used:
  1. `python ef/efbuild.py`
  2. Copy `psi5_ef.crt` to `js/ref/psi5_ef_tested.crt`
  3. `python ef/efbuild.py --bridge`
  4. Copy `psi5_ef_bridge.crt` to `js/ref/psi5_ef_bridge_tested.crt`
  5. `python js/build.py`
  6. `python js/bundle.py`
  7. `node js/test/run.js`
- Suite status: commit `38ce351` passed fully. The current worktree (Navigation experiments) passes everything except the two new Navigation checks, which fail in both emulator timing modes because of the test-flow problem above, not necessarily because of the ROM changes.
- A JS-emulator 8-frame colour sample while clicking Priority 1 showed the label cyan on every sampled frame — it did not cover the prompt-entry transition, which the disassembly analysis above identifies as the actual flash source (the wrap-path paint).

## Useful game internals (verified by disassembly)

- `$0774`: menu cursor index, `Y = column - 1` over `$5231,Y` (screen) / `$DA31,Y` (colour).
- Joy-right move: `$8657`, forward paint `$9B7C-$9B92` (white `$9B85/$9B87`). Wrap (left from first word): `$86A0-$86BA`, white `$86AD/$86AF`. Cursor restore writes cyan (3) around `$94B3`.
- Menu-loop getkey hook (`TKEY`/`MKEY`) runs via `ROMCALL` with `SEI` — RAM-part scratch vars are safe from IRQ interleave inside it.
- `TITLE+12` distinguishes `" NAVIGATION - POSSIBLE COURSES"` (`'-'`, Display) from `" NAVIGATION STATUS REPORT"` (`'S'`, Status). Titles on row 15 start with a leading space, so first letters are at `TITLE+1`.
- Navigation's rank handler is `$8AE7` (per `RE-NOTES.md`); position is always `'1'` — "Rank" selects a course.

## Handoff state

- `38ce351` is committed and was fully green at its own build.
- Everything described under "Current uncommitted experiments" is uncommitted in the working tree, including the generated CRT/browser files.
- Nothing was changed after the user's latest test round except this document and the removal of debug logging from `js/test/run.js`.
- The user takes over debugging from here.
