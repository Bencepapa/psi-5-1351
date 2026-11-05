# Bridge UI redesign plan

## Navigation

Use the top line as a permanent department tab bar. The active department is written in full inside a fixed 12-character field; the others use fixed abbreviations so the row remains within 40 columns. Centre each active name in that field (`Engineering`, the longest at 11 characters, gets the unavoidable single padding cell).

Example for Scanning:

```text
?12 Weap   Scanning  Nav  Eng  Rep  *
Status Display ?3 Examine           <-
```

The reverse-video active field, not printable brackets, supplies the tab shape. Example active fields:

```text
|   Weapons  |
|  Scanning  |
| Navigation |
|Engineering |
|   Repair   |
```

The `|` characters above are width guides only. Keep every compact field at five cells: `Weap `, `Scan `, `Nav  `, `Eng  `, `Rep  `. Replacing any one five-cell field with the same 12-cell active field makes the total row width constant and shifts later tabs by the same seven cells regardless of department. Exact starting columns should be derived from these field widths in one shared table used by drawing and mouse hit-testing.

`?` plus the total count glyph is the global Acknowledge/message entry; clicking it opens the unfiltered Acknowledge screen. With no messages only `?` is shown.

Decided after the mockups (2026-11-03): every tab shows its pending-message count right after the name, as one custom glyph: an inverse digit in a rounded box, drawn in white, `1`-`5`, or `+` for six or more, and nothing for zero. Each compact tab is name + count + one space (`Weap❷ Scan❸ Nav❶ Eng❹ Rep `: 4-letter names take 6 cells, 3-letter names 5); the active department takes a 12-cell field (name and count centred) plus one space. With `?` + count + space at the left (3 cells, the total uses the same glyphs) and the back arrow fixed in column 39, the widest case (Navigation, Engineering or Repair active) fills all 40 columns; with Weapons or Scanning active one cell stays free before the arrow. Tabs after the active one shift, so the hit-test table is built from the same field widths.

Count glyphs: the six codes `$B8-$BC` and `$CC` in the bridge charset at `$5800` (the first choice, `$02 $5F $B8 $1D $9A $CC`, broke the Repair list: some unused-looking characters are game data, see RE-NOTES). None of them appeared on the text screen (`$5000`) in a tour of every department's Status and Display, Acknowledge and 6000 frames of play; the top view uses its own charset at `$6000`. Bit 7 is not reverse video in this charset (those codes are other glyphs), so the active tab is marked by colour (white) only.

The last cell of the tab bar (column 39) is the back arrow `$7F` while a department is open. A gear icon would need a seventh free glyph code; all six go to the counts, and `*` (`$2A`) cannot be reused because Repair (and maybe Weapons) uses it to mark outstanding work. So the back arrow stays. The cell is at the right edge, which may be hard to hit with the mouse; keep it there and test it.

Keep the back arrow as the last item of every department command row too. Left click on either arrow goes to the home state: the text area is empty, the tab bar shows only the abbreviated tabs with their counts (no active field, so there is plenty of room), and only in this state the last cell becomes Quit (there is no room for in-game settings, so Settings stays in the startup Advanced list). Row 14 is empty in the home state or shows a short status line, for example the ETA to the destination and the remaining cargo (the variables still have to be found). Right click remains Back/Cancel during a multi-step command. Both paths should use the game's existing back behavior rather than creating a second state-reset path.

The active tab should look connected to the second row. In standard text mode the VIC-II has one shared background colour, so independent rectangular tab backgrounds are not available from colour RAM alone. First implementation:

- dark blue background for both menu rows;
- inactive tabs in green or light blue text;
- active tab in white, bounded by PETSCII separators or reverse custom characters;
- white remains hover, yellow remains drag/drop feedback.

This avoids another cycle-sensitive raster split. A later custom-character version can draw filled tab caps if the visual distinction is not strong enough.

### Experiment: department background colours

Test only, not a decision: colour by department, using the colours the crew selection screen gives each department (its department colour table at `$0800`).

