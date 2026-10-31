// Headless checks for the Psi-5 page (node js/test/run.js [outdir]).
//
// 1. cartridge and chips: CRT parsing, EasyFlash banking, the reset through the cartridge,
//    CIA timers and interrupts, the time-of-day alarm, the undocumented opcodes
// 2. the game, once at page speed and once with m.dma = true (the cycles the VIC takes, as
//    on a real machine): trainer prompt -> title (music on the SID) -> course list -> crew
//    selection -> bridge -> Engineering, with the mouse pointer and a click
// 3. the debugger: save / load state, write watch
// Writes PNG snapshots of every screen to outdir.
'use strict';
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
global.CPU6502 = require(path.join(ROOT, 'src/cpu6502.js'));
global.SentinelFont = require(path.join(ROOT, 'src/font.js'));
global.SentinelVideo = require(path.join(ROOT, 'src/video.js'));
global.SentinelDisasm = require(path.join(ROOT, 'src/disasm.js'));
const Debugger = require(path.join(ROOT, 'src/debugger.js'));
const Profiles = require(path.join(ROOT, 'src/profiles.js'));
const C128 = require(path.join(ROOT, 'src/machine.js'));
const Video = require(path.join(ROOT, 'src/video.js'));
const Hooks = require(path.join(ROOT, 'src/hooks.js'));
const ctx = {};
vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'programs.js'), 'utf8'), ctx);
const PROG = ctx.PSI5_PROGRAMS.psi5;
const SYM = PROG.symbols;
const BRIDGE_CRT = new Uint8Array(fs.readFileSync(path.join(ROOT, 'ref', 'psi5_ef_bridge_tested.crt')));
const FULL_CRT = new Uint8Array(fs.readFileSync(path.join(ROOT, 'ref', 'psi5_ef_tested.crt')));
const OUT = process.argv[2] || path.join(__dirname, 'out');
fs.mkdirSync(OUT, { recursive: true });

let failures = 0;
function check(cond, msg) { console.log((cond ? 'ok   ' : 'FAIL ') + msg); if (!cond) failures++; }
const hx = v => v.toString(16).toUpperCase();

