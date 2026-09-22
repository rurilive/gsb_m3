"""前缀式格子编码（类 geohash）。

点编成字符串码：每多一位字符，格子在经向或纬向上再对半细分一次，
所以截断编码就是降低精度，短码的格子完整包住长码的格子。
经度方向按环形处理，neighbors 跨过 ±180 度经线能接上；
纬度到极点到顶，不绕回。
"""

from typing import NamedTuple

from .errors import InvalidCoordinate
from .geo import check_lat, check_lon, normalize_lon

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
DEFAULT_PRECISION = 9
MAX_PRECISION = 32


class GeoCell(NamedTuple):
    """解码出的格子范围，单位度。"""

    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

    @property
    def center(self):
        """格子中心 (lat, lon)。"""
        return ((self.lat_min + self.lat_max) / 2.0, (self.lon_min + self.lon_max) / 2.0)

    def contains(self, lat, lon):
        """点是否落在格子闭区间里。"""
        return self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max


def _check_precision(precision):
    if isinstance(precision, bool) or not isinstance(precision, int):
        raise ValueError("精度必须是非负整数，收到 %r" % (precision,))
    if precision < 1 or precision > MAX_PRECISION:
        raise ValueError("精度必须落在 1 到 %d 之间，收到 %r" % (MAX_PRECISION, precision))
    return precision


def _check_code(code):
    if not isinstance(code, str) or not code:
        raise InvalidCoordinate("格子码必须是非空字符串，收到 %r" % (code,))
    if len(code) > MAX_PRECISION:
        raise InvalidCoordinate("格子码最长 %d 位，收到 %r" % (MAX_PRECISION, code))
    for ch in code:
        if ch not in BASE32:
            raise InvalidCoordinate("格子码含有非法字符 %r" % (ch,))
    return code


def _split_bits(precision):
    """该精度下纬向、经向各占多少比特；经向先编，不少于纬向。"""
    bits = precision * 5
    return bits // 2, (bits + 1) // 2


def _encode_indices(lat_idx, lon_idx, lat_bits, lon_bits):
    value = 0
    for level in range(lon_bits):
        value = (value << 1) | ((lon_idx >> (lon_bits - 1 - level)) & 1)
        if level < lat_bits:
            value = (value << 1) | ((lat_idx >> (lat_bits - 1 - level)) & 1)
    total = lat_bits + lon_bits
    return "".join(BASE32[(value >> (total - pos - 5)) & 31] for pos in range(0, total, 5))


def _decode_indices(code):
    lat_bits, lon_bits = _split_bits(len(code))
    lat_idx = 0
    lon_idx = 0
    take_lon = True
    for ch in code:
        val = BASE32.index(ch)
        for shift in (4, 3, 2, 1, 0):
            bit = (val >> shift) & 1
            if take_lon:
                lon_idx = (lon_idx << 1) | bit
            else:
                lat_idx = (lat_idx << 1) | bit
            take_lon = not take_lon
    return lat_idx, lon_idx, lat_bits, lon_bits


def encode(lat, lon, precision=DEFAULT_PRECISION):
    """把点编成 precision 位的格子码。"""
    precision = _check_precision(precision)
    lat = check_lat(lat)
    lon = normalize_lon(check_lon(lon))
    lat_bits, lon_bits = _split_bits(precision)
    lat_idx = min(int((lat + 90.0) / 180.0 * (1 << lat_bits)), (1 << lat_bits) - 1)
    lon_idx = min(int((lon + 180.0) / 360.0 * (1 << lon_bits)), (1 << lon_bits) - 1)
    return _encode_indices(lat_idx, lon_idx, lat_bits, lon_bits)


def decode(code):
    """把格子码解回 GeoCell；范围保证包住编进去的原点。"""
    code = _check_code(code)
    lat_idx, lon_idx, lat_bits, lon_bits = _decode_indices(code)
    lat_step = 180.0 / (1 << lat_bits)
    lon_step = 360.0 / (1 << lon_bits)
    return GeoCell(
        -90.0 + lat_idx * lat_step,
        -90.0 + (lat_idx + 1) * lat_step,
        -180.0 + lon_idx * lon_step,
        -180.0 + (lon_idx + 1) * lon_step,
    )


def neighbors(code):
    """同精度的周边 8 个邻格码；跨 ±180 度经线绕回，极点方向缺省。"""
    code = _check_code(code)
    lat_idx, lon_idx, lat_bits, lon_bits = _decode_indices(code)
    ring = []
    for dlat in (-1, 0, 1):
        for dlon in (-1, 0, 1):
            if dlat == 0 and dlon == 0:
                continue
            row = lat_idx + dlat
            if row < 0 or row >= (1 << lat_bits):
                continue
            col = (lon_idx + dlon) % (1 << lon_bits)
            ring.append(_encode_indices(row, col, lat_bits, lon_bits))
    return ring