- **Option A, whole text area:** the text area's background is `$D021`, set from `$3A07` by the IRQ at `$8F27` (raster `$AA`). Set it per department; no new raster split is needed. Risk: the list text is black, white and red, so some department colours will be hard to read, and white (hover) or yellow (drag) may disappear on light backgrounds. Check every department with list, header and red text.
- **Option B, second menu row only:** keep the text area as it is and colour just the command row (row 14). Both menu rows get their blue background from `$8EF9` (`LDY #$06`) at the text split, and it lasts until `$8F27`. Colouring only row 14 needs a background change between row 13 and row 14 (raster about 162), which is a new, cycle-sensitive split. Alternatively, colour the tab bar row too and keep both menu rows in the department colour, which needs no new split.
- Mockups (JS, Engineering status in every department colour): Option A reads well with lighter colours: Weapons light blue, Scanning light red, Engineering light grey, Repair light green; there is no light purple, so Navigation stays purple or uses cyan. Option B needs yellow (not black or green) tab and command text; the active tab stays white. Decision (2026-11-03): Option B, the two menu rows only, in the department colour with yellow tab and command text, the active tab white and the count glyphs white. The text area keeps its original colours.
- Judge both on the real machine and in the JS page: legibility of black/white/red text, the white hover, yellow drag preview and blue flash, and whether the active-tab look still works.


## Input in the New UI

The New UI is played with a pointer. The 1351 mouse drives it directly; a joystick in port 2 also moves the same pointer (fire = left click, fire held while moving = drag), so the game stays playable with a joystick. Joystick and mouse share port 2: the mouse's right button reads as joystick up, so the joystick-pointer mode must only apply while no 1351 is detected (`MOUSEON`), and right-click Back has a joystick equivalent only through the on-screen back arrows. The keyboard is no longer a complete control method: Rank is replaced by dragging, so ordering lists needs the pointer. Most keyboard control goes, to free memory, but veteran players should keep quick access: the department keys stay (the original main menu already has `A W S N E R Q`; the tab bar can also map `1`-`5` to Weapons..Repair and `0` to Acknowledge). `F` for Fire may stay; other command letters (and the A/B/C, 1/2/3 item keys in prompts) are removed or decided later, based on the menu analysis of what each one costs.

## Common commands

- Entering a department opens its Status view by default. Status selection itself only changes page pointers (`$8AC8`); it does not start department work.
- `Status` and `Display` keep those exact names in every department. They are an iconic part of the bridge UI and become direct view tabs rather than command-tree steps.
- `Rank` disappears from the menu; drag ordering on Display calls the existing `$8AE7` handler.
- `Cancel` disappears where selecting an item and right-clicking can express removal/cancel safely.
- Every department command row keeps its original `?`, expanded to `?N`. It opens Acknowledge pre-filtered to that department; Back returns to the exact department and Status/Display view that was previously visible.
- The top-row `?NN` opens the original unfiltered Acknowledge view. Its badge is the total pending count; the department command-row badge is only that department's count.
- Department tabs are always clickable, without returning through the main menu.

Badge digits are informational, not separate buttons. Hovering or clicking `?NN`/`?N` acts on the complete control. The count should update from the same pending-message state used by Acknowledge, not from a second UI-maintained counter.

### Message capacity

The game has five independent FIFO queues with a hard limit of eight pending messages per department. Duplicate message types are ignored; a ninth distinct message discards that department's oldest entry. Therefore:

- department badge range: `0-8`, exactly one digit;
- global badge range: `0-40`, two digits;
- global count is the sum of the five queue lengths, not a separate game counter.

The authoritative queue end pointers are `$FFE8-$FFEC`; queue bases are `0,8,16,24,32`. Badges should derive their counts from these pointer differences.

## Modal commands

The department/tab row is permanent only while browsing Status/Display or waiting for a new command. Some original interactions need both command rows, so an active multi-step command temporarily owns both rows:

```text
Weapons Fire - Target A - Shots
At-will 1 2 3 4 5 6 7 8 9       <-
```

```text
Repair Assign - Device C
1 2 3 4 5 6 7 robodroids        <-
```

```text
Acknowledge messages - Auto Answer
Enabled Disabled                 <-
```

Rules:

- row 13 becomes a non-interactive command title/context line;
- row 14 contains only the choices for the current step and Back;
- the content area remains useful context where possible, such as Scan contacts during Fire and Repair Status during Assign;
- completing or cancelling the command restores the department row and its previous Status/Display view;
- right click performs the same Back action as the visible arrow;
- modal title words never receive mouse hover because they are not choices.

The manual explicitly calls out that the original UI can monitor one department's Status or Display while issuing commands in another. The redesign should not lose this capability accidentally. Default Status applies only on a normal department switch; an active command flow owns the content area until it completes or is cancelled.

