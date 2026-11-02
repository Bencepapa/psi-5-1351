"""Read PRG directory entries and sector chains without launching c1541."""
from d64put import SPT, ts_off


def sector(disk, track, number):
    if not 1 <= track < len(SPT) or not 0 <= number < SPT[track]:
        raise ValueError(f'invalid D64 sector {track}/{number}')
    offset = ts_off(track, number)
    if offset + 256 > len(disk):
        raise ValueError(f'truncated D64 sector {track}/{number}')
    return disk[offset:offset + 256]


def prg_entries(disk):
    """Yield (lowercase ASCII name, first track, first sector) in disk order."""
    track, number = 18, 1
    seen = set()
    while track:
        if (track, number) in seen:
            raise ValueError('cyclic D64 directory')
        seen.add((track, number))
        block = sector(disk, track, number)
        for offset in range(0, 256, 32):
            if block[offset + 2] & 7 == 2:
                name = block[offset + 5:offset + 21].rstrip(b'\xa0').decode('ascii').lower()
                yield name, block[offset + 3], block[offset + 4]
        track, number = block[:2]


def read_file(disk, track, number):
    result = bytearray()
    seen = set()
    while track:
        if (track, number) in seen:
            raise ValueError('cyclic D64 file chain')
        seen.add((track, number))
        block = sector(disk, track, number)
        next_track, next_number = block[:2]
        if next_track:
            result.extend(block[2:])
        else:
            if next_number == 0:
                raise ValueError('invalid D64 final-sector byte count')
            result.extend(block[2:next_number + 1])
        track, number = next_track, next_number
    return bytes(result)
