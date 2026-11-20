"""Follow the pages queued to the firmware's PCM: device from script dumps.

The device consumes in real time, also under --mute, so tests cannot step a
read pointer. Instead each snapshot reads the 24-bit counters kept since the
stream's last flush (_pcm_written, _pcm_consumed) and the four-page staging
ring. Page k of a stream is the k-th 256-byte page queued since that flush and
sits in ring slot k % 4 until four more pages are queued.
"""


def snapshot(sym, ring, extra=()):
    """Script commands for one snapshot: written, consumed, ring, extras."""
    return [f'dump 0x{sym["pcm_written"]:04x} 3', f'dump 0x{sym["pcm_consumed"]:04x} 3',
            f'dump xram:0x{ring:04x} 1024', *extra]


def counter(data):
    return int.from_bytes(data, 'little')


class Stream:
    """Collect each queued page once, in order, from consecutive snapshots."""

    def __init__(self):
        self.pages = {}
        self.written = None
        self.consumed = None

    def add(self, written, consumed, ring):
        """Returns False once the stream was flushed (its counters restarted)."""
        written, consumed = counter(written), counter(consumed)
        if self.written is not None and written < self.written:
            return False
        count = written // 256
        first = count - 4 if self.written is None else self.written // 256
        assert count - first <= 4, 'More pages were queued between snapshots than the ring holds'
        for page in range(max(0, first), count):
            self.pages[page] = bytes(ring[(page % 4)*256:(page % 4 + 1)*256])
        self.written, self.consumed = written, consumed
        return True

    def queued(self):
        """Bytes queued at the last clock, as the sequencers saw them."""
        return self.written - self.consumed

    def contiguous(self):
        """The page indices seen, checked to have no gap."""
        pages = sorted(self.pages)
        assert pages == list(range(pages[0], pages[-1] + 1)), 'A queued page was missed'
        return pages