function png(file, w, h, px) {
  const raw = Buffer.alloc((w * 4 + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (w * 4 + 1)] = 0;
    for (let x = 0; x < w; x++) {
      const c = px[y * w + x], o = y * (w * 4 + 1) + 1 + x * 4;
      raw[o] = c & 255; raw[o + 1] = (c >> 8) & 255; raw[o + 2] = (c >> 16) & 255; raw[o + 3] = 255;
    }
  }
  const crcT = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; crcT[n] = c >>> 0; }
  const crc = b => { let c = 0xFFFFFFFF; for (const x of b) c = crcT[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  const chunk = (t, d) => { const l = Buffer.alloc(4); l.writeUInt32BE(d.length); const td = Buffer.concat([Buffer.from(t), d]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([l, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 6;
  fs.writeFileSync(file, Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]));
}

// Writes the screen to outdir/<name>.png; returns {lit, colors}: the pixels that differ from
// the most common colour, and the number of colours used (a blank screen has one).
function snap(m, name) {
  const px = new Uint32Array(Video.VIC_W * Video.VIC_H);
  px.set(m.video.px);
  png(path.join(OUT, name + '.png'), Video.VIC_W, Video.VIC_H, px);
  const count = new Map();
  for (const c of px) count.set(c, (count.get(c) || 0) + 1);
  let top = 0; for (const n of count.values()) if (n > top) top = n;
  return { lit: px.length - top, colors: count.size };
}

// Commodore key matrix: [column, row], as in app.js
const KEYS = { Enter: [0, 1], KeyE: [1, 6], KeyS: [1, 5], KeyW: [1, 1], KeyN: [4, 7], Digit1: [7, 0] };

function boot(dma, which = 'bridge') {
  const m = new C128('c64');
  m.dma = !!dma;
  m.standInKernal = true;
  m.loadCrt(which === 'full' ? FULL_CRT : BRIDGE_CRT);
  m.startCart();
  return m;
}
function frames(m, n) { for (let i = 0; i < n; i++) if (!m.runFrame()) return false; return true; }
function tap(m, code, hold = 4, gap = 60) {
  const k = KEYS[code];
  m.setKey(k[0], k[1], true); frames(m, hold);
  m.setKey(k[0], k[1], false); frames(m, gap);
}
// Run until the program counter is in [lo, hi] at the end of a frame.
function until(m, lo, hi, max) {
  for (let i = 0; i < max; i++) { if (m.cpu.pc >= lo && m.cpu.pc <= hi) return true; if (!m.runFrame()) return false; }
  return m.cpu.pc >= lo && m.cpu.pc <= hi;
}
// Run until a breakpoint address is executed.
function untilAt(m, addr, max) {
  m.setBreak(addr, true);
  let hit = false;
  for (let i = 0; i < max && !hit; i++) {
    const r = m.run();
    if (r === 'break' && m.breakInfo && m.breakInfo.type === 'break' && m.breakInfo.pc === addr) hit = true;
    else if (r === 'stopped') break;
  }
  m.setBreak(addr, false);
  return hit;
}
// Move the mouse until the pointer cell is at (row, col). The 1351 reports up as positive.
function pointerTo(m, row, col) {
  for (let i = 0; i < 80 && m.ram[SYM.POINTERROW] !== row; i++) { m.moveMouse(0, m.ram[SYM.POINTERROW] > row ? 1 : -1); frames(m, 2); }
  for (let i = 0; i < 80 && Math.abs(m.ram[SYM.POINTERCOL] - col) > 1; i++) { m.moveMouse(m.ram[SYM.POINTERCOL] > col ? -4 : 4, 0); frames(m, 1); }
  frames(m, 3);
}
function rowChar(m, row, col) { return m.ram[SYM.TEXTSCREEN + row * 40 + col]; }
function findRowChar(m, row, code) {
  for (let col = 0; col < 40; col++) if (rowChar(m, row, col) === code) return col;
  return -1;
}
function clickPointer(m, row, col, right = false) {
  pointerTo(m, row, col);
  if (right) m.mouse.right = true; else m.mouse.left = true;
  frames(m, 8);
  if (right) m.mouse.right = false; else m.mouse.left = false;
  frames(m, 120);
}
function guardedFrames(m, n, label) {
  const bad = [SYM.RESTART, SYM.TRAINERPROMPT, SYM.TITLEWAIT, 0x3CA7];
  bad.forEach(a => m.setBreak(a, true));
  let hit = null, alive = true;
  for (let i = 0; i < n && alive; i++) {
    while (true) {
      const r = m.run();
      if (r === 'frame') break;
      if (r === 'break') { hit = m.breakInfo.pc; alive = false; break; }
      alive = false; break;
    }
    if (m.stopped || m.cpu.jam) alive = false;
  }
  bad.forEach(a => m.setBreak(a, false));
  check(alive && !hit, label + ' stays alive for ' + n + ' frames' + (hit === null ? '' : ' (reached $' + hx(hit) + ')'));
  return alive;
}
function sidWrites(m) {
  const w = { n: 0, regs: new Set(), gates: 0 };
  const orig = m.sidWrite.bind(m);
  m.sidWrite = function (r, v) { w.n++; w.regs.add(r); if ((r === 4 || r === 11 || r === 18) && (v & 1)) w.gates++; return orig(r, v); };
  return w;
}

// ---- 1. cartridge and chips ---------------------------------------------------------
{
  const m = new C128('c64');
   const cart = m.loadCrt(BRIDGE_CRT);
  check(cart.name === 'PSI-5 TRADING COMPANY', 'CRT: name "' + cart.name + '"');
  const banks = Object.keys(cart.banks).map(Number);
  check(banks.length === 23 && Math.max(...banks) === 22, 'CRT: 23 banks (0-22), 46 CHIP packets of 8K');
  check(cart.banks[0].lo.length === 0x2000 && cart.banks[0].hi.length === 0x2000 && cart.banks[22].hi.length === 0x2000, 'CRT: ROML and ROMH chip of 8K per bank');
  let threw = false; try { m.loadCrt(new Uint8Array(64)); } catch (e) { threw = true; }
  check(threw, 'CRT: a file that is not a cartridge is refused');

  m.startCart();
  check(m.cartMode === 3 && m.cpu.pc === 0xFF00, 'reset: Ultimax at power on, PC from the ROMH vector = $' + hx(m.cpu.pc));
  const romL0 = cart.banks[0].lo[0x1E00], romH0 = cart.banks[0].hi[0x0000];
  check(m.read(0x9E00) === romL0, 'Ultimax: ROML at $8000-$9FFF (bank 0)');
  m.write(0xDE02, 0x07);                       // I/O is visible in Ultimax
  check(m.cartMode === 2, '$DE02 = 7: 16K mode');
  m.port1 = 0x37; m.port0 = 0x2F;
  check(m.read(0xA000) === romH0 && m.read(0x9E00) === romL0, '16K: ROML $8000 and ROMH $A000 visible');
  m.write(0xDE00, 5);
  check(m.read(0x8000) === cart.banks[5].lo[0] && m.read(0xA000) === cart.banks[5].hi[0], '$DE00 = 5: bank 5 in both windows');
  m.write(0xDE00, 40);
  check(m.read(0x8000) === 0xFF, 'a bank that is not in the file reads $FF');
  m.write(0xDE00, 0);
  m.write(0xDE02, 0x06);
  check(m.cartMode === 1 && m.read(0x8000) === cart.banks[0].lo[0] && m.read(0xA000) === m.ram[0xA000], '$DE02 = 6: 8K mode (ROML only)');
  m.write(0xDE02, 0x04);
  check(m.cartMode === 0 && m.read(0x8000) === m.ram[0x8000], '$DE02 = 4: cartridge off, RAM at $8000');
  m.write(0xDF10, 0x5A);
  check(m.read(0xDF10) === 0x5A && m.efRam[0x10] === 0x5A, '256 bytes of RAM at $DF00 (also with the cartridge off)');
  m.write(0xDE02, 0x07); m.port1 = 0x30;       // $01: all RAM
  check(m.read(0x8000) === m.ram[0x8000], '16K mode with LORAM / HIRAM low: RAM shows');
  m.port1 = 0x37;
  m.write(0xDE02, 0x05);
  check(m.cartMode === 3 && m.read(0xFFFC) === 0x00 && m.read(0xFFFD) === 0xFF, 'Ultimax again: ROMH at $E000-$FFFF whatever $01 says');
}

// stand-in KERNAL: only the interrupt layer, SETLFS / SETNAM
{
  const m = boot(false);
  m.setCartCtl(4); m.port1 = 0x37; m.port0 = 0x2F;
  check(m.read(0xFFFE) === 0x48 && m.read(0xFFFF) === 0xFF, 'KERNAL stand-in: IRQ vector $FF48 while the KERNAL is in');
  m.port1 = 0x35;
  check(m.read(0xFFFE) === m.ram[0xFFFE], '$01 = $35: RAM under the KERNAL');
}

// CIA timers, interrupts and the time-of-day alarm
{
  const m = new C128('c64');
  m.port1 = 0x35;
  const w = (a, v) => m.write(a, v);
  w(0xDC04, 0x10); w(0xDC05, 0x00);
  w(0xDC0E, 0x11);                                   // force load, start
  m.cpu.cycles += 10;
  const lo = m.read(0xDC04);
  check(lo >= 4 && lo <= 7, 'CIA1 timer A counts down with the clock (' + lo + ' left after 10 of 16 cycles)');
  m.cpu.cycles += 20;
  check((m.read(0xDC0D) & 1) === 1, 'timer A underflow sets ICR bit 0');
  check(m.read(0xDC0D) === 0, 'reading the ICR clears it');
  w(0xDC04, 5); w(0xDC05, 0); w(0xDC0E, 0x19);      // force load + start + one-shot
  m.cpu.cycles += 100;
  m.read(0xDC0D);
  check((m.read(0xDC0E) & 1) === 0, 'a one-shot timer stops after its underflow');
  w(0xDC0E, 0); w(0xDC04, 4); w(0xDC05, 0); w(0xDC06, 2); w(0xDC07, 0);
  w(0xDC0F, 0x51); w(0xDC0E, 0x11);                  // B counts A's underflows
  m.cpu.cycles += 5 * 3 + 2;
  check((m.read(0xDC0D) & 2) === 2, 'timer B counts timer A underflows');

  // the interrupt reaches the processor: handler at $0300 counts, loop at $0400
  const k = new C128('c64');
  k.port1 = 0x35;
  k.ram[0xFFFE] = 0x00; k.ram[0xFFFF] = 0x03;
  k.ram.set([0xEE, 0x10, 0x03, 0xAD, 0x0D, 0xDC, 0x40], 0x0300);
  k.ram.set([0x58, 0x4C, 0x01, 0x04], 0x0400);          // CLI, JMP *
  k.write(0xDC04, 0x00); k.write(0xDC05, 0x10);         // 4096 cycles
  k.write(0xDC0D, 0x81); k.write(0xDC0E, 0x11);
  k.cpu.pc = 0x0400; k.cpu.p = 0x24; k.cpu.sp = 0xFF; k.stopped = null;
  for (let i = 0; i < 4; i++) k.runFrame();
  check(k.ram[0x0310] >= 17 && k.ram[0x0310] <= 20, 'CIA1 timer A interrupt vectors through $FFFE (' + k.ram[0x0310] + ' in 4 frames at 4096 cycles)');

  // the alarm the game tests: alarm = 10:20:40.5, then the clock set to the same time
  const t = new C128('c64'); t.port1 = 0x35;
  const tw = (a, v) => t.write(a, v);
  tw(0xDD0F, 0x80);
  tw(0xDD0B, 0x10); tw(0xDD0A, 0x20); tw(0xDD09, 0x40); tw(0xDD08, 0x05);
  tw(0xDD0F, 0x00);
  t.read(0xDD0D);
  tw(0xDD0B, 0x10); tw(0xDD0A, 0x20); tw(0xDD09, 0x40);
  check((t.read(0xDD0D) & 4) === 0, 'TOD: no alarm before the clock is complete');
  tw(0xDD08, 0x05);
  check((t.read(0xDD0D) & 4) === 4, 'TOD: ICR bit 2 when the clock is set to the alarm time');
  tw(0xDD0B, 0x01); tw(0xDD0A, 0x59); tw(0xDD09, 0x59); tw(0xDD08, 0x09);
  t.cpu.cycles += 98525;
  const hrs = t.read(0xDD0B), mins = t.read(0xDD0A), secs = t.read(0xDD09), ten = t.read(0xDD08);
  check(hrs === 0x02 && mins === 0 && secs === 0 && ten === 0, 'TOD: ticks every 98525 cycles with BCD carry (' + [hrs, mins, secs, ten].map(hx).join(':') + ')');
}

// undocumented opcodes (the game jumps into the middle of an instruction: ISC $CC,X)
{
  const m = new C128('c64');
  const run = (bytes, setup) => {
    m.ram.fill(0); m.ram.set(bytes, 0x200);
    m.cpu.pc = 0x200; m.cpu.a = m.cpu.x = m.cpu.y = 0; m.cpu.p = 0x20; m.cpu.jam = null;
    if (setup) setup();
    m.cpu.step();
  };
  run([0xF7, 0x10], () => { m.ram[0x10] = 0x41; m.cpu.a = 0x50; m.cpu.p |= 1; });
  check(m.ram[0x10] === 0x42 && m.cpu.a === 0x0E, 'ISC: memory + 1, then A - memory');
  run([0xA7, 0x20], () => { m.ram[0x20] = 0x80; });
  check(m.cpu.a === 0x80 && m.cpu.x === 0x80, 'LAX zp: A and X');
  run([0x87, 0x30], () => { m.cpu.a = 0xF0; m.cpu.x = 0x3C; });
  check(m.ram[0x30] === 0x30, 'SAX zp: A and X stored');
  run([0xC7, 0x40], () => { m.ram[0x40] = 0x11; m.cpu.a = 0x10; });
  check(m.ram[0x40] === 0x10 && (m.cpu.p & 2), 'DCP zp: decrement, compare');
  run([0x07, 0x50], () => { m.ram[0x50] = 0x81; m.cpu.a = 0x04; });
  check(m.ram[0x50] === 0x02 && m.cpu.a === 0x06 && (m.cpu.p & 1), 'SLO zp: shift left, OR into A');
  run([0x1A]);
  check(!m.cpu.jam && m.cpu.pc === 0x201, 'NOP implied');
  run([0x02]);
  check(!!m.cpu.jam, 'JAM opcodes still jam');
}

// ---- 2. the game ----------------------------------------------------------------------
function playthrough(dma) {
  const tag = dma ? 'dma' : 'plain';
  const label = (dma ? 'm.dma' : 'page speed') + ': ';
  const m = boot(dma, 'full');
  const sid = sidWrites(m);

  check(until(m, 0x0CA0, 0x0CC0, 600) && !m.stopped, label + 'boots through the cartridge to the trainer prompt (PC $' + hx(m.cpu.pc) + ', frame ' + m.frame + ')');
  let s = snap(m, tag + '-1-trainer');
  check(s.lit > 1000 && m.cartMode === 0, label + 'trainer screen drawn (' + s.lit + ' lit pixels), cartridge off');

  tap(m, 'KeyN', 4, 20);
  check(until(m, 0x04B1, 0x04B8, 800), label + 'N answers the trainers: the title waits (PC $' + hx(m.cpu.pc) + ')');
  frames(m, 120);
  s = snap(m, tag + '-2-title');
  check(s.lit > 8000 && s.colors >= 6, label + 'title screen drawn (' + s.lit + ' lit pixels, ' + s.colors + ' colours)');
  check(sid.n > 20 && sid.gates >= 1 && m.sid[0x18] === 0x0F, label + 'music reaches the SID: ' + sid.n + ' writes to registers ' + [...sid.regs].sort((a, b) => a - b).join(',') + ', volume $' + hx(m.sid[0x18]));

  m.joy2 = 16; frames(m, 5); m.joy2 = 0;
  check(until(m, 0x5F90, 0x5FA0, 1500), label + 'fire at the title: the course list waits for a key (PC $' + hx(m.cpu.pc) + ', frame ' + m.frame + ')');
  frames(m, 20);
  s = snap(m, tag + '-3-courses');
  check(s.lit > 8000 && s.colors >= 4, label + 'course list drawn (' + s.lit + ' lit pixels)');

  tap(m, 'Digit1', 4, 150);
  s = snap(m, tag + '-4-crew');
  check(s.lit > 8000, label + 'course 1: crew selection (' + s.lit + ' lit pixels)');
  for (let i = 0; i < 5; i++) { tap(m, 'Enter', 4, 100); tap(m, 'KeyW', 4, 100); }
  s = snap(m, tag + '-5-crew-all');
  check(s.lit > 8000 && s.colors >= 6, label + 'five candidates chosen (' + s.lit + ' lit pixels, ' + s.colors + ' colours)');

  tap(m, 'Enter', 4, 20);                 // accept the final crew
  tap(m, 'Enter', 4, 20);                 // and begin
  const reached = untilAt(m, SYM.GETKEY, 4000);
  check(reached && !m.stopped, label + 'the bridge menu loop runs (getkey $3EE9 reached, frame ' + m.frame + ')');
  frames(m, 200);
  s = snap(m, tag + '-6-bridge');
  check(s.lit > 8000 && s.colors >= 8, label + 'bridge drawn (' + s.lit + ' lit pixels, ' + s.colors + ' colours)');
  const irq = m.ram[SYM.IRQVECTOR] | (m.ram[SYM.IRQVECTOR + 1] << 8);
  check(irq >= 0x8E00 && irq < 0x9000, label + 'bridge raster IRQ installed ($' + hx(irq) + ')');
  check(m.port1 === 0x35, label + 'KERNAL off during play ($01 = $' + hx(m.port1) + ')');
  check(sid.n > 60, label + 'the SID got ' + sid.n + ' writes by the bridge');

  // mouse: detected, the pointer moves, a click on the menu row types the word's key
  check(m.ram[SYM.MOUSEON] !== 0, label + 'the patch finds the 1351 in port 2 (MOUSEON=$' + hx(m.ram[SYM.MOUSEON]) + ')');
  const x0 = m.ram[SYM.MOUSEX], c0 = m.ram[SYM.POINTERCOL], r0 = m.ram[SYM.POINTERROW];
  for (let i = 0; i < 12; i++) { m.moveMouse(-5, 0); frames(m, 1); }
  frames(m, 3);
  const x1 = m.ram[SYM.MOUSEX], c1 = m.ram[SYM.POINTERCOL];
  check(x1 !== x0 && c1 !== c0, label + 'mouse left: pointer column ' + c0 + ' -> ' + c1);
  for (let i = 0; i < 40; i++) { m.moveMouse(0, -3); frames(m, 1); }
  frames(m, 3);
  const r1 = m.ram[SYM.POINTERROW];
  check(r1 > r0, label + 'mouse down: pointer row ' + r0 + ' -> ' + r1);
  // a click outside menus is the fire button: "Press BUTTON to begin"
  const before = snap(m, tag + '-7-begin');
  m.mouse.left = true; frames(m, 8); m.mouse.left = false;
  frames(m, 400);
  const after = snap(m, tag + '-8-departure');
  check(after.lit !== before.lit && m.ram[SYM.MOUSEMENUON] !== 0, label + 'a click began the mission: the menu row appears (' + before.lit + ' -> ' + after.lit + ' lit pixels)');
  // click the word "Eng." on the menu row: its shortcut key goes into the key queue
  pointerTo(m, 14, 24);
  check(m.ram[SYM.POINTERROW] === 14 && m.ram[SYM.POINTERCOL] >= 23 && m.ram[SYM.POINTERCOL] <= 26, label + 'pointer on the word Eng. (row ' + m.ram[SYM.POINTERROW] + ', column ' + m.ram[SYM.POINTERCOL] + ')');
  snap(m, tag + '-9-pointer-on-eng');
  m.mouse.left = true; frames(m, 8); m.mouse.left = false; frames(m, 100);
  snap(m, tag + '-10-engineering');
   check(m.ram[SYM.CMDDEPT] === 0x45 && m.ram[SYM.DEPTLETTER] === 0x45, label + 'the click chose Engineering (command record department $' + hx(m.ram[SYM.CMDDEPT]) + ')');
   const engineeringMenuState = m.saveState();
  // then the word "Status" at the left of the engineering menu
  pointerTo(m, 14, 2);
  m.mouse.left = true; frames(m, 8); m.mouse.left = false; frames(m, 150);
  s = snap(m, tag + '-11-status');
  const dev = [...m.ram.slice(SYM.DEVSTATE, SYM.DEVSTATE + 12)];
  check(m.ram[SYM.CMDCMD] === 0x53 && dev.some(v => v & 0x80), label + 'the click on Status shows the device list (command $' + hx(m.ram[SYM.CMDCMD]) + ', devices ' + dev.map(hx).join(' ') + ')');
  // click a device row: enable / cancel through the game's own routine
  pointerTo(m, 18, 2);
  const dev0 = dev.join(',');
  m.mouse.left = true; frames(m, 8); m.mouse.left = false; frames(m, 200);
  const dev1 = [...m.ram.slice(SYM.DEVSTATE, SYM.DEVSTATE + 12)].join(',');
   check(dev1 !== dev0, label + 'a click on a device row cancels it through the game routine (' + dev0 + ' -> ' + dev1 + ')');
   snap(m, tag + '-12-device-click');
   // The second device column must address J, not the first-column B.
    pointerTo(m, 18, 23);
   const PEND = 0x07E0;   // requests: a device may go to RqC first instead of changing state
   const b0 = m.ram[SYM.DEVSTATE + 1], j0 = m.ram[SYM.DEVSTATE + 9] + m.ram[PEND + 9] * 256, bp0 = m.ram[PEND + 1];
   m.mouse.left = true; frames(m, 8); m.mouse.left = false; frames(m, 150);
    check(m.ram[SYM.DEVSTATE + 1] === b0 && m.ram[PEND + 1] === bp0 && m.ram[SYM.DEVSTATE + 9] + m.ram[PEND + 9] * 256 !== j0, label + 'right-column Engineering Status click toggles J, not B (pointer ' + m.ram[SYM.POINTERCOL] + ',' + m.ram[SYM.POINTERROW] + '; B ' + hx(b0) + ' -> ' + hx(m.ram[SYM.DEVSTATE + 1]) + ', J ' + hx(j0) + ' -> ' + hx(m.ram[SYM.DEVSTATE + 9]) + ')');
   const backCol = findRowChar(m, 14, 0x7F);
   check(backCol >= 0, label + 'Engineering menu has the back arrow code $7F on row 14');
   if (backCol >= 0) clickPointer(m, 14, backCol);
    check(rowChar(m, 15, 1) === 0x45, label + 'clicking the back arrow goes back to the Engineering menu');
   const count0 = m.ram[SYM.BRIDGEKEYCOUNT];
   clickPointer(m, 14, 39);
   check(m.ram[SYM.BRIDGEKEYCOUNT] === count0, label + 'clicking a blank menu cell does nothing');
   m.mouse.right = true; frames(m, 8); m.mouse.right = false; frames(m, 120);
    check(rowChar(m, 15, 1) === 0x45, label + 'right mouse button goes back through $DC00 bit 0');
    m.loadState(engineeringMenuState);
    const displayCol = findRowChar(m, 14, 0x44);
   if (displayCol >= 0) clickPointer(m, 14, displayCol);
    const dragRow = 18, dropRow = 20;
   pointerTo(m, dragRow, 2); m.mouse.left = true; frames(m, 20);
    const dragColor = m.colorRam[dragRow * 40 + 3];
    pointerTo(m, dropRow, 2); const dropColor = m.colorRam[dropRow * 40 + 3];
    check(dragColor === 12 && dropColor === 7, label + 'held drag greys the source row and yellows the row under the pointer (title ' + String.fromCharCode(...m.ram.slice(SYM.TEXTSCREEN + 15 * 40, SYM.TEXTSCREEN + 15 * 40 + 20)) + '; pointer ' + m.ram[SYM.POINTERCOL] + ',' + m.ram[SYM.POINTERROW] + '; colours ' + dragColor + '/' + dropColor + ')');
   m.mouse.left = false; frames(m, 80);
    check(m.ram[SYM.CMDCMD] === 0x44 || m.ram[SYM.CMDCMD] === 0x52 || m.ram[SYM.CMDCMD] === 0x57, label + 'releasing a drag ranks and flashes the selected item (command $' + hx(m.ram[SYM.CMDCMD]) + ')');
   snap(m, tag + '-13-drag');
   return { m, sid, tag, label };
}

function bridgeSmoke(dma) {
  const label = (dma ? 'bridge m.dma' : 'bridge page speed') + ': ';
  const m = boot(dma, 'bridge');
  const writes = [];
  const ciaWrite = m.ciaWrite;
  m.ciaWrite = function (cia, r, v) {
    if (cia === m.cia2 && (r === 0x0F || (r >= 8 && r <= 11))) writes.push([r, v]);
    return ciaWrite.call(m, cia, r, v);
  };
  const reached = untilAt(m, SYM.GETKEY, 1200);
  check(reached && !m.stopped, label + 'boots directly to getkey $' + hx(SYM.GETKEY) + ' (frame ' + m.frame + ')');
  check(writes.some(x => x[0] === 0x0F && (x[1] & 0x80)) && writes.some(x => x[0] === 8), label + 'boot programs the CIA2 TOD alarm through $DD0F and $DD0B-$DD08');
  frames(m, 200);
  const s = snap(m, (dma ? 'bridge-dma' : 'bridge-plain') + '-bridge');
  check(s.lit > 20000 && s.colors >= 8, label + 'bridge drawn (' + s.lit + ' lit pixels, ' + s.colors + ' colours)');
  check(m.ram[SYM.SPRITEPTRS + 7] === 0x82, label + 'pointer sprite uses block $82 at the text split');
  guardedFrames(m, 3000, label + 'copy-protection path');
  return m;
}

const bridgeGames = [false, true].map(bridgeSmoke);
const games = [false, true].map(playthrough);

function joystickRegression(m, label) {
  for (const present of [true, false]) {
    m.mouse.present = present;
    for (const bit of [8, 4]) {
      for (let i = 0; i < 14; i++) {
        m.joy2 = bit; guardedFrames(m, 12, label + ' mouse ' + present + ' held ' + bit + ' #' + i);
        m.joy2 = 0; frames(m, 8);
      }
    }
  }
  m.joy2 = 0;
  check(!m.stopped && !m.cpu.jam, label + ' left/right regression never jams or stops the machine');
}
joystickRegression(bridgeGames[0], 'bridge cartridge');
joystickRegression(games[0].m, 'full-game cartridge');

// ---- 3. debugger -------------------------------------------------------------------------
{
  const { m } = games[1];
  const hooks = new Hooks(m, SYM);
  const dbg = new Debugger(m, hooks, 'psi5', Profiles.psi5);
  check(dbg.watches.length === Profiles.psi5.watches.length && dbg.parse('SETDEVICE') === 0x95AC, 'debugger: profile watches and labels resolve');
  m.setWatch(SYM.MOUSEBTN, true);
  m.mouse.left = true;
  let hit = false;
  for (let i = 0; i < 20 && !hit; i++) { if (m.run() === 'break' && m.breakInfo.type === 'watch') hit = true; }
  m.mouse.left = false; m.setWatch(SYM.MOUSEBTN, false);
  check(hit && m.breakInfo.addr === SYM.MOUSEBTN, 'debugger: a write watch on MOUSEBTN stops when the click is read (writer $' + hx(m.breakInfo.pc) + ')');
  while (m.frameOpen) m.run();
  const st = m.saveState();
  frames(m, 50);
  const a = Buffer.from(m.ram).toString('base64') + m.cpu.pc + ',' + m.cpu.cycles;
  m.loadState(m.stateFromText(m.stateToText(st)));
  frames(m, 50);
  const b = Buffer.from(m.ram).toString('base64') + m.cpu.pc + ',' + m.cpu.cycles;
  check(a === b, 'debugger: loading a saved state (through text) and running 50 frames gives the same memory, PC and cycles');
}

// QUIT / restart: known not to work (it loads from disk, the KERNAL LOAD is not there)
{
  const m = boot(false);
  frames(m, 200); tap(m, 'KeyN', 4, 20); until(m, 0x04B1, 0x04B8, 800);
  m.joy2 = 16; frames(m, 5); m.joy2 = 0; until(m, 0x5F90, 0x5FA0, 1500);
  console.log('info: QUIT is not tested (needs the disk drive); the restart code is at $' + hx(SYM.RESTART));
}

console.log(failures ? failures + ' check(s) FAILED' : 'all checks passed');
process.exit(failures ? 1 : 0);