## Processing delay

`Processing Command` is presentation, not synchronization. In the normal `mx` bridge it initializes `$076C` to `$56` at `$8839`, waits about 81 PAL frames (roughly 1.6 seconds), flashes the line and repeatedly runs the normal live updater `$93E8`. The selected command handler runs only after this wait. Status and Display merely select page pointers after the delay.

Removing the delay is safe for command execution: simulation and crew updates continue from the normal menu loop. It does change pacing because commands take effect sooner and the player no longer gives the simulation 1.6 seconds per action.

Recommended setting:

- `Instant` (default): keep cleanup through `$882D`, then jump from `$882E` to executor `$8867`;
- `Brief`: timer `$14`, about 0.38 seconds PAL;
- `Classic`: original `$56`, about 1.6 seconds PAL.

The trainer bridge `dx` has shifted addresses and an original `$FF` delay, so it needs a separate patch. Until a safe shared configuration byte exists, implement this as a D64/CRT build option rather than EasyFlash-only state.

## Weapons

The original Fire command is:

1. shots: `At-will`, `1` through `9`;
2. weapon: Missiles, Blasters, Cannons, Thermos;
3. target: a dynamic Scan ID;
4. insertion priority.

`At-will` means an ongoing firing order; a number authorizes that many shots. The final priority is the same queue order shown by Weapons Display and changed by Rank, so the redesigned Fire flow does not need to ask for it.

Proposed flow:

1. Fire opens a target list based on Scan Status (`$7040`).
2. Each target shows ID, class, friend/foe, lock and abbreviated position/range.
3. Selecting a target opens weapon and shot-count choices.
4. Confirm adds the order at the end of the queue.
5. Weapons Display reorders orders by drag through `$8AE7`.

The original `$8DCB` handler validates only that the Scan ID still exists. It does not reject friends, unlocked targets or out-of-range targets. The new UI should preserve that game rule but show strong warnings. Targets with an existing firing order should be disabled, matching the original dynamic menu.

Auto-opening Weapons Status must not happen in the middle of Fire. Fire replaces the content area with its Scan-backed target picker, preserving the useful Scan/Weapons relationship without relying on the old screen remaining underneath the prompts.

Keep the first version of the shot count (`At-will`, `1` through `9`) and weapon selection unchanged. They carry real game rules and collapsing them now would obscure whether an order is continuous and which weapon resource the player requested. Simplify only the target selection and final priority step first.

Suggested command row:

```text
Status Display ?3 Fire              <-
```

### Autonomous Weapons orders

When the Weapons crew becomes idle, its update routine chooses an eligible tracked target and an operational weapon, then calls the normal Fire handler `$8DCB` with priority 1. The resulting order is an ordinary Weapons Display row: its shots, weapon, target and status are visible and it can be cancelled or reprioritized. The original row has no persistent player/crew provenance flag, so the redesign must not claim that it can reliably label old rows `Auto` without adding new state.

## Scanning

Keep the two original views and terminology:

- `Status`: all detected contacts, up to 16, with ID, class, friend/foe type, lock and position. Activity marks show examination and outstanding Weapons orders.
- `Display`: the prioritized examination list, up to 8, including target ID/class/type, lock, damage, priority, position/range and suggested weapon.

Proposed interaction:

- clicking a Status contact selects it and exposes `Examine` as the primary action;
- `Examine` adds it to Display at the end unless it already exists;
- Display rows drag to reorder through `$8AE7`;
- a row-level remove action replaces the old Cancel prompt;
- known/unknown fields remain visually distinct; do not manufacture data before the crew discovers it.

Suggested command row:

```text
Status Display ?3 Examine           <-
```

When idle, Scanning selects an unexamined contact and calls the normal Examine handler `$8CFC` with priority 1. It therefore appears as a normal Display row and remains removable/reorderable. As with Weapons, the original row does not remember whether it was created automatically.

## Navigation

Keep the original views:

- `Status`: standard/requested/current course, requested/current speed, evasive state, ETA/relative ETA and risk for each route;
- `Display`: the five possible courses and their current priority/selection order.

The route names and risk information belong in Status; the shorter Display remains the direct course chooser. Selecting or double-clicking a Display row calls the existing Rank behavior, which for Navigation promotes that course to position 1. Dragging may also be allowed, but must not imply that all five routes are executed as a work queue.

