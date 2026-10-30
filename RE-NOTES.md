# Psi-5 Trading Company: reverse-engineering notes

## Disk images

| Image | What it is | Notes |
|---|---|---|
| `PSI5.d64` | Crack by Headbanger: packed loader + `part1` (`$E000`), `part2` (`$A000`), `part3` (`$1000`, unpacked) | One fixed preset mission with no course or crew selection; probably the old side-B "preset" game. The v1 mouse patch (`PSI5-1351_v1.d64`) is for this one. |
| `PSI 5 Trading Company+.d64` | Wiseguy Industries 2015 | Intro menu: SPACE = course + crew selection, 1/2/3 = the three preset missions from the tape's B side. Slow standard loading. |
| `PSI-5 +4D 101% ATA.d64` | Avatar 2020 (BCC#14), "101%", single-sided, Krill loader | **Target.** 4 courses. The KERNAL is switched off during play (`$01=$35`). Everything below is about this version. |

## Driving it in VICE (`tools/`)

The scripts use the remote monitor on port 6511.

| Script | Purpose |
|---|---|
| `tobridge.sh` | Boots, takes course 1, hires the first candidate of every department, accepts, presses RETURN, opens Engineering → Status (about 3 minutes) |
| `p4d.py boot / keys / shot / dump / mon` | Boot, key injection, screenshot, a 64 KB RAM dump, raw monitor commands |
| `callsub.py TARGET [A=..] ["> addr bytes" ...]` | Calls a game subroutine from the menu loop with no stub. It breaks at `$3EE9`, pushes `$3EE8` as the return address, pokes the given bytes, and sets PC (see below). |
| `catch.py "watch ..." KEYS` | Injects keys and reports checkpoint hits |

**Getting into the game:**
- **Front end:** it reads the matrix, so `keybuf` is no use there. Intro: poke `$091D=$FF` and `$0924=$00`. Trainer prompt: poke `$0D2D=$FF` (answers "no" to every question).
- **Never use `keybuf` on this version.** Its loader code sits at `$0277`, which is the KERNAL keyboard buffer; a typed key corrupts a branch and the loader hangs.
- **Course and crew screens:** key queue at `$CF00`, count in `$62` (getkey `$CFB7`).
- **Bridge:** key queue at `$03CA` (max 10), count in `$4E` (getkey `$3EE9`, called from the menu loop at `$8609`).
- **Codes:** keys are ASCII upper case (`E` = `$45`), RETURN = `$0D`, ← = `$14`.
- **Page `$0100` is not free.** The game uses it as a buffer, and a stub placed there crashed the game.

## Screen

Same as the other version:
- VIC bank 1: text screen `$5000`, bitmap colours `$5400`, font `$5800`.
- Menu row 14 (`$5231`), command line row 13, the department's list from row 15 down.
- IRQ: `$0314` -> `$8F40` (raster split, then `$8EA7`). The joystick read is the only `$DC00` read, at `$8FB1`.

## The menu tree

**Menu record** (Engineering at `$C1F0`; the department records are listed from `$BF20`):
```
"Status Display ? Cancel Rank Enable " $FF
$07                              item count ($46)
S D / C R E <-                   shortcut keys; bit 7 set = leaf (the command is complete)
7 words                          per item: pointer to the next node (sub-menu or prompt)
```

**The interpreter** is around `$8655-$8814`:
- `($0C)` points to the current node, `$37` is the depth.
- The chosen key goes into the **command record at `$2D,X`**: `$2D` = department letter, `$2E` = command, `$2F` = argument (item letter), `$30` = position, and so on.
- At a leaf (bit 7) it goes on to the **executor at `$8867`**.
- `$93E8` (the live redraw of the department screen) saves `$2D-$39` to `$042C` and restores it afterwards.

**Executor:**
- `$3FBB` (X = record offset) sets `$38` = department letter and `$39` = department index: N=0, W=1, S=2, R=3, E=4, other=5.
- It then dispatches on the command letter (`$8A4D`):

| Command | Handler |
|---|---|
| S Status | `$8AC8` |
| D Display | `$8ADC` |
| R Rank | `$8AE7` |
| C Cancel | `$8B52` (Nav `$8B58`, Eng `$8B69`, others: remove from list) |
| A Accel (Nav) | `$8BCA` |
| A Assign (Repair) | `$8C43` |
| F Fire (Weapons) | `$8DCB` |
| F (other) | `$8C04` |
| E Enable (Eng) | `$8E8E` |
| E Examine (Scan) | `$8CFC` |
| P | `$8E93` |
| `Q` (main menu) | restart, `$89C1` |

## Engineering data

| Data | Location | Notes |
|---|---|---|
| Device states (Status list A–L) | `$58CC + n` (n = 0–11) | bit 7 = enabled (`$81`/`$01` = enabled/disabled for the battery, `$00` = off) |
| Pending requests | `$07E0 + n` | `$80` = waiting for the engineer (shown as RqE/RqC) |
| Status texts | `$5D2A` | `"RqE" "RqC" "yes" "no "` |
| Status page rows | base `$71E0`, row offsets at `$5CE4`/`$5CF4` | the "Enab" column is written by `$95AC` |
| Department list pages | lo/hi pointers at `$5C62`/`$5C6C`, indexed by `$39`; column offsets at `$5CDE` | `$94D2` (Y = `$39`) collects the item letters into `$1B..` and the count into `$1A` |

## Direct calls (tested in VICE)

**Enable/Cancel a device:** `$2F` = device letter (`'A'`+n), then `LDA #1` (Enable) or `#0` (Cancel), `JSR $95AC`.
- Device F (Blaster) → the engineer processed the request within a second, and the Status list shows "no".
- If the device is already in the wanted state, `$95AC` just writes yes/no and clears the request.

**Rank:** `$2F` = item letter, `$30` = new position (`'1'`…), `$38`/`$39` = department (Eng = `'E'`/4), `JSR $8AE7`.
- Engineering Display: F "Charge Shield Batt" went to priority 1, and A–E renumbered to 2–6.
- The same routine works for the lists of the other departments. In Nav (`$39`=0) the position is always `'1'`: "Rank" selects a course.

**Rules for a patch** that calls these:
- Call them from the main loop, at the menu loop's getkey (`JSR $3EE9` at `$8609`), never from the IRQ.
- Save and restore `$2D-$3A`, as `$93E8` does, so a half-entered command isn't destroyed.
- Read the clicked item's letter from the screen (column 1, or column 21 for devices I–L). Tell the lists apart by the title on row 15: `"ENGINEERING STATUS REPORT"` (devices) or `"... POWER CLASS PRIORITIES"` (classes).

## Disk files of the +4D image

Extracted into `plus4d/*.prg`. All files are packed except `dp` (raw 127-byte depacker). `psi-5 docs /ata` is a text file; the `.CCC...` and `Bavatar...` entries are empty spacers.

**Packed format** (decoded from `dp`; `tools/krillpack.py` implements it and was checked):
```
PRG load address L (2 bytes), then the stream:
  [last byte][x][y]    P = y:x; the first output byte goes to P+1; "last byte" is the final output byte
  10nnnnnn             copy n+1 literal bytes that follow (1..64)
  0eeeeddd v           match of length e+2 (2..17), distance 2048 - ddd*256 - v (1..2048)
  11nnnnnn             match of length 2, distance 255-c (c = $C0..$FE)
  00                   end
  [trailer]            optional raw bytes loaded after the end of the data
```
- The stream ends at the end address of the unpacked data, so it is unpacked in place. The write pointer must never pass the next unread byte (the slack is 0 at the end token in every original file).
- A match with length 2 and distance over 1792 would give control byte 00 (= end), so it is not allowed.
- The optimal-parse encoder gives the same size as the original packer for `mx`, and equal or smaller for the others.

| File | Unpacked address range | Role |
|---|---|---|
| `b` | `$5400-$9EFF` | crew selection / mission start phase (the first file loaded after "accept crew"; its code was overwritten later) |
| **`mx`** | **`$81C2-$BB1F`** (+5 byte trailer) | **the bridge program** for the no-trainer game: 98% identical to the RAM image at the bridge, and the engine code `$8600-$9840` is 100% identical. The menu records at `$BF20+` and all routines in this file are the ones in the notes above. |
| `dx` | `$81C2-$BB17` (+13 byte trailer) | a similar bridge program **with trainers** (8 bytes shorter, different code layout, probably used when trainers are chosen); has to be patched separately if wanted |
| `c`, `h`, `ma`, `t`, `de`, `di`, `f`, `l`, `p`, `u`, `accolade inc`, `copyright 1985` | see `krillpack.py unpack` | graphics, texts, screens and tables for other phases |

**Tools:**
- `tools/krillpack.py unpack|verify|repack`: decode a file to raw data, verify encode(decode) = same data, and repack patched data (the trailer is kept).
- `tools/d64put.py DISK name NEW.prg [OUT]`: replaces a file's contents in a D64, keeps its directory entry, frees or takes sectors in the BAM.
- Checked in VICE: `plus4d/test_b.d64` (with `b` and `mx` repacked **unchanged**, `mx` as a new byte stream of the same size) boots through course selection, crew and the bridge to the Engineering screen, and the engine code is byte-identical to the original run.

## Free memory in the bridge phase (analysis, no result yet)

Static analysis of the RAM image at the bridge (`tools/t_b1.bin`, taken from the repacked test disk) and of all unpacked files:
- **No bridge file has a free stretch:** the unpacked `mx` has no run of 24+ identical bytes (00/20/FF/EA); every byte range up to `$CFFF` is covered by some file; `$0800-$39FF` = `di`, `$3A00-$CFFF` = `ma` (only 54% still in place at the bridge), `$E000-$FFFF` = `l` and `de`.
- **Candidates that turned out to be used:**
  - `$4000-$41FF` (512 zero bytes) is a work buffer (cleared at `$B18E`, written by `$9CFA...`).
  - `$81C2-$8287`: part of it is a saved screen line (`$81F7..`), plus `$8285`.
  - `$5000-$5207` (the text screen rows that are not displayed) holds **code** called as `$5017/$5020/$5025/$5036`.
  - `$7040-$7FFF` (the bitmap rows not displayed) holds the six department list pages.
  - `$0100-$01E3` and `$0374-$03F2`: the stack page and the depacker/key queue; `$8000-$81C1` belongs to the overlay `u`, which carries a `CBM80` signature at `$8004` (the cartridge-style start code of this release).
- **Still open (need a run-time access test):**
  - `$0334-$0373` (64 bytes);
  - `$0100-$01BF`;
  - `$CBCC-$CC3F` (116 zero bytes, the tail of `c`);
  - `$4300-$4DFF` (sparse, maybe sprite/graphics data);
  - `$3500`, `$1F00` and `$2F00-$30FF` (zero/space-heavy pages inside `di`).

  Method: `watch load` + `watch store` on the candidate pages, then play every department for a few minutes, with hits logged (`tools/p4d.py` and `tools/callsub.py` already give the key injection).
- **If nothing is free:** the patch must be smaller. A mouse-as-joystick patch (no sprite) needs about 150-250 bytes; a pointer sprite needs 64 bytes of shape data in the VIC bank (`$4000-$7FFF`) plus about 400 bytes of code for hit-testing and the direct calls.

## Free memory: test results (marker fill + department tour) and the install problem

- **Result of the run-time test** (`tools/filltour.py`: fill with `$55`, tour all departments with injected keys, about 2 minutes in warp):
  - `$2F60-$30A0` (321 bytes): never written during play.
  - `$CBCC-$CBE3` and `$CC0C-$CC3F`: untouched.
  - `$CBE4-$CC0B`: used.
  - `tools/memtour.py` (VICE `trace` checkpoints) floods the monitor connection; don't use it on busy areas.
- **The bridge uses sprites:** `$E040` sets `$57F8+n = n` (blocks 0-7 = `$4000-$41FF`) for the ships in the viewscreen. A sprite pointer has to be multiplexed below the split at raster 154 (text row 13), with a 64-byte shape inside the VIC bank. The disk patch (`mouse4d`) used a colour-flipped character cell; the EasyFlash version uses sprite 7 multiplexing (see below).
- **Why the patch can't simply go into a file at `$2F60`:** when the bridge starts, the routine at `$CC34` in **`c`** copies `$4000-$63FF` to `$1C00-$3FFF` (`STA ($12),Y` at `$CC47`, found with a watchpoint). `$4000-$63FF` is built at run time; no file has these bytes. Bytes patched into `di` at `$2F60` would be overwritten by that copy.
- **What's needed:** an installer that runs after this copy (patch `JMP $CE81` at `$CC59` in `c`) and copies the patch code to `$2F60`/`$CBCC`. The installer and the code bytes need ~360 bytes somewhere in RAM at that moment:
  - `c` has no free run;
  - `$CEE4-$CFFF` (after `c`) is not tested, and `$CF00` is the front end's key queue.
- **The patch itself is written and fits** (`mouse4d/psi5_4d_mouse.asm`):
  - main code `$2F60-$309C` (317 bytes), helpers `$CBCC-$CBDC`, variables `$CC0C-$CC18`;
  - colour-flipped cell pointer on rows 13-24, mouse in port 2;
  - a click on the menu row types that word's shortcut key into the game's key queue, and outside menus a click is fire;
  - list clicks (device toggle, drag to rank) are left for v2: no room.
- **`mouse4d/build.py`** puts the hooks into `mx` and repacks `mx`/`di`/`c`. It still needs the installer step. The new disk leaves out the 38-block docs file, because the original has 1 free block.
- **Option 1 (installer stash after `c`) checked: not enough room.**
  - `ma` loads after `c`'s copy routine and zeroes `$CBCC-$CC3F`, so the code can only live in `$2F60-$30A0`. The variables can stay at `$CC0C`.
  - The shaved code needs ~316 bytes plus ~25 for the installer, but `$CEE4-$CFFF` is only 284 bytes.
  - The list template text that ends up at `$2F60` is in `ma` (`$7839`) and `h` (`$B039`), at other addresses: the copy source at `$5360` is assembled at run time, so patching a file does not carry code there.
- **Remaining routes:**
  1. Find the code that builds `$4000-$63FF` before the copy, and make it take our bytes.
  2. Stash under I/O (`$D000+`), if the Krill loader can load there.
  3. EasyFlash (`$DF00` RAM + ROM).
  4. A smaller feature set (no pointer).
- **EasyFlash alternative (chosen):** 256 bytes of cartridge RAM at `$DF00`, plus ROM banks, gives room for the code and the installer. It also replaces the disk loading.

## EasyFlash version (`ef/`, `psi5_ef.crt`) - works

- **Build:** `python ef/efbuild.py` writes `psi5_ef.crt` (23 banks).
  - **Snapshot:** `tools/snap.py` takes the machine state at the trainer prompt: `snap_ram.bin`, `snap_col.bin` (colour RAM), `snap_io.txt` and `snap_cpu.txt` (PC `$0CAD`, SP `$F6`).
  - **Files:** stored as the bytes each load leaves in memory: the raw load at L, then unpacked at P.
- **Boot** (`ef/ef_boot.asm`, bank 0):
  1. The Ultimax reset stub at `$FF00` switches to 16K mode, then jumps to `$8000`.
  2. The boot copies the resident code to `$DF00` and restores RAM `$0200-$CFFF` and `$E000-$FFFF`. The `$D000-$DFFF` RAM goes through `$1000` with `$01=$34`, then colour RAM, VIC registers (raster compare `$99` for this snapshot, `$DD00` from the snapshot), and the CIAs (interrupts off; the boot also re-sets the CIA2 TOD alarm).
  3. Zero page and stack come last, then `GO` in `$DF00` RAM: cartridge off, registers, `RTI` to `$0CAD`.
- **Loader** (`ef/ef_res.asm`, resident in the EasyFlash RAM `$DF00-$DFF9`):
  - `$0200` (raw) and `$020B` (load + unpack) are patched to `JMP RAWLD` / `JMP CDLD`.
  - The name (X/Y, length `$B7`) is first copied into a buffer: it can lie under the cartridge window, e.g. `$8020`.
  - The loader then searches the directory at `$9E00` (bank 0) and copies the file from the banks.
- **Mouse** (`ef/mouse_ram.asm`, `ef/mouse_rom.asm`):
  - **ROM part:** bank 1, with the jump table at `$8000` (`MPRE`, `MJOY`, `MKEY`). The trampoline sets `$01=$37`, selects bank 1 (`$DE00=1`) in 8K mode (`$DE02=$06`, ROML at `$8000`), calls the ROM, then switches the cartridge off (`$DE02=$04`).
  - **RAM part:** `$0210-$02FF` holds the trampolines, variables, sprite wrappers and the `TSPR`/`TTOP` stubs; the pointer's register code is in the ROM part (`MSPR`, `MTOP`). `$0334-$03F2` looks free on the bridge but is overwritten during loading. The game's key queue at `$03CA` is left alone.
  - **Hooks** (in `mx` and the RAM image): `$8F2D` (`JSR $8FA5` → `JSR TPRE`), `$8FB1` (`LDA $DC00` → `JSR TJOY`), `$9005` (`JSR $3E72` → `JSR TPOST`) and `$8609` (`JSR $3EE9` → `JSR TKEY`). Sprite hooks: `$8EFF` (`JMP $8F95` → `JMP TSPR`), `$8F40` (`STA $D018` → `JSR TTOP`), `$E8C8`/`$E8F1` (`STA $D000,Y` → `JSR WRX`), `$E8D3`/`$E8FC` (`STA $D001,Y` → `JSR WRY`), `$E88A` (`STA $D02B,X` → `JSR WRC`) and `$E90B`/`$92ED`/`$9387`/`$9437`/`$B920` (`STA $D015` → `JSR WRE`).
  - **Pointer:** sprite 7, multiplexed. Shape in block `$82` at `$6080`: written at raster `$82`, frame art written back from ROM at `$2D`; the text screen's sprite 7 pointer is `$53FF`. Registers: `$D00E`/`$D00F` (X/Y), `$D010` bit 7, `$D02E` (colour) and `$D015` bit 7 (enable). If the first byte at `$5780` changes, the ROM part copies the 63-byte shape back. The wrappers send the game's stores for sprite 7 to shadow variables (`SHX`, `SHY`, `SHC`, `GEN`); `TTOP` restores the ship above the split.
  - **Clicks:** a menu-row click pushes the word's first character into the key queue at `$03CA` (count `$4E`); `?` becomes `/`, and anything below `/` is the back arrow `$14`. On a list row, `ITEM` reads the item letter from the clicked column (first column or the second device column). If the game asks for a letter or number (one-character word on the menu row), it types that item letter or row number. Otherwise it acts by title: Engineering Status toggles a device (`$95AC`); Engineering Display, Weapons, Repair and Scan detailed lists drag to rank (`$8AE7`); Navigation selects a course (`$8AE7`, position `'1'`); Scan Status examines (`$8CFC`); Repair Status types Assign and its letter. `SAVE`/`RECBUF` keep `$2D-$3A` and restore it afterwards.
- **Tested in VICE (`-cartcrt`, no disk):** trainer prompt → title → course list → crew → bridge → Engineering status.
- **Known limits:**
  - **QUIT (restart)** uses the KERNAL LOAD from disk (`$89D5`) and will fail without a disk; not handled yet.
  - **Trainers:** the game always starts at the trainer prompt (from the snapshot).
- **Pitfalls found:**
  - My assembler encodes a self-modified `STA $0000` as zero page: force absolute with `.byte $8D` + `.word`.
  - The CRT needs colour RAM restored separately.
  - The Krill loader lives at `$0277`, so never use VICE `keybuf` there.
- **Next:** test the other departments' lists, then mouse on the crew selection screen, mouse in port 1 and QUIT/restart.

## Next steps

1. Test the list clicks in the other departments (Weapons, Scan, Nav, Repair).
2. Mouse on the crew selection screen.
3. Mouse in port 1.
4. QUIT/restart without a disk.
5. Decide about `dx` (trainer version).
