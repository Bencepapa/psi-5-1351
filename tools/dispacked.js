// Disassemble original packed game files using their decoded load address.
// Usage: node tools/dispacked.js c ce70 60
'use strict';
const path = require('path');
const cp = require('child_process');
const D = require('../js/src/disasm.js');
const root = path.resolve(__dirname, '..');
const [name, address, count = '60'] = process.argv.slice(2);
if (!name || !address) throw new Error('usage: dispacked.js FILE HEX_ADDRESS [COUNT]');
const script = 'import sys,json;from pathlib import Path;sys.path.insert(0,"tools");' +
  'from krillpack import decode;r=decode(Path(sys.argv[1]).read_bytes());' +
  'print(json.dumps([r[1],list(r[2])]))';
const [start, bytes] = JSON.parse(cp.execFileSync('python', ['-c', script,
  path.join(root, 'plus4d', name + '.prg')], { cwd: root, encoding: 'utf8' }));
const mem = new Uint8Array(65536);
mem.set(bytes, start);
const pc = parseInt(address, 16);
if (pc < start || pc >= start + bytes.length) throw new Error('address outside decoded file');
console.log(`${name}: $${start.toString(16)}-$${(start + bytes.length - 1).toString(16)}`);
for (const d of D.range(a => mem[a], pc, Number(count))) {
  console.log(`${D.h4(d.pc)}  ${d.bytes.map(D.h2).join(' ').padEnd(8)} ${d.text}`);
}