`Accel` remains a compact form with speed and `Standard`/`Evasive` choices. The original Navigation Cancel only eliminates evasive maneuvering, so replace its ambiguous name with an explicit `Evasion off` action while retaining the same handler.

Suggested command row:

```text
Status Display ?3 Accel Evasion off <-
```

Navigation does not create bored/automatic command rows. Its status changes continuously as the navigator flies the selected course.

## Engineering

Keep the original views:

- `Status`: the 12 devices A-L, their descriptions and enabled/request state (`yes`, `no`, `RqE`, `RqC`), plus both battery charge/remaining-time values;
- `Display`: the six power classes, priority, power drain and active level (`yes`, `no`, partial/brownout).

Proposed interaction:

- click a Status device to select it;
- show `Enable` or `Cancel` according to its current/requested state, or use one direct toggle affordance while preserving `RqE`/`RqC` feedback;
- drag Display rows to reprioritize through `$8AE7`;
- keep power demand and partial activation visible because they explain Navigation speed shortfalls and weapon/shield availability.

Suggested command row:

```text
Status Display ?3 Enable/Cancel      <-
```

Engineering Cancel is not a queue removal: it requests that the selected Status device be disabled. The redesign must not reuse a generic Display-row delete action for it.

## Repair

Keep the original views:

- `Status`: ready/total robodroids followed by up to 16 repairable items with ID, description and ETR. `*` means currently being worked on; the blinking check means a repair order exists.
- `Display`: up to 8 ordered repair jobs with device ID/description, robodroids, priority and ETR.

`Assign` has two independent choices: the damaged item and the desired number of robodroids. The Display's robodroid field represents both current workers and assigned/requested workers. They can differ because a reassigned or finished droid spends time returning, collecting tools and receiving instructions before becoming available again.

Proposed interaction:

1. Click a Status damage row.
2. Open a small `Droids 1-7` selector, limited by the game's accepted range but not misleadingly limited to only the currently ready count.
3. Confirm by calling `$8C43`; a new job is appended and can then be dragged to its desired priority.
4. Clicking Assign for an item already on Display updates its requested droid count and can move its priority, matching the existing handler rather than creating a duplicate job.
5. Display rows drag to reorder and expose a direct remove action.

Suggested command row:

```text
Status Display ?3 Assign             <-
```

### Automatic Repair jobs

When idle, Repair takes the first available repairable Status item, chooses a crew-dependent default robodroid count and calls the normal Assign handler `$8C43` at priority 1. This creates or updates an ordinary Display job. It is visible, cancellable and rankable; there is no separate hidden repair activity and no durable `Auto` marker in the original job row.

The UI should therefore treat Display as the complete source of ordered repair work. Status can show damage being worked even during droid transit, while Display explains requested versus actual workers.

## Acknowledge

Acknowledge is not another work department and should not receive artificial Status/Display pages. It is the message reader and filter reached globally through `?NN` or department-locally through that department's `?N`.

Do not put counts into abbreviated filter names. Use row 13 as an overview and keep row 14 close to the original Acknowledge menu:

```text
Messages 12  Weap3 Scan2 Nav1 Eng4 Rep2
Weap Scan Nav Eng Rep Clear Auto <-
```

The first line is 39 cells at its maximum shown width and each department count is only one digit. The total and department digits use red reverse video but are not individually clickable. The second line fits after removing abbreviation dots, so `Clear` and `Auto` do not need to be merged. They have different original semantics and remain independently selectable.

Proposed layout:

- show pending messages as a readable list or one selected message in the content area;
- `Weap`, `Scan`, `Nav`, `Eng`, and `Rep` filter pending messages rather than switching crew departments;
- entering from a department preselects its filter; entering from the top-row global `?NN` starts unfiltered;
- show every one-digit department count and the two-digit total in the non-interactive overview line;
- `Clear` and `Auto` remain distinct special commands, not department filters;
- `Clear` is global: it resets all five queues, not only the current filter;
- `Auto` opens the two-row modal shown above and toggles automatic acknowledgement. Auto consumes and displays queued messages one at a time; it is not automatic clearing;
- when no messages match, retain the iconic `No messages pending.` state;
- the back arrow returns to the previously active department and view, not necessarily its Status page.

