// Debugger profile for Psi-5: what to watch, which events exist, which on-screen keys to
// show. Addresses are labels from psi5-symbols.txt (js/build.py puts them into programs.js)
// or '$hex'.
//
//   watches: {name, at, size (bytes, default 1), fmt: 'dec' | 'hex' | 'bytes'}
//   cheats:  {id, name, help, freeze: [{at, size, value}]}   value omitted = keep current
//            {id, name, help, skip: 'LABEL'}                  the routine returns at once
//   events:  {name, at: 'LABEL', pause: bool}                 log (and pause) when entered
//   keys:    on-screen buttons: {label, mouse: 'left'|'right'|'both'} or {label, key: 'Space'}
'use strict';

var SentinelProfiles = {
  psi5: {
    title: 'Psi-5 Trading Company (EasyFlash, +4D 101%)',
    watches: [
      { name: 'Department', at: 'DEPTLETTER', fmt: 'hex' },
      { name: 'Command record', at: 'CMDDEPT', size: 6, fmt: 'bytes' },
      { name: 'Menu depth', at: 'MENUDEPTH' },
      { name: 'Bridge key count', at: 'BRIDGEKEYCOUNT' },
      { name: 'Device states A-L', at: 'DEVSTATE', size: 12, fmt: 'bytes' },
      { name: 'Device requests', at: 'DEVREQ', size: 12, fmt: 'bytes' },
      { name: 'Pointer column', at: 'POINTERCOL' },
      { name: 'Pointer row', at: 'POINTERROW' },
      { name: 'Mouse X / Y', at: 'MOUSEX', size: 2, fmt: 'bytes' },
      { name: 'Mouse buttons', at: 'MOUSEBTN', fmt: 'hex' },
      { name: 'Mouse detected', at: 'MOUSEON', fmt: 'hex' },
    ],
    cheats: [],
    events: [
      { name: 'File load (cartridge)', at: 'EFCDLD' },
      { name: 'Raw load (cartridge)', at: 'EFRAWLD' },
      { name: 'Status', at: 'H_STATUS' },
      { name: 'Display', at: 'H_DISPLAY' },
      { name: 'Rank', at: 'H_RANK' },
      { name: 'Cancel', at: 'H_CANCEL' },
      { name: 'Enable / cancel a device', at: 'SETDEVICE' },
      { name: 'QUIT (loads from disk)', at: 'RESTART', pause: true },
    ],
    keys: [
      { label: 'Click / L', mouse: 'left' },
      { label: 'R', mouse: 'right' },
      { label: 'RETURN', key: 'Enter' },
      { label: 'SPACE', key: 'Space' },
      { label: '←', key: 'Backquote' },
      { label: 'Y', key: 'KeyY' },
      { label: 'N', key: 'KeyN' },
      { label: '1', key: 'Digit1' },
      { label: '2', key: 'Digit2' },
      { label: '3', key: 'Digit3' },
      { label: '4', key: 'Digit4' },
    ],
    help: 'Mouse (port 2): the pointer is a flipped character cell on the lower half of the bridge; click a word on the menu row to type its key, click outside menus for the fire button. ' +
          'Keyboard: letters and digits as on the C64, Enter = RETURN, ` = ←. Arrows + Right Ctrl: joystick. Answer N at the trainer prompt, click or fire at the title. QUIT needs the disk drive and does not work here.',
  },
};

if (typeof module !== 'undefined') module.exports = SentinelProfiles;
