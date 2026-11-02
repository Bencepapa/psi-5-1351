"""Dictionary repacker for Psi-5's independently decoded crew messages."""

BASES = (0xEC80, 0xF0BE, 0xF42D, 0xF934, 0xFBDD)
TAILS = (0xF0A7, 0xF421, 0xF8D7, 0xFBC4, 0xFF9F)
COUNTS = (22, 18, 27, 14, 20)

ESCAPE = 17
END = 60

# Greedy corpus dictionary. Entries are raw symbols and never nest.
DICTIONARY = (
    (47,34,47,36,50,47,41,36), (41,38,37,0,51,53,48,48,47,50,52),
    (36,33,45,33,39,37,36), (0,51,57,51,52,37,45), (28,0,0),
    (50,37,48,33,41,50), (0,52,47,0), (0,41,51,0), (34,50,47,43,37,46),
    (29,0,51,41,50), (52,33,50,34,47,33,50,36,0,50,37,52,50,47),
    (0,40,33,51,0,34,37,37,46), (41,46,39,0), (0,36,37,51,52,50,47,57,37,36),
    (52,41,47,46), (33,50,39,47), (0,48,47,55,37,50),
    (3,50,33,54,37,46,44,33,52,47,50), (5,46,39,41,46,37), (0,52,40,37),
    (0,33,50,37), (37,33,35,52,47,50,0), (47,46,37), (30,0,0),
    (40,47,51,37,0), (41,46,39), (54,37,0), (0,40,33), (0,0,0,0),
    (0,52,47), (0,50,37,52,50,47), (47,50,52),
)

# Reclaimed holes. Special data immediately following each department remains fixed.
MOUSE_PAYLOAD = 0xEFB8       # first 239 bytes
MOUSE_LAST = 0xF38F          # final byte
DICT_OFFSETS = 0xF390
DISPATCH = 0xF80E
DICT_DATA = 0xFEB5


def _at(mem, start, address):
    return address - start


def unpack6(payload):
    out = []
    for i in range(0, len(payload), 3):
        a, b, c = (payload[i:i + 3] + bytes(3))[:3]
        for symbol in (a & 0x3F, ((b << 2) | (a >> 6)) & 0x3F,
                       ((c << 4) | (b >> 4)) & 0x3F, (c >> 2) & 0x3F):
            out.append(symbol)
            if symbol == END:
                return tuple(out)
    raise ValueError('message has no terminator')


def pack6(symbols):
    out = bytearray()
    for i in range(0, len(symbols), 4):
        group = list(symbols[i:i + 4])
        actual = len(group)
        group += [0] * (4 - actual)
        a, b, c, d = group
        packed = (a | ((b & 3) << 6), (b >> 2) | ((c & 15) << 4), (c >> 4) | (d << 2))
        out.extend(packed[:(0, 2, 2, 3, 3)[actual]])
    return bytes(out)


def encode(symbols):
    cost = [10**9] * (len(symbols) + 1)
    choice = [None] * len(symbols)
    cost[-1] = 0
    for i in range(len(symbols) - 1, -1, -1):
        cost[i] = 1 + cost[i + 1]
        choice[i] = (1, None)
        for token, phrase in enumerate(DICTIONARY):
            n = len(phrase)
            if symbols[i:i + n] == phrase and 2 + cost[i + n] < cost[i]:
                cost[i] = 2 + cost[i + n]
                choice[i] = (n, token)
    out = []
    i = 0
    while i < len(symbols):
        n, token = choice[i]
        if token is None:
            assert symbols[i] != ESCAPE
            out.append(symbols[i])
        else:
            out.extend((ESCAPE, token))
        i += n
    return tuple(out)


def expand(symbols):
    out = []
    i = 0
    while i < len(symbols):
        if symbols[i] == ESCAPE:
            out.extend(DICTIONARY[symbols[i + 1]])
            i += 2
        else:
            out.append(symbols[i])
            i += 1
    return tuple(out)


def patch_messages(mem, start, mouse, dispatcher):
    """Repack message records in place and occupy only their newly reclaimed tails."""
    assert len(mouse) == 240
    assert len(dispatcher) <= 0xF8D7 - DISPATCH
    originals = []
    for base, tail, count in zip(BASES, TAILS, COUNTS):
        p = base
        records = []
        for _ in range(count):
            n = mem[_at(mem, start, p)]
            payload = bytes(mem[_at(mem, start, p + 1):_at(mem, start, p + 1 + n)])
            symbols = unpack6(payload)
            records.append(symbols)
            originals.append(symbols)
            p += 1 + n
        assert p == tail

        packed_records = bytearray()
        for symbols in records:
            coded = encode(symbols[:-1]) + (END,)
            assert expand(coded) == symbols
            payload = pack6(coded)
            packed_records += bytes([len(payload)]) + payload
        assert base + len(packed_records) <= tail
        lo, hi = _at(mem, start, base), _at(mem, start, tail)
        mem[lo:hi] = packed_records.ljust(tail - base, b'\0')

    offsets = bytearray()
    data = bytearray()
    for phrase in DICTIONARY:
        offsets.append(len(data))
        data.extend(phrase)
        data.append(ESCAPE)
    assert len(offsets) == 32 and len(data) == 212

    def put(address, blob):
        i = _at(mem, start, address)
        mem[i:i + len(blob)] = blob

    put(MOUSE_PAYLOAD, mouse[:-1])
    put(MOUSE_LAST, mouse[-1:])
    put(DICT_OFFSETS, offsets)
    put(DICT_DATA, data)
    put(DISPATCH, dispatcher)

    # Decode the repacked records again as a build-time corpus proof.
    check = []
    for base, count in zip(BASES, COUNTS):
        p = base
        for _ in range(count):
            n = mem[_at(mem, start, p)]
            coded = unpack6(bytes(mem[_at(mem, start, p + 1):_at(mem, start, p + 1 + n)]))
            check.append(expand(coded))
            p += 1 + n
    assert check == originals
    return len(originals)


def patch_decoder(mem, start):
    for address in (0xC83E, 0xC856, 0xC876, 0xC882):
        i = _at(mem, start, address)
        assert bytes(mem[i:i + 3]) == b'\x20\x90\xC8'
        mem[i + 1:i + 3] = bytes([DISPATCH & 255, DISPATCH >> 8])