Do not turn Acknowledge into passive notifications only: reading and filtering the letters/messages is gameplay and can contain diagnostic clues. The global `?NN` merely removes the redundant long `Acknowledge` main-menu label while exposing the total pending count.

## Autonomous work rule

The manual's statement that Repair, Weapons and Scanning crew become bored maps to real queue insertion. All three autonomous paths call the same public command handlers used by the player:

- Weapons: `$8DCB` Fire;
- Scanning: `$8CFC` Examine;
- Repair: `$8C43` Assign.

Consequently their generated work appears in the normal Display list and obeys normal Cancel/Rank behavior. The redesign should not add a second `automatic activity` panel. If future UI wants to mark newly generated rows, that requires a new provenance bit or transient notification; it cannot be reconstructed reliably from the existing queue data.

## What the New UI can free (menu analysis, 2026-11-03)

The command handlers mostly have to stay. Only the keyboard menu around them can go. Callers found by scanning the bridge RAM for `JSR`/`JMP`:

| Handler | Entry | Callers outside the menu dispatch | Verdict |
|---|---|---|---|
| Rank | `$8AE7` | mouse `$0260`; Assign `$8C7E`, Examine `$8D39`, `$8E86`, P `$8E97` | stays (drag, and other commands use it) |
| Cancel (remove from list) | `$8B52` | game logic `$A192`, `$A8A7`, `$AAA9`, `$AAE5`, `$B723` | stays |
| Cancel Nav / Eng | `$8B58` / `$8B69` | none (`$8B69` calls `$95AC`) | small; replace by direct clicks |
| Assign | `$8C43` | autonomous Repair `$A1E9` | stays |
| Examine | `$8CFC` | mouse `$0266`; autonomous Scanning `$B448` | stays |
| Fire | `$8DCB` | autonomous Weapons `$AA22` | stays |
| Enable (Eng) | `$8E8E` | only `JMP $95AC` | trivial |
| Device enable/disable | `$95AC` | mouse `$025A`, Cancel Eng `$8B6B` | stays |

The real space is the menu machinery itself, in `ma` (not `mx`):

- `$BB1F`: `JMP $8814`, the "next" target of every leaf (keep or replace).
- `$BB22-$BEA5`, about 900 bytes: the item descriptions shown on the input row (`Status report`, `Rank power class`, `Cancel examination of target`, ...). The prompt strings (`? to leave pri`, `robos to device`) and the Acknowledge texts (`next message from WEAP.`) are mixed in, and the message reader still needs these.
- `$BEA6-$C40F`, about 1.4 KB: the menu nodes. A node holds the item text, the count, the keys (bit 7 = leaf), one description pointer per item and one next-node pointer per item except the back arrow (the interpreter at `$87D5` indexes them as keys + 2 x count + 2 x item). The prompt nodes are 5 bytes (flag, description, next), for example Cancel `$C246`, Rank `$C058` (then the position menu `STOP 1 2 ... 8`), Examine `$C1EB`, Assign `$C2DA` (`1 2 3 4 5 6 7_robodroids`), Fire `$C342` (`Missiles Blasters Cannons Thermos`).
- The interpreter `$8655-$8866`, about 530 bytes, in `mx`.

If the New UI fills the command record (`$2D`: department, `$2E` command, `$2F` item, `$30` position) itself and calls the executor `$8867`, as the mouse code already does for Rank, Enable and Examine, then the interpreter, the department nodes and the command descriptions are not needed: roughly 2 KB in total. That needs the department letter shortcuts to be reimplemented (a few bytes), the Acknowledge reader to keep its strings, and every command the New UI offers to be tested through the executor. Freeing them piece by piece (only Rank, Cancel, Enable) gains little, because their menu data is a few dozen bytes each.

## Plan: the New UI drives the executor directly

Goal: the New UI never uses the menu interpreter. It fills the command record and calls the game's own command code, so the interpreter, the department menu nodes and the command descriptions (about 2 KB) can be freed later. The Classic UI is not touched.

