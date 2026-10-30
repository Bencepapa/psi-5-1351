// High-level C64 / C128 machine for the Sentinel code.
//
// The 6502/8502 code runs unchanged on a 6502 core. The chips around it are
// register files: the VIC is drawn line by line from logged register writes
// (video.js), the SID is replayed in an AudioWorklet (audio.js), the VDC keeps
// its own RAM. Two models:
//
//   c128  native C128 mode as the tests use it: MMU configuration register at
//         $FF00/$D500, VDC at $D600, $D030 2 MHz bit
//   c64   C64 memory map from the processor port $00/$01, used by the full
//         patched game (Sentinel-1351_v9.prg) and by Psi-5 (EasyFlash cartridge)
//
// No ROMs: the programs bank them out or never call them. ROM areas read as RAM,
// the character ROM is an original font (font.js).
//
// Debugging lives here too, because it has to sit in the instruction loop:
// PC breakpoints, write watchpoints, frozen addresses, instruction / frame
// stepping that can stop in the middle of a frame, and save / load state.
'use strict';

var C128 = (function () {
  var CPU = (typeof CPU6502 !== 'undefined') ? CPU6502 : require('./cpu6502.js');
  var Video = (typeof SentinelVideo !== 'undefined') ? SentinelVideo : require('./video.js');
  var Font = (typeof SentinelFont !== 'undefined') ? SentinelFont : require('./font.js');

  var PAL_LINES = 312, PAL_LINE_CYCLES = 63;
  var FRAME_CYCLES = PAL_LINES * PAL_LINE_CYCLES;   // 19656 at 1 MHz
  var RETURN_TRAP = 0xFFF0;                         // RTS from START lands here (C128 tests)

  function Machine(model) {
    var m = this;
    this.model = model === 'c64' ? 'c64' : 'c128';
    this.ram = new Uint8Array(0x10000);
    this.colorRam = new Uint8Array(0x400);
    this.vic = new Uint8Array(0x40);
    this.sid = new Uint8Array(0x20);
    this.vdcRam = new Uint8Array(0x10000);
    this.vdcReg = new Uint8Array(0x40);
    this.mmu = new Uint8Array(0x0C);
    this.cpu = new CPU({ read: function (a) { return m.read(a); },
                         write: function (a, v) { m.write(a, v); } });
    this.hooks = null;            // set by Hooks
    this.writeLog = null;         // addresses written while a port is verified
    this.sidLog = [];             // [cycleInFrame, reg, value] for audio
    this.vicLog = [];             // [line, cycleInLine, reg, value]: VIC writes this frame
    this.ptrLog = [];             // [line, cycleInLine, addr, value]: sprite pointer writes
    this.vicStart = new Uint8Array(0x40);   // VIC registers when the frame began
    this.ptrStart = new Uint8Array(512);    // sprite pointers of every 1K screen then
    // debugging
    this.bpAt = new Uint8Array(0x10000);    // PC breakpoints
    this.wpAt = new Uint8Array(0x10000);    // write watchpoints
    this.frozenAt = new Uint8Array(0x10000);
    this.frozen = {};                        // addr -> value
    this.watchHit = null;
    this.breakInfo = null;                   // why the last run() stopped early
    this.skipBreakAt = -1;
    this.cart = null;                        // EasyFlash image (loadCrt): {banks: {n: {lo, hi}}}
    this.cartMode = 0;                       // 0 off, 1 8K, 2 16K, 3 Ultimax
    this.efRam = new Uint8Array(256);        // EasyFlash RAM at $DF00
    this.efBank = 0; this.efCtl = 0;
    this.stolenTotal = 0;                    // cycles the VIC took (m.dma); the CIAs count them
    this.nmiFlag = false;
    this.standInKernal = false;
    this.video = new Video.Vic(this);
    this.reset();
  }

  // Stand-in for the KERNAL ROM (there is none): just the interrupt layer a program needs
  // while $01 has the KERNAL switched in: the IRQ entry $FF48 (push A, X, Y, then JMP
  // ($0314), or ($0316) for BRK), $EA31 / $EA81 (the normal exit), the NMI entry $FE43
  // and the vectors. Only visible when m.standInKernal is set (Psi-5).
  var KERNAL = (function () {
    var k = new Uint8Array(0x2000).fill(0xEA);
    k.fill(0x02, 0xFF81 - 0xE000, 0xFFF4 - 0xE000);          // jump table: a call not provided here jams
    function put(a, bytes) { k.set(bytes, a - 0xE000); }
    put(0xFF48, [0x48, 0x8A, 0x48, 0x98, 0x48, 0xBA, 0xBD, 0x04, 0x01, 0x29, 0x10, 0xF0, 0x03, 0x6C, 0x16, 0x03, 0x6C, 0x14, 0x03]);
    // jump table entries (JMP) to the routines, which live in a spare corner of the ROM
    function entry(a, at, code) { put(at, code); put(a, [0x4C, at & 0xFF, at >> 8]); }
    entry(0xFFBA, 0xFB00, [0x85, 0xB8, 0x86, 0xBA, 0x84, 0xB9, 0x60]);   // SETLFS: A, X, Y -> $B8, $BA, $B9
    entry(0xFFBD, 0xFB10, [0x85, 0xB7, 0x86, 0xBB, 0x84, 0xBC, 0x60]);   // SETNAM: length, name pointer -> $B7, $BB / $BC
    entry(0xFFB7, 0xFB20, [0xA5, 0x90, 0x60]);                            // READST
    entry(0xFF90, 0xFB30, [0x85, 0x9D, 0x60]);                            // SETMSG
    put(0xEA31, [0x4C, 0x81, 0xEA]);
    put(0xEA81, [0x68, 0xA8, 0x68, 0xAA, 0x68, 0x40]);
    put(0xFE43, [0x78, 0x6C, 0x18, 0x03]);
    put(0xFCE2, [0x4C, 0xE2, 0xFC]);
    put(0xFFFA, [0x43, 0xFE, 0xE2, 0xFC, 0x48, 0xFF]);
    return k;
  })();

  var NEVER = 1e15;
  // A CIA: ports, interrupt mask / flags and the two interval timers. The timers are
  // counted lazily from the system clock (ciaSync); 'due' is the clock of the next
  // underflow that has its interrupt enabled.
  function newCia(o) {
    o.icrMask = 0; o.icr = 0;
    o.ta = o.tb = o.la = o.lb = 0xFFFF; o.cra = o.crb = 0;
    o.last = 0; o.due = NEVER;
    o.tod = [0, 0, 0, 0x01];             // time of day: tenths, seconds, minutes, hours (BCD, $80 = PM)
    o.alarm = [0, 0, 0, 0];
    o.todRun = true; o.todLast = 0; o.todLatch = null;
    return o;
  }
  function cloneCia(c) { return Object.assign({}, c, { tod: c.tod.slice(), alarm: c.alarm.slice(), todLatch: c.todLatch && c.todLatch.slice() }); }
  // Count n clocks on one timer ('a' or 'b'); returns its underflows (flag in ICR).
  function adv(c, k, n) {
    var t = c['t' + k], l = c['l' + k], u = 0;
    if (n <= t) t -= n;
    else { n -= t + 1; u = 1 + Math.floor(n / (l + 1)); t = l - n % (l + 1); }
    c['t' + k] = t;
    if (u) {
      c.icr |= k === 'a' ? 1 : 2;
      if (c['cr' + k] & 8) { c['cr' + k] &= ~1; c['t' + k] = l; u = 1; }     // one-shot
    }
    return u;
  }

  var TOD_TENTH = 98525;               // clocks per tenth of a second (PAL)
  function bcdInc(v, max) { var n = (v >> 4) * 10 + (v & 15) + 1; if (n > max) return -1; return ((n / 10 | 0) << 4) | (n % 10); }

  var P = Machine.prototype;

  P.reset = function () {
    this.ram.fill(0);
    this.colorRam.fill(14);
    this.vic.fill(0);
    this.sid.fill(0);
    this.vdcRam.fill(0);
    this.vdcReg.fill(0);
    this.mmu.fill(0);
    this.mmuCR = 0x00;            // C128 after RUN from BASIC: ROMs + I/O
    this.port0 = 0x2F;            // C64 processor port: DDR, data
    this.port1 = 0x37;
    // VIC as BASIC leaves it: text at $0400
    this.vic[0x11] = 0x1B; this.vic[0x16] = 0xC8; this.vic[0x18] = 0x14;
    this.vic[0x20] = 14; this.vic[0x21] = 6;
    this.vic[0x30] = 0xFC;
    this.vicIrq = 0;              // latched interrupt bits of $D019
    this.collSS = 0; this.collSB = 0;
    // CIA1: keyboard columns out, rows in. CIA2: VIC bank 0.
    this.cia1 = newCia({ pra: 0x7F, prb: 0xFF, ddra: 0xFF, ddrb: 0x00 });
    this.cia2 = newCia({ pra: 0x97, prb: 0xFF, ddra: 0x3F, ddrb: 0x00 });
    // VDC as the KERNAL sets it up: 80x25, screen $0000, attributes $0800,
    // character set $2000, 16 bytes per character.
    var r = this.vdcReg;
    r[0] = 126; r[1] = 80; r[2] = 102; r[4] = 39; r[6] = 25; r[9] = 7;
    r[12] = 0x00; r[13] = 0x00; r[20] = 0x08; r[21] = 0x00;
    r[22] = 0x78; r[23] = 0x08; r[25] = 0x47; r[26] = 0xF0; r[27] = 0; r[28] = 0x2F;
    this.vdcIndex = 0;
    Font.loadVdc(this.vdcRam, 0x2000);
    this.vdcRam.fill(0x20, 0, 0x800);                 // blank screen
    this.vdcRam.fill(0x8D, 0x800, 0x1000);            // KERNAL default attribute
    // input
    this.keys = new Uint8Array(8);                     // pressed rows per column
    this.joy2 = 0;                                     // bits 0-4 active (1 = pressed)
    this.mouse = { present: true, x: 0, y: 0, left: false, right: false };
    this.noise = 0x7FFFF8;
    this.noisePhase = 0;
    this.osc3Time = 0;
    this.sidLog.length = 0;
    this.stopped = null;
    this.romReads = 0;
    this.cpu.jam = null;
    this.cpu.cycles = 0;
    this.frame = 0;
    this.frameStart = 0;
    this.vCycle = 0;
    this.lastCpu = 0;
    this.frameOpen = false;
    this.lastLine = 0;
  };

  // ---- loading -------------------------------------------------------------

  P.loadPrg = function (bytes) {
    var load = bytes[0] | (bytes[1] << 8);
    this.ram.set(bytes.subarray(2), load);
    return load;
  };

  // Start a program at its entry, as SYS from BASIC would: RTS at the end
  // returns to a trap address that stops the machine.
  P.start = function (entry) {
    var c = this.cpu;
    c.sp = 0xFB; c.p = 0x24; c.a = c.x = c.y = 0;
    var ret = RETURN_TRAP - 1;
    c.push(ret >> 8); c.push(ret & 0xFF);
    c.pc = entry;
    this.frameStart = c.cycles;
    this.vCycle = 0;
    this.lastCpu = c.cycles;
    this.frame = 0;
    this.frameOpen = false;
    this.stopped = null;
  };

  // CRT file (EasyFlash, hardware type 32): CHIP packets of 8K at $8000 (ROML) or
  // $A000 / $E000 (ROMH) per bank. A bank or half missing from the file reads as $FF.
  P.loadCrt = function (b) {
    var sig = String.fromCharCode.apply(null, b.subarray(0, 16));
    if (sig.indexOf('C64 CARTRIDGE') !== 0) throw new Error('not a CRT file');
    var hdr = ((b[0x10] << 24) | (b[0x11] << 16) | (b[0x12] << 8) | b[0x13]) >>> 0;
    var type = (b[0x16] << 8) | b[0x17];
    if (type !== 32) throw new Error('CRT hardware type ' + type + ' is not EasyFlash (32)');
    var cart = { banks: {}, name: '' };
    for (var i = 0x20; i < 0x40 && b[i]; i++) cart.name += String.fromCharCode(b[i]);
    var o = hdr;
    while (o + 16 <= b.length) {
      var len = ((b[o + 4] << 24) | (b[o + 5] << 16) | (b[o + 6] << 8) | b[o + 7]) >>> 0;
      var bank = (b[o + 10] << 8) | b[o + 11], addr = (b[o + 12] << 8) | b[o + 13], size = (b[o + 14] << 8) | b[o + 15];
      if (String.fromCharCode(b[o], b[o + 1], b[o + 2], b[o + 3]) !== 'CHIP' || len < 16) break;
      var e = cart.banks[bank] || (cart.banks[bank] = { lo: null, hi: null });
      var data = b.slice(o + 16, o + 16 + size);
      if (addr === 0x8000) e.lo = data; else e.hi = data;       // ROMH: $A000 or $E000
      o += len;
    }
    this.cart = cart;
    return cart;
  };

  // Power on through the cartridge: EasyFlash starts in Ultimax mode, bank 0, and the
  // processor takes its reset vector from ROMH ($FFFC).
  P.startCart = function () {
    var c = this.cpu;
    this.efBank = 0; this.efRam.fill(0);
    this.setCartCtl(0);
    c.sp = 0xFF; c.p = 0x24; c.a = c.x = c.y = 0;
    c.pc = this.read(0xFFFC) | (this.read(0xFFFD) << 8);
    this.frameStart = c.cycles;
    this.vCycle = 0;
    this.lastCpu = c.cycles;
    this.frame = 0;
    this.frameOpen = false;
    this.stopped = null;
  };

  // $DE02: bit 2 = software sets GAME / EXROM (else the jumper: Ultimax at reset),
  // bit 1 = EXROM low, bit 0 = GAME low. 16K = both, 8K = EXROM only, Ultimax = GAME only.
  P.setCartCtl = function (v) {
    this.efCtl = v;
    if (!this.cart) { this.cartMode = 0; return; }
    if (!(v & 4)) this.cartMode = 3;
    else this.cartMode = (v & 3) === 3 ? 2 : (v & 3) === 2 ? 1 : (v & 3) === 1 ? 3 : 0;
  };

  // Cartridge ROM byte of the current bank at an address, or -1 when none is mapped there.
  P.cartRead = function (a) {
    var cm = this.cartMode, hi;
    if (cm === 3) {
      if (a >= 0x8000 && a < 0xA000) hi = 0; else if (a >= 0xE000) hi = 1; else return -1;
    } else {
      var bits = this.c64Bits();
      if (a >= 0x8000 && a < 0xA000) { if ((bits & 3) !== 3) return -1; hi = 0; }
      else if (a >= 0xA000 && a < 0xC000) { if (cm !== 2 || !(bits & 2)) return -1; hi = 1; }
      else return -1;
    }
    var e = this.cart.banks[this.efBank & 0x3F];
    var d = e && (hi ? e.hi : e.lo);
    return d ? d[a & 0x1FFF] : 0xFF;
  };

  // ---- timing --------------------------------------------------------------

  // The system clock the CIAs count: processor cycles plus the ones the VIC took.
  P.now = function () { return this.cpu.cycles + this.stolenTotal; };

  P.clockMHz = function () { return (this.model === 'c128' && (this.vic[0x30] & 1)) ? 2 : 1; };
  // Cycles since the frame started, counted at 1 MHz: in the C128's 2 MHz mode
  // ($D030 bit 0) the processor runs two cycles per raster cycle. vCycle holds
  // the raster time up to the last instruction, lastCpu the processor's count then.
  P.cycleInFrame = function () {
    return this.vCycle + (this.cpu.cycles - this.lastCpu) / this.clockMHz();
  };
  P.syncClock = function () {
    this.vCycle += (this.cpu.cycles - this.lastCpu) / this.clockMHz();
    this.lastCpu = this.cpu.cycles;
    if (this.dma) this.stealCycles();
  };
  // Optional (m.dma = true, the timing tests): the cycles the VIC takes from the
  // processor, as on a real machine: 43 on a bad line, 3 + 2 per sprite on a line
  // with sprite data. Off by default: the page and the rates measured against the
  // original run without them.
  P.stealCycles = function () {
    var line = Math.floor((this.vCycle - 12) / PAL_LINE_CYCLES);        // (from cycle 12)
    if (this.dmaFrame !== this.frame) { this.dmaFrame = this.frame; this.dmaLine = -1; }
    while (this.dmaLine < line) {
      var l = ++this.dmaLine, v = this.vic, steal = 0, n = 0;
      if ((v[0x11] & 0x10) && l >= 48 && l <= 247 && (l & 7) === (v[0x11] & 7)) steal += 43;
      for (var i = 0; i < 8; i++) {
        if (!(v[0x15] & (1 << i))) continue;
        var d = (l - v[1 + 2 * i]) & 0x1FF;
        if (d < ((v[0x17] & (1 << i)) ? 42 : 21)) n++;
      }
      if (n) steal += 3 + 2 * n;
      this.vCycle += steal; this.stolenTotal += steal;
    }
  };
  P.rasterLine = function () {
    var c = this.cycleInFrame();
    return Math.floor(c / PAL_LINE_CYCLES) % PAL_LINES;
  };
  P.rasterCycle = function () {
    return Math.floor(this.cycleInFrame()) % PAL_LINE_CYCLES;
  };

  P.beginFrame = function () {
    this.frameEnd = this.frameStart + FRAME_CYCLES;
    this.sidLog.length = 0;
    this.vicLog.length = 0;
    this.ptrLog.length = 0;
    this.vicStart.set(this.vic);
    for (var b = 0; b < 64; b++) this.ptrStart.set(this.ram.subarray(b * 0x400 + 0x3F8, b * 0x400 + 0x400), b * 8);
    this.video.beginFrame();
    this.frameOpen = true;
    this.lastLine = 0;
    this.checkRaster(0);
  };

  P.endFrame = function () {
    this.video.renderTo(PAL_LINES);
    this.frameStart = this.frameEnd;
    this.vCycle -= FRAME_CYCLES;
    this.frame++;
    this.frameOpen = false;
    if (this.hooks) this.hooks.endFrame();
    if (this.onFrame) this.onFrame(this);
  };

  // Run until the end of the current frame. Returns 'frame' when it ended,
  // 'break' when a breakpoint / watchpoint / hook stopped it (this.breakInfo
  // says why; the next run() continues the same frame), 'stopped' when the
  // program ended or the CPU jammed.
  P.run = function () {
    if (this.stopped) return 'stopped';
    if (!this.frameOpen) this.beginFrame();
    var c = this.cpu, hooks = this.hooks, bp = this.bpAt;
    this.breakInfo = null;
    while (this.cycleInFrame() < FRAME_CYCLES) {
      var pc = c.pc;
      if (bp[pc] && pc !== this.skipBreakAt) {
        this.breakInfo = { type: 'break', pc: pc };
        this.skipBreakAt = pc;
        return 'break';
      }
      this.skipBreakAt = -1;
      if (this.exec()) return this.stopped ? 'stopped' : 'break';
    }
    this.endFrame();
    return 'frame';
  };

  // One instruction (plus any interrupt it lets in). Returns true if the
  // machine must stop: the program ended, the CPU jammed, a watchpoint fired
  // or a hook asked for a break.
  P.exec = function () {
    var c = this.cpu, pc = c.pc;
    if (pc === RETURN_TRAP) { this.stopped = 'returned to BASIC'; return true; }
    this.instrPC = pc;
    if (this.hooks && this.hooks.at[pc]) this.hooks.enter(pc); else c.step();
    this.syncClock();
    if (c.jam) { this.stopped = c.jam; return true; }
    if (this.stopped) return true;
    var line = this.rasterLine();
    if (line !== this.lastLine) this.checkRaster(line);
    if (this.cia1.due <= this.now() || this.cia2.due <= this.now()) this.ciaDue();
    if (this.nmiFlag) { this.nmiFlag = false; c.nmi(); }
    if (((this.vicIrq & this.vic[0x1A] & 0x0F) || (this.cia1.icr & this.cia1.icrMask & 0x1F)) && !(c.p & 4)) c.irq();
    if (this.watchHit) {
      this.breakInfo = this.watchHit; this.watchHit = null;
      return true;
    }
    if (this.breakRequest) {
      this.breakInfo = this.breakRequest; this.breakRequest = null;
      return true;
    }
    return false;
  };

  // Raster compare: latch bit 0 of $D019 on the line that matches.
  P.checkRaster = function (line) {
    var cmp = this.vic[0x12] | ((this.vic[0x11] & 0x80) << 1);
    var from = this.lastLine;
    this.lastLine = line;
    // the lines entered since the last check: (from, line], or just 'line' at frame start
    if (line === cmp || (line > from && cmp > from && cmp <= line)) this.vicIrq |= 1;
  };

  // Step one instruction, finishing the frame if it ends. Returns as run().
  P.stepInstruction = function () {
    if (this.stopped) return 'stopped';
    if (!this.frameOpen) this.beginFrame();
    this.skipBreakAt = -1;
    this.breakInfo = null;
    if (this.exec()) return this.stopped ? 'stopped' : 'break';
    if (this.cycleInFrame() >= FRAME_CYCLES) { this.endFrame(); return 'frame'; }
    return 'step';
  };

  // Compatibility: run a whole frame, ignoring breakpoints' "stop" (they still
  // stop if set). Returns false once the program has stopped.
  P.runFrame = function () {
    var r;
    do { r = this.run(); } while (r === 'break' && !this.breakInfo);
    return r !== 'stopped';
  };

  // ---- memory map ------------------------------------------------------------

  // Raster position of a write, for the line-by-line renderer.
  P.logAt = function (log, what, v) {
    var c = Math.floor(this.cycleInFrame());
    log.push(Math.floor(c / PAL_LINE_CYCLES), c % PAL_LINE_CYCLES, what, v);
  };

  // C64 banking: bits 0-2 of the port (inputs read high)
  P.c64Bits = function () { return (this.port1 | ~this.port0) & 7; };

  P.ioVisible = function () {
    if (this.model === 'c128') return (this.mmuCR & 1) === 0;
    if (this.cartMode === 3) return true;                    // Ultimax: I/O always
    var b = this.c64Bits();
    return (b & 4) && (b & 3);
  };

  P.read = function (a) {
    if (this.model === 'c64') {
      if (a < 2) return a === 0 ? this.port0 : ((this.port1 & this.port0) | (~this.port0 & 0x17)) & 0xFF;
      if (this.cartMode && a >= 0x8000) {
        var cb = this.cartRead(a);
        if (cb >= 0) return cb;
      }
      if (a >= 0xE000 && this.standInKernal && this.cartMode !== 3 && (this.c64Bits() & 2)) return KERNAL[a - 0xE000];
      if (a >= 0xD000 && a < 0xE000) {
        var b = this.c64Bits();
        if (this.cartMode === 3 || ((b & 3) && (b & 4))) return this.ioRead(a);
        if (this.cartMode !== 3 && (b & 3) && !(b & 4)) return Font.rom[a & 0x7FF];
      }
      return this.ram[a];
    }
    if (a >= 0xD000 && a < 0xE000 && this.ioVisible()) return this.ioRead(a);
    if (a >= 0xFF00 && a <= 0xFF04) return a === 0xFF00 ? this.mmuCR : 0;
    return this.ram[a];
  };

  // Read without side effects (debugger, watches): I/O shows the register file.
  P.peek = function (a) {
    a &= 0xFFFF;
    if (a >= 0xD000 && a < 0xE000 && this.ioVisible()) {
      if (a < 0xD400) {
        var r = a & 0x3F;
        if (r === 0x12) return this.rasterLine() & 0xFF;
        if (r === 0x19) return this.vicIrq;
        if (r === 0x1E) return this.collSS;
        if (r === 0x1F) return this.collSB;
        return this.vic[r];
      }
      if (a < 0xD800) return a < 0xD500 ? this.sid[a & 0x1F] : 0xFF;
      if (a < 0xDC00) return this.colorRam[a & 0x3FF];
      return this.ram[a];
    }
    if (this.model === 'c64' && a < 2) return a === 0 ? this.port0 : this.port1;
    return this.ram[a];
  };

  // Write from the debugger: RAM always (also under I/O), or I/O when asked.
  P.poke = function (a, v, io) {
    a &= 0xFFFF; v &= 0xFF;
    if (io && a >= 0xD000 && a < 0xE000) { this.ioWrite(a, v); return; }
    this.ram[a] = v;
    if (this.frozenAt[a]) this.frozen[a] = v;
  };

  P.write = function (a, v) {
    if (this.writeLog) this.writeLog.push(a);
    if (this.wpAt[a] && !this.watchHit) {
      this.watchHit = { type: 'watch', addr: a, old: this.peek(a), value: v, pc: this.instrPC };
    }
    if (this.model === 'c64') {
      if (a < 2) { if (a === 0) this.port0 = v; else this.port1 = v; this.ram[a] = v; return; }
      if (a >= 0xD000 && a < 0xE000 && this.ioVisible()) { this.ioWrite(a, v); return; }
    } else {
      if (a >= 0xD000 && a < 0xE000 && this.ioVisible()) { this.ioWrite(a, v); return; }
      if (a === 0xFF00) { this.mmuCR = v; return; }
      if (a > 0xFF00 && a <= 0xFF04) { this.mmuCR = this.mmu[a - 0xFF00]; return; }
    }
    if (this.frozenAt[a]) return;
    if ((a & 0x3F8) === 0x3F8) this.logAt(this.ptrLog, a, v);
    this.ram[a] = v;
  };

  P.ioRead = function (a) {
    if (a < 0xD400) return this.vicRead(a & 0x3F);
    if (this.model === 'c64') {
      if (a < 0xD800) return this.sidRead(a & 0x1F);
    } else {
      if (a < 0xD500) return this.sidRead(a & 0x1F);
      if (a < 0xD600) return (a & 0xFF) === 0 ? this.mmuCR : this.mmu[(a & 0x0F) % 12];
      if (a < 0xD700) return (a & 1) ? this.vdcRead(this.vdcIndex) : 0x80 | 0x02;  // status: ready, version 2
      if (a < 0xD800) return 0xFF;
    }
    if (a < 0xDC00) return (this.colorRam[a & 0x3FF] & 0x0F) | 0xF0;
    if (a < 0xDD00) return this.cia1Read(a & 0x0F);
    if (a < 0xDE00) return this.cia2Read(a & 0x0F);
    if (this.cart && a >= 0xDF00) return this.efRam[a & 0xFF];
    return 0xFF;
  };

  P.ioWrite = function (a, v) {
    if (a < 0xD400) { this.vicWrite(a & 0x3F, v); return; }
    if (this.model === 'c64') {
      if (a < 0xD800) { this.sidWrite(a & 0x1F, v); return; }
    } else {
      if (a < 0xD500) { this.sidWrite(a & 0x1F, v); return; }
      if (a < 0xD600) { if ((a & 0xFF) === 0) this.mmuCR = v; else this.mmu[(a & 0x0F) % 12] = v; return; }
      if (a < 0xD700) { if (a & 1) this.vdcWrite(this.vdcIndex, v); else this.vdcIndex = v & 0x3F; return; }
      if (a < 0xD800) return;
    }
    if (a < 0xDC00) { this.colorRam[a & 0x3FF] = v & 0x0F; return; }
    if (a < 0xDD00) { this.ciaWrite(this.cia1, a & 0x0F, v); return; }
    if (a < 0xDE00) { this.ciaWrite(this.cia2, a & 0x0F, v); return; }
    if (this.cart) {
      if (a >= 0xDF00) this.efRam[a & 0xFF] = v;
      else if (a === 0xDE00) this.efBank = v & 0x3F;
      else if (a === 0xDE02) this.setCartCtl(v);
    }
  };

  // ---- VIC registers -------------------------------------------------------

  P.vicWrite = function (r, v) {
    if (r === 0x19) { this.vicIrq &= ~v & 0x0F; return; }      // acknowledge
    if (r === 0x1E || r === 0x1F) return;
    if (r === 0x30 && this.model === 'c64') return;
    this.logAt(this.vicLog, r, v);
    this.vic[r] = v;
    if (r === 0x12 || r === 0x11) {
      // the compare matches at once if it is set to the current line
      var cmp = this.vic[0x12] | ((this.vic[0x11] & 0x80) << 1);
      if (cmp === this.rasterLine() && this.rasterCycle() === 0) this.vicIrq |= 1;
    }
  };

  P.vicRead = function (r) {
    var line, v;
    switch (r) {
      case 0x11: line = this.rasterLine(); return (this.vic[0x11] & 0x7F) | ((line & 0x100) >> 1);
      case 0x12: return this.rasterLine() & 0xFF;
      case 0x19: return this.vicIrq | 0x70 | ((this.vicIrq & this.vic[0x1A] & 0x0F) ? 0x80 : 0);
      case 0x1E: this.video.renderTo(this.rasterLine()); v = this.collSS; this.collSS = 0; return v;
      case 0x1F: this.video.renderTo(this.rasterLine()); v = this.collSB; this.collSB = 0; return v;
      case 0x16: return this.vic[r] | 0xC0;
      case 0x18: return this.vic[r] | 0x01;
      case 0x1A: return this.vic[r] | 0xF0;
      case 0x2F: return this.model === 'c128' ? this.vic[r] | 0xF8 : 0xFF;
      case 0x30: return this.model === 'c128' ? this.vic[r] | 0xFC : 0xFF;
    }
    if (r >= 0x20 && r <= 0x2E) return this.vic[r] | 0xF0;
    if (r > 0x30) return 0xFF;
    return this.vic[r];
  };

  // VIC bank from CIA2 port A bits 0-1 (inverted)
  P.vicBank = function () {
    var pa = (this.cia2.pra & this.cia2.ddra) | (~this.cia2.ddra & 0xFF);
    return (3 - (pa & 3)) * 0x4000;
  };

  // ---- CIA ---------------------------------------------------------------

  // Timers up to the clock. TA / TB underflows set ICR bits 0 / 1; TB counts the clock
  // (CRB bits 6-5 = 00) or TA's underflows (10).
  P.ciaSync = function (cia) {
    var n = this.now() - cia.last, ua = 0;
    cia.last += n;
    if (n <= 0) return;
    if ((cia.cra & 1) && !(cia.cra & 0x20)) ua = adv(cia, 'a', n);
    if (cia.crb & 1) {
      var src = (cia.crb >> 5) & 3;
      if (src === 0) adv(cia, 'b', n); else if (src === 2 && ua) adv(cia, 'b', ua);
    }
  };

  // When does the next enabled interrupt fall due? (An underflow of timer B counting
  // TA's underflows is caught after TA's.)
  P.ciaSchedule = function (cia) {
    var d = NEVER;
    if ((cia.icrMask & 1) && (cia.cra & 1) && !(cia.cra & 0x20)) d = cia.last + cia.ta + 1;
    if ((cia.icrMask & 2) && (cia.crb & 1) && ((cia.crb >> 5) & 3) === 0) d = Math.min(d, cia.last + cia.tb + 1);
    cia.due = d;
  };

  P.ciaDue = function () {
    var cs = [this.cia1, this.cia2];
    for (var i = 0; i < 2; i++) {
      var cia = cs[i], before = cia.icr;
      this.ciaSync(cia);
      if (i === 1 && (cia.icr & ~before & cia.icrMask & 0x1F)) this.nmiFlag = true;
      this.ciaSchedule(cia);
    }
  };

  // Time of day: the clock runs on the system clock (a tenth every 98525 cycles); hours
  // are 1-12 with a PM bit. Writing the hours stops it until the tenths are written; it
  // raises ICR bit 2 whenever it equals the alarm (a write counts: Psi-5 checks for that).
  P.todTick = function (cia) {
    var n = this.now() - cia.todLast;
    if (!cia.todRun) { cia.todLast = this.now(); return; }
    var k = Math.floor(n / TOD_TENTH);
    cia.todLast += k * TOD_TENTH;
    while (k-- > 0) {
      var t = cia.tod, x = bcdInc(t[0], 9);
      if (x >= 0) t[0] = x;
      else {
        t[0] = 0; x = bcdInc(t[1], 59);
        if (x >= 0) t[1] = x;
        else {
          t[1] = 0; x = bcdInc(t[2], 59);
          if (x >= 0) t[2] = x;
          else {
            t[2] = 0;
            var h = t[3] & 0x1F, pm = t[3] & 0x80;
            if (h === 0x11) { h = 0x12; pm ^= 0x80; } else if (h === 0x12) h = 1; else h = bcdInc(h, 12);
            t[3] = h | pm;
          }
        }
      }
      this.todCompare(cia);
    }
  };
  P.todCompare = function (cia) {
    var t = cia.tod, a = cia.alarm;
    if (t[0] === a[0] && t[1] === a[1] && t[2] === a[2] && t[3] === a[3]) {
      cia.icr |= 4;
      if (cia === this.cia2 && (cia.icrMask & 4)) this.nmiFlag = true;
    }
  };

  P.ciaWrite = function (cia, r, v) {
    if (r >= 8 && r <= 11) {
      var i = r - 8;
      v &= [0x0F, 0x7F, 0x7F, 0x9F][i];
      if (cia.crb & 0x80) cia.alarm[i] = v;
      else {
        this.todTick(cia);
        cia.tod[i] = v;
        if (i === 3) cia.todRun = false;
        if (i === 0) { cia.todRun = true; cia.todLast = this.now(); }
      }
      this.todCompare(cia);
      return;
    }
    var tmr = r >= 4 && r <= 7 || r >= 0x0D && r <= 0x0F;
    if (tmr) this.ciaSync(cia);
    switch (r) {
      case 0: cia.pra = v; break;
      case 1: cia.prb = v; break;
      case 2: cia.ddra = v; break;
      case 3: cia.ddrb = v; break;
      case 4: cia.la = (cia.la & 0xFF00) | v; break;
      case 5: cia.la = (cia.la & 0x00FF) | (v << 8); if (!(cia.cra & 1)) cia.ta = cia.la; break;
      case 6: cia.lb = (cia.lb & 0xFF00) | v; break;
      case 7: cia.lb = (cia.lb & 0x00FF) | (v << 8); if (!(cia.crb & 1)) cia.tb = cia.lb; break;
      case 0x0D:
        if (v & 0x80) cia.icrMask |= v & 0x1F; else cia.icrMask &= ~v;
        if (cia === this.cia2 && (cia.icr & cia.icrMask & 0x1F)) this.nmiFlag = true;
        break;
      case 0x0E: if (v & 0x10) cia.ta = cia.la; cia.cra = v & ~0x10; break;
      case 0x0F: if (v & 0x10) cia.tb = cia.lb; cia.crb = v & ~0x10; break;
    }
    if (tmr) this.ciaSchedule(cia);
  };

  // Timer / ICR reads, common to both CIAs; -1 for the other registers.
  P.ciaTimerRead = function (cia, r) {
    if (r >= 8 && r <= 11) {
      this.todTick(cia);
      var i = r - 8, l = cia.todLatch;
      if (i === 3 && !l) cia.todLatch = cia.tod.slice();       // reading the hours latches the time
      var v = (cia.todLatch || cia.tod)[i];
      if (i === 0) cia.todLatch = null;
      return v;
    }
    if (r < 4 || (r > 7 && r < 0x0D) || r > 0x0F) return -1;
    this.ciaSync(cia);
    switch (r) {
      case 4: return cia.ta & 0xFF;
      case 5: return cia.ta >> 8;
      case 6: return cia.tb & 0xFF;
      case 7: return cia.tb >> 8;
      case 0x0D: {
        var v = cia.icr | ((cia.icr & cia.icrMask & 0x1F) ? 0x80 : 0);
        cia.icr = 0;
        this.ciaSchedule(cia);
        return v;
      }
      case 0x0E: return cia.cra;
      default: return cia.crb;
    }
  };

  // Port 2 joystick lines (active low), with the 1351's buttons on fire/up.
  P.port2Lines = function () {
    var j = this.joy2;
    if (this.mouse.present) {
      if (this.mouse.left) j |= 0x10;
      if (this.mouse.right) j |= 0x01;
    }
    return ~j & 0x1F | 0xE0;
  };

  P.cia1Read = function (r) {
    var cia = this.cia1;
    switch (r) {
      case 0: {
        var out = (cia.pra & cia.ddra) | (~cia.ddra & 0xFF);
        return out & this.port2Lines();
      }
      case 1: {
        // keyboard: AND of the rows of every column driven low on port A
        var cols = ((cia.pra & cia.ddra) | (~cia.ddra & 0xFF)) & this.port2Lines();
        var rows = 0xFF;
        for (var c = 0; c < 8; c++) if (!(cols & (1 << c))) rows &= ~this.keys[c];
        return rows & 0xFF;
      }
      case 2: return cia.ddra;
      case 3: return cia.ddrb;
    }
    var t = this.ciaTimerRead(cia, r);
    return t < 0 ? 0 : t;
  };

  P.cia2Read = function (r) {
    var cia = this.cia2;
    if (r === 0) return (cia.pra & cia.ddra) | (~cia.ddra & 0xFF);
    if (r === 1) return 0xFF;
    if (r === 2) return cia.ddra;
    if (r === 3) return cia.ddrb;
    var t = this.ciaTimerRead(cia, r);
    return t < 0 ? 0 : t;
  };

  // ---- SID ---------------------------------------------------------------

  P.sidWrite = function (r, v) {
    this.sid[r] = v;
    if (r < 0x19) this.sidLog.push(Math.floor(this.cycleInFrame()), r, v);
  };

  P.sidRead = function (r) {
    switch (r) {
      case 0x19: return this.potValue(0);
      case 0x1A: return this.potValue(1);
      case 0x1B: return this.osc3();
      case 0x1C: return 0;
    }
    return 0;
  };

  // 1351 in proportional mode: bits 6-1 carry the position, read on port 2
  // when CIA1 port A bits 7/6 select it. An empty port reads $FF.
  P.potValue = function (axis) {
    var sel = this.cia1.pra & 0xC0;
    if (!this.mouse.present || sel !== 0x80) return 0xFF;
    var v = axis === 0 ? this.mouse.x : this.mouse.y;
    return (v << 1) & 0x7E;
  };

  // Voice 3 oscillator output. Only the noise waveform matters here (used as a
  // random source), so it is the SID's 23-bit LFSR clocked by the voice 3
  // accumulator.
  P.osc3 = function () {
    var now = this.cpu.cycles;
    var freq = this.sid[0x0E] | (this.sid[0x0F] << 8);
    var elapsed = now - (this.osc3Time || 0);
    this.osc3Time = now;
    var phase = this.noisePhase + freq * elapsed;
    var clocks = Math.floor(phase / 0x80000);          // bit 19 rising edges
    this.noisePhase = phase % 0x80000;
    clocks = Math.min(clocks, 64);
    var n = this.noise;
    for (var i = 0; i < clocks; i++) {
      var bit = ((n >> 22) ^ (n >> 17)) & 1;
      n = ((n << 1) | bit) & 0x7FFFFF;
    }
    this.noise = n;
    if ((this.sid[0x12] & 0x80) === 0) return 0;
    return ((n >> 15) & 0x80) | ((n >> 14) & 0x40) | ((n >> 11) & 0x20) | ((n >> 9) & 0x10) |
           ((n >> 8) & 0x08) | ((n >> 5) & 0x04) | ((n >> 3) & 0x02) | ((n >> 2) & 0x01);
  };

  // ---- VDC (8563) ----------------------------------------------------------

  P.vdcAddr = function () { return ((this.vdcReg[18] << 8) | this.vdcReg[19]) & 0xFFFF; };
  P.vdcSetAddr = function (a) { this.vdcReg[18] = (a >> 8) & 0xFF; this.vdcReg[19] = a & 0xFF; };

  P.vdcWrite = function (r, v) {
    var reg = this.vdcReg, i, n, a;
    reg[r] = v;
    if (r === 31) {
      a = this.vdcAddr();
      this.vdcRam[a] = v;
      this.vdcSetAddr(a + 1);
    } else if (r === 30) {
      // word count: N more writes (fill with R31) or copies (R24 bit 7)
      n = v === 0 ? 256 : v;
      a = this.vdcAddr();
      if (reg[24] & 0x80) {
        var src = (reg[32] << 8) | reg[33];
        for (i = 0; i < n; i++) this.vdcRam[(a + i) & 0xFFFF] = this.vdcRam[(src + i) & 0xFFFF];
        src += n; reg[32] = (src >> 8) & 0xFF; reg[33] = src & 0xFF;
      } else {
        for (i = 0; i < n; i++) this.vdcRam[(a + i) & 0xFFFF] = reg[31];
      }
      this.vdcSetAddr(a + n);
    }
  };

  P.vdcRead = function (r) {
    if (r === 31) {
      var a = this.vdcAddr(), v = this.vdcRam[a];
      this.vdcSetAddr(a + 1);
      return v;
    }
    return this.vdcReg[r];
  };

  // ---- input ---------------------------------------------------------------

  P.setKey = function (col, row, down) {
    if (down) this.keys[col] |= (1 << row); else this.keys[col] &= ~(1 << row);
  };

  // Mouse motion in 1351 counts (Y up is positive, as on the real mouse).
  P.moveMouse = function (dx, dy) {
    this.mouse.x = (this.mouse.x + dx) & 0x3F;
    this.mouse.y = (this.mouse.y + dy) & 0x3F;
  };

  // ---- debugging -------------------------------------------------------------

  P.setBreak = function (a, on) { this.bpAt[a & 0xFFFF] = on ? 1 : 0; };
  P.setWatch = function (a, on) { this.wpAt[a & 0xFFFF] = on ? 1 : 0; };
  P.freeze = function (a, v) {
    a &= 0xFFFF;
    if (v === null || v === undefined) { this.frozenAt[a] = 0; delete this.frozen[a]; return; }
    this.ram[a] = v & 0xFF; this.frozenAt[a] = 1; this.frozen[a] = v & 0xFF;
  };

  // ---- save / load state -------------------------------------------------------

  var ARRAYS = ['ram', 'colorRam', 'vic', 'sid', 'vdcRam', 'vdcReg', 'mmu', 'vicStart', 'ptrStart', 'keys', 'efRam'];
  var SCALARS = ['model', 'mmuCR', 'port0', 'port1', 'vicIrq', 'collSS', 'collSB', 'vdcIndex', 'joy2',
                 'noise', 'noisePhase', 'osc3Time', 'stopped', 'frame', 'frameStart', 'frameEnd', 'vCycle', 'lastCpu',
                 'frameOpen', 'lastLine', 'efBank', 'efCtl', 'stolenTotal', 'nmiFlag'];

  P.saveState = function () {
    var s = { version: 1, cpu: {}, arrays: {}, cia1: cloneCia(this.cia1),
              cia2: cloneCia(this.cia2), mouse: Object.assign({}, this.mouse),
              vicLog: this.vicLog.slice(), ptrLog: this.ptrLog.slice(), sidLog: this.sidLog.slice()};
    var self = this;
    ['a', 'x', 'y', 'sp', 'pc', 'p', 'cycles'].forEach(function (k) { s.cpu[k] = self.cpu[k]; });
    ARRAYS.forEach(function (k) { if (!(k === 'vdcRam' && self.model === 'c64')) s.arrays[k] = self[k].slice(); });
    SCALARS.forEach(function (k) { s[k] = self[k]; });
    return s;
  };

  P.loadState = function (s) {
    var self = this;
    if (s.model !== this.model) throw new Error('state is for a ' + s.model + ', this machine is a ' + this.model);
    ['a', 'x', 'y', 'sp', 'pc', 'p', 'cycles'].forEach(function (k) { self.cpu[k] = s.cpu[k]; });
    this.cpu.jam = null;
    ARRAYS.forEach(function (k) { if (s.arrays[k]) self[k].set(s.arrays[k]); });
    SCALARS.forEach(function (k) { self[k] = s[k]; });
    if (s.vCycle === undefined) { this.vCycle = s.cpu.cycles - s.frameStart; this.lastCpu = s.cpu.cycles; }
    this.cia1 = cloneCia(Object.assign(newCia({}), s.cia1)); this.cia2 = cloneCia(Object.assign(newCia({}), s.cia2));
    this.setCartCtl(this.efCtl || 0);
    Object.assign(this.mouse, s.mouse);
    this.vicLog = s.vicLog.slice(); this.ptrLog = s.ptrLog.slice(); this.sidLog = s.sidLog.slice();
    // frozen addresses are debugger settings, not machine state: they stay and win
    for (var a in this.frozen) this.ram[a] = this.frozen[a];
    this.writeLog = null; this.watchHit = null; this.breakInfo = null; this.skipBreakAt = this.cpu.pc;
    if (this.hooks) this.hooks.resetPending();
    // re-render the part of the frame that already ran
    this.video.replay(this.frameOpen ? this.rasterLine() : PAL_LINES);
  };

  // Compact text form (base64 of a JSON with base64 arrays), for files / storage.
  P.stateToText = function (s) {
    s = s || this.saveState();
    var o = Object.assign({}, s, { arrays: {} });
    for (var k in s.arrays) o.arrays[k] = b64(s.arrays[k]);
    return JSON.stringify(o);
  };
  P.stateFromText = function (t) {
    var o = JSON.parse(t);
    for (var k in o.arrays) o.arrays[k] = unb64(o.arrays[k]);
    return o;
  };

  function b64(u8) {
    if (typeof Buffer !== 'undefined') return Buffer.from(u8).toString('base64');
    var s = '';
    for (var i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
    return btoa(s);
  }
  function unb64(t) {
    if (typeof Buffer !== 'undefined') return new Uint8Array(Buffer.from(t, 'base64'));
    var s = atob(t), u = new Uint8Array(s.length);
    for (var i = 0; i < s.length; i++) u[i] = s.charCodeAt(i);
    return u;
  }

  Machine.FRAME_CYCLES = FRAME_CYCLES;
  Machine.LINE_CYCLES = PAL_LINE_CYCLES;
  Machine.LINES = PAL_LINES;
  Machine.RETURN_TRAP = RETURN_TRAP;
  return Machine;
})();

if (typeof module !== 'undefined') module.exports = C128;
