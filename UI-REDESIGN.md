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

`?NN` is the global Acknowledge/message entry and total pending-message badge. The digits use red reverse video; clicking any of the three cells opens the unfiltered Acknowledge screen. With no messages, keep the three-cell field stable but render only `?` and two spaces.

The five department fields plus one active expansion consume 32 cells. `?NN ` consumes four and Settings one, so the complete row is 37 cells and still fits without shortening department names further. Per-department counts do not belong in these tabs: adding them would either break the fixed widths or make the active Engineering/Navigation names inconsistent.

`*` is a temporary PETSCII placeholder for Settings until a suitable gear character is chosen. Settings replaces Quit; restart/quit can live inside that screen.

Keep the back arrow as the last item of every department command row. It is iconic even when direct tabs make it less necessary: left click returns to the department bar/default context, while right click remains Back/Cancel during a multi-step command. Both paths should use the game's existing back behavior rather than creating a second state-reset path.

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
- Judge both on the real machine and in the JS page: legibility of black/white/red text, the white hover, yellow drag preview and blue flash, and whether the active-tab look still works.


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