1. **Separate build.** `efbuild.py --newui` writes `psi5_ef_newui.crt`. The New UI patches are applied to the unpacked `mx`/`ma` images that the cartridge serves; the Classic CRT stays byte-identical. Later the post-crew choice selects which set the loader serves.
2. **One command entry, `DOCMD`, in the ROM part.** Input: department letter, command letter, item letter, position. It saves `$2D-$3A` (as `SAVE`/`RECBUF` do now), writes the record (`$2D` department, `$2E` command, `$2F` item, `$30` position), sets `$38`/`$39` through `$3FBB`, calls the dispatch `$8A4D` (not the executor `$8867`, so the Processing delay at `$8839` is skipped: Instant comes for free) and restores the record. The mouse's existing direct calls (Rank, device toggle, Examine) become `DOCMD` calls.
3. **Test every command through `DOCMD` in JS** before anything is removed: Status, Display, Rank (drag), Cancel in all five departments (queue removal, Engineering device off, Navigation), Enable, Fire with the weapon choice, Examine, Assign with the robodroid count, Accel, Acknowledge filters, Clear and Auto. Each test checks the same RAM effect as the keyboard path.
4. **Menu rows.** The tab bar (row 13) and the command row (row 14) are drawn by the New UI: department colour on both rows, yellow text, white active tab, the six count glyphs, the back arrow in column 39, the home state with Quit and the status line. One field-width table serves drawing and hit-testing. The joystick moves the pointer when no 1351 is found.
5. **Prompts that remain** become small New UI choices on row 14 instead of interpreter prompts: Fire's weapon (`Missiles Blasters Cannons Thermos`), Assign's robodroid count (`1`-`7`), Accel's speed. Rank's position menu (`STOP 1 2 ... 8`) is replaced by dragging.
6. **Keyboard.** The New UI's key handler maps the department letters, `1`-`5`, `0` (Acknowledge) and maybe `F`, then calls `DOCMD`.
7. **Cut over.** Redirect the main loop's call into the interpreter (`$8655`) to the New UI loop. Keep `$BB1F` (`JMP $8814`) and the Acknowledge strings until they are proven unused.
8. **Free the space.** Move the strings the Acknowledge reader and the remaining prompts need into a compact table, then reuse `$BB22-$BEA5`, `$BEA6-$C40F` and `$8655-$8866` for New UI RAM code. On the cartridge most New UI logic can stay in ROM; the freed RAM matters most for a later D64.

Verified in JS (2026-11-03, New UI bridge cartridge):

