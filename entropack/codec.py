"""Baseline entropy coder for entropack.

This module currently contains only the most naive implementation: a
fixed-width encoder. Every symbol in a fixed alphabet is written with the
same number of bits, so the encoded size depends only on the number of
symbols, never on how often each symbol actually occurs.

There is no frequency counting, no variable-length coding, no prefix code
and no tree of any kind here.
"""


class EntropyError(Exception):
    """Base class for all errors raised by entropack."""


class InvalidAlphabetError(EntropyError):
    """Raised when an alphabet is empty or otherwise unusable."""


class SymbolNotFoundError(EntropyError):
    """Raised when a symbol to encode is not part of the alphabet."""


class BitStreamError(EntropyError):
    """Raised when a bit stream cannot be decoded as requested."""


def _ceil_log2(n):
    """Smallest number of bits needed to index n distinct values."""
    bits = 0
    value = 1
    while value < n:
        value <<= 1
        bits += 1
    return bits


class FixedWidth:
    """Encodes symbols of a fixed alphabet using a constant bit width.

    The alphabet is an ordered sequence of single-character strings. Each
    symbol is written as the fixed-width binary form of its index in that
    sequence. The final byte is zero padded. Decoding therefore has to be
    told how many symbols to read back.
    """

    def __init__(self, symbols):
        self._symbols = list(symbols)
        if not self._symbols:
            raise InvalidAlphabetError("alphabet must not be empty")
        if len(set(self._symbols)) != len(self._symbols):
            raise InvalidAlphabetError("alphabet must not contain duplicates")
        self._width = max(1, _ceil_log2(len(self._symbols)))
        self._index = {sym: i for i, sym in enumerate(self._symbols)}

    @property
    def width(self):
        """Number of bits used for every symbol."""
        return self._width

    @property
    def symbols(self):
        """The alphabet, in index order."""
        return list(self._symbols)

    def encode(self, text):
        """Encode text into packed bytes at the fixed width.

        Returns the raw byte payload. Padding bits in the last byte are
        always zero and carry no information.
        """
        if not isinstance(text, str):
            raise EntropyError("text must be a str")
        bits = []
        for ch in text:
            try:
                value = self._index[ch]
            except KeyError:
                raise SymbolNotFoundError(
                    "symbol not in alphabet: %r" % (ch,)
                ) from None
            for shift in range(self._width - 1, -1, -1):
                bits.append((value >> shift) & 1)
        return self._pack(bits)

    def decode(self, data, count):
        """Decode exactly count symbols from data.

        count must be the number of symbols originally encoded, because a
        fixed-width stream carries no way to tell real symbols apart from
        the zero padding of the last byte.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise EntropyError("data must be bytes")
        if count < 0:
            raise BitStreamError("count must not be negative")
        total_bits = len(data) * 8
        needed = count * self._width
        if needed > total_bits:
            raise BitStreamError("not enough bits to decode %d symbols" % count)
        chars = []
        pos = 0
        for _ in range(count):
            value = 0
            for _bit in range(self._width):
                byte = data[pos >> 3]
                bit = (byte >> (7 - (pos & 7))) & 1
                value = (value << 1) | bit
                pos += 1
            chars.append(self._symbols[value])
        return "".join(chars)

    @staticmethod
    def _pack(bits):
        if not bits:
            return b""
        out = bytearray()
        acc = 0
        filled = 0
        for bit in bits:
            acc = (acc << 1) | bit
            filled += 1
            if filled == 8:
                out.append(acc)
                acc = 0
                filled = 0
        if filled:
            out.append(acc << (8 - filled))
        return bytes(out)

    def __repr__(self):
        return "FixedWidth(symbols=%r, width=%d)" % (
            "".join(self._symbols),
            self._width,
        )
