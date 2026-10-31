"""Build the browser pages from page.html.

  js/index.html          loads src/*.js and programs.js (serve js/ with any static server)
  js/dist/psi5.html  one self-contained file, scripts inlined
  --fragment PATH        the same without the doctype/head skeleton (for publishing)
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = ['programs.js', 'src/cpu6502.js', 'src/font.js', 'src/video.js', 'src/machine.js',
           'src/hooks.js', 'src/disasm.js', 'src/debugger.js', 'src/profiles.js',
           'src/audio.js', 'src/app.js']
HEAD = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')


def page():
    with open(os.path.join(HERE, 'page.html'), encoding='utf-8') as f:
        return f.read()


def inline():
    parts = []
    for s in SCRIPTS:
        with open(os.path.join(HERE, s), encoding='utf-8') as f:
            parts.append('<script>\n' + f.read().replace('</script', '<\\/script') + '\n</script>')
    return '\n'.join(parts)


def full(body):
    head, rest = body.split('<div class="wrap">', 1)
    return HEAD + head + '</head>\n<body>\n<div class="wrap">' + rest + '</body>\n</html>\n'


def main():
    src = page()
    tags = '\n'.join(f'<script src="{s}"></script>' for s in SCRIPTS)
    with open(os.path.join(HERE, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(full(src.replace('<!--SCRIPTS-->', tags)))
    os.makedirs(os.path.join(HERE, 'dist'), exist_ok=True)
    one = src.replace('<!--SCRIPTS-->', inline())
    with open(os.path.join(HERE, 'dist', 'psi5.html'), 'w', encoding='utf-8') as f:
        f.write(full(one))
    docs = os.path.join(os.path.dirname(HERE), 'docs')
    os.makedirs(docs, exist_ok=True)
    with open(os.path.join(docs, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(full(one))
    shutil.copyfile(os.path.join(HERE, 'ref', 'psi5_ef_tested.crt'),
                    os.path.join(docs, 'psi5_ef.crt'))
    shutil.copyfile(os.path.join(HERE, 'ref', 'psi5_ef_bridge_tested.crt'),
                    os.path.join(docs, 'psi5_ef_bridge.crt'))
    if '--fragment' in sys.argv:
        with open(sys.argv[sys.argv.index('--fragment') + 1], 'w', encoding='utf-8') as f:
            f.write(one)
    print('wrote js/index.html, js/dist/psi5.html, and docs/')


if __name__ == '__main__':
    main()