- Step 1 and 2 are built: `efbuild.py --newui`; the mouse's device toggle, rank and examine now go through the dispatch, and all 462 JS checks pass on both cartridges.
- The command record the interpreter builds is exactly the typed letters from `$2D` (department, command, arguments in prompt order), with `$14` after a leaf command, and the executor reaches the dispatch with X = 0. Checked with a CPU hook at `$8867`/`$8A4D` for Nav Accel (`N A 4 S`: speed, then Standard/Evasive), Nav Rank (`N R B`: course letter), Nav Cancel (`N C`), Scan Examine (`S E A 1`: target, priority), Eng Rank (`E R A 2`), Eng Cancel/Enable (`E C A`, `E E A`), Weap Fire (`W F 1 M A 1`: at-will or 1-9, weapon, target, priority), Status/Display.
- For department commands the executor adds nothing before the dispatch: `$886D` (`$3A` = 0) -> `$88DF`: `$2E` is not `/` and `$2D` is not `A`, so `$89B8`: `LDX #0`, Quit check, `JMP $8A4D`. Its only extra is the return address `$8AA1`; `$8AA2` resets the interpreter's menu afterwards, which the New UI does not need. So `DOCMD` = write the record, `LDX #0`, `JSR $8A4D`.
- Acknowledge (`$2D` = `A`) and the `/` shortcut are handled inside the executor (`$88EE`: Auto `E`/`D` -> `$07FE`; Clear zeroes `$55D9-$55DE` and calls `$C650`; filters via `$8915`), and Quit (`Q`) jumps to `$89C1`. The New UI calls those parts of the executor, or reimplements them, in step 7.
- Not covered yet: commands that need a filled list in this game state (Weapons/Repair Cancel, Repair Assign's device prompt), and Acknowledge.

Open questions: whether anything else reads the menu nodes (the mouse menu-row hover reads the native cursor variables `$0774`, `$4D`, `$3D`, which belong to the interpreter); how the input row's command echo is used by the game (it is part of the Classic look and goes away).

## Ideas (2026-11-04)

- **Message arrival:** when a message arrives the game plays a sound effect. At the same moment the matching count badge in the tab bar should flash (for example a few frames inverted or in another colour), so the player sees which department sent it. Hook: the message queue write at `$C6xx` (the write position `$FFE8+i` grows) or the sound trigger; the tab bar already redraws when a count changes (`NUSIG`), so the flash only needs a short timer.
- **Prompts beyond two rows:** the original squeezed every command into the two menu rows (the echo line on row 13, the choices on row 14), because that was all the space it had. The New UI can use other areas, for example the text area for a small form: Fire with the weapon, target and priority side by side, Assign with the robodroid count next to the damaged device. Most likely limited by memory.
- **Home overview in the text area (if the bytes allow):** at home (no department open) the text area is free. Opening a department shows its Status page, so home can show an overview of all five departments instead, one clickable block per department (a click opens that department). For example two rows each:
  - row 1: the full name, its message count, the length of its work queue (Repair: 10 jobs, Scanning: 2 targets, Weapons: 2 firing orders, Engineering: 3 devices powered, Navigation: the course) and a warning when something critical fails (for example life support);
  - row 2: a department-specific note (the next repair, the nearest target, ETA and speed, the battery state).
  Design it properly before coding (layout, colours, what matters most per department); the data comes from the same lists the Status/Display pages read.
- **Acknowledge overview:** the same idea for Acknowledge: every department's full name with its waiting messages, and a click opens the messages filtered to that department.
- **Course view instead of a star map:** the manual (`../psi5/manual.txt`) has no star maps. Navigation's design is five path variants towards the destination, which Status lists as courses: the shortest path, a medium deviation to port or starboard, a full port or starboard circumvention. For each it shows the ETA, the RETA (`-` early, `+` late) and a RISK column (only while the INF scanner works); the manual's advice is to watch RISK and change course to avoid overwhelming odds. So a visual view can show the real data: five lanes side by side (Full Port ... Standard ... Full Starboard), the current lane marked, each lane's risk as a bar or colour and its RETA, plus what Scanning has detected. A click on a lane selects that course (Nav Rank, as the mouse already does on the course list).
  Codex found the data (RE-NOTES, "Route and encounter map"): the encounters are authored per path and position (5 paths x 50 positions of 16-bit masks), and the game's RSK is the count of mask bits over the current position and up to five ahead. So a strip of the current position and the next few per lane can be drawn from existing data, no new map data. Fairness rule: show only what the game would tell the player anyway, so per-position counts (not ship types), and only while the INF scanner works (as RSK). Remembering what Scanning has examined would need new state.
  The author's "secret maps" (https://www.cerebus.de/psi5/code/tips.html, Ship Distributions for Kozzar-7, Zipo-Aga, Splyteux) confirm it was meant to be hidden from the player: per course A-E a column of 19 numbered rows with 0-4 ship icons of nine types (Skront, Scout, Narvik, Lepsor, Flarkan, Kifbok, Prato, Xantog, Zeltoad), described as guidelines that vary per mission. So the in-game view stays simplified: what the scanner would reveal.
  Wanted (user, 2026-11-05): per lane the ETA/RETA and, for the positions in scanner range, which ship types to expect (or at least how many different types), not just a colour or the RSK number. The encounter masks select types through `$3C61`, so the types are in the data. Ways to show them without free charset codes:
  - text: the game's own ship names, abbreviated (`Lep Fla Kif`), using the normal letters;
  - sprites: the ship shapes already exist for the top view (sprites), and the text area only uses sprite 7 (the pointer). Re-multiplexing the other sprites at the text split, like the pointer, gives up to 7 ship icons in a row, for example for the hovered or selected lane;
  - both: text in every lane, sprites for the lane under the pointer.
  Fairness: show types only for the positions the scanner covers (current and up to five ahead, as RSK) and only while the INF scanner works.
  Placement: Navigation's Display is the "prioritized list of possible courses" and its Rank only moves a course to position 1 (selects it). With lanes clickable, both are redundant in the New UI, so the lane view can replace Navigation's Display (Status keeps the ETA/RETA/RSK table), with no new menu item.
- **Feedback from the first VICE test (2026-11-05), done:** Weapons dark blue (6), home and Acknowledge neutral dark grey (11), Repair green (5, the darkest green the C64 has) with yellow/white text; light grey `|` separators between the tabs; Quit at home works (home clicks on rows 13-14 no longer fire the native main menu); the bar is redrawn when the game writes over it (row checksum), not only when the counts change; the counts no longer flicker (glyph codes moved).
- **Pointer on row 13:** the pointer cannot reach the top of row 13 (the sprite is set at the split, after line 154). Codex proposed setting the sprite registers earlier through a small RAM handoff at `$8ECE` (details in `.zen/split_findings.md`); open: where its 83 bytes can live safely (it suggested `$2F60`, which the bridge start overwrites).
- **The blinking cursor** (`~`, code `$7E`, animated by the game) is iconic: keep it somewhere in the New UI, place to be decided.
- **Engineering power flow:** on Engineering's power class list (Shields, Weapons, Engines, Scanners, the batteries) show where power flows and where not, for example a vertical line of the game's own animated characters (codes 2-7 are already animated gauges) next to the rows that are powered, and a broken/dim line for partial (`par`) or none.
- **Where the memory can come from:**
  - On the cartridge, RAM is the limit, not storage: only 23 of the 64 EasyFlash banks are used, so about 650 KB of ROM is free. New UI code, texts, tables and screen layouts can live in ROM and be copied to RAM only while needed, so nothing has to be compressed for the CRT.
  - Short tunes and sound data that sit in RAM permanently could move to ROM as well, if the player can be pointed at a copy made just before playing. Compressing them helps the D64 (where there is no ROM), but only after measuring how big they are: the music player is at `$C406`, its data has not been mapped yet.
  - The ~2 KB of menu machinery from the analysis above.

## Startup choice and settings

The choice between the two UIs comes right after crew selection, not in a boot menu. After Accept, and before the bridge files load, the player sees:

- **Classic UI** or **New UI**, chosen by mouse, joystick or key;
- **Advanced**, a short settings list.

Everything up to that point (trainer, title, course and crew) is shared by both UIs. The bridge files (`mx`, `ma`, `de`) differ, and they load after this screen, so the cartridge loader can serve the chosen set. The choice survives Replay. The simplest presentation is to rewrite the crew summary's text rows, as was done for the course and crew prompts, rather than drawing a new screen.

Advanced settings, all optional:

- Processing command delay: Instant / Brief / Classic (see Processing delay).
- Department colours: off by default, see Experiment: department background colours.
- Room for later small switches.

Storage: the settings must survive file loads. The cartridge's 256-byte RAM at `$DF00` is full, so a few bytes have to be freed there.

D64: the two UIs are two separate disks, so the Classic/New choice only exists on the cartridge. The Advanced settings can be offered after crew selection on both disks.

Memory limits: the bridge has no free RAM (the mouse RAM part fills `$0210-$02FF`, and every apparent gap has been in use). So settings must not grow the bridge code:

- prefer patching the loaded bridge code at load time over adding new resident code, for example the delay as a changed timer value or jump at `$882E`;
- on the cartridge, put any new logic in the ROM part, called through the existing trampolines;
- keep each setting small, and drop a setting rather than squeezing the Classic or New UI.

## Implementation phases

1. Keep the original handlers and command records; replace only navigation and rendering.
2. Add the Processing speed build option and default it to Instant.
3. Build the fixed-width department bar, global `?`, Settings entry and preserved back arrow.
4. Implement the Weapons target list and Fire form so Scan context is preserved.
5. Auto-open Status only on normal department entry, never inside an active command flow or when returning from Acknowledge.
6. Implement direct Status/Display interactions department by department, starting with existing mouse-supported actions.
7. Remove explicit Rank after drag ordering is verified for Engineering, Weapons, Scanning and Repair; keep Navigation's course-selection meaning explicit.
8. Replace each Cancel only after its alternative is tested; Engineering and Navigation require different UI because their Cancel semantics are not queue removal.

## Memory and disk compatibility

The final patch must use the same runtime layout for D64 and CRT. `$0210-$02FF` is not safe during long play, as the frame 58251 crash state proves. `$2F60-$30A0` survived the earlier bridge tour, but needs a disk-compatible installer after the game copies `$4000-$63FF` to `$1C00-$3FFF`.

Potential space sources:

- compress the in-game letters/messages and use the saved bytes for installer or UI code;
- reduce duplicated menu strings after the permanent tab bar replaces command records;
- share renderer and hit-test code between departments;
- keep large static text/layout data packed on disk and in EasyFlash ROM, with only the active screen in RAM.

Before choosing a letter compression format, inventory the text blocks, references and maximum simultaneous decode buffer. Prefer a simple token dictionary or line-oriented RLE that has a small 6510 decoder and works identically in the D64 and CRT loaders.
