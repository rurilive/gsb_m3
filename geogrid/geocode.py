"""Geohash 编解码与邻格。

标准 geohash：经纬度交替二分，5 比特一个字符，base32 字母表
"0123456789bcdefghjkmnpqrstuvwxyz"。编码前缀即低精度格子，所以按
精度截断再 decode 得到的范围一定包住原格子。经度先归一化，跨 180
度线的邻格接得上；纬度到极点后不再向外取邻格。
"""

from .errors import InvalidCoordinate
from .geo import check_lat, check_lon, normalize_lon

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
MAX_PRECISION = 24

_DECODE_MAP = {ch: idx for idx, ch in enumerate(BASE32)}


def check_precision(precision):
    """校验并返回整型精度（字符数）。"""
    if isinstance(precision, bool) or not isinstance(precision, int):
        raise ValueError("精度必须是整数，收到 %r" % (precision,))
    if precision < 1 or precision > MAX_PRECISION:
        raise ValueError("精度必须落在 1 到 %d 之间，收到 %r" % (MAX_PRECISION, precision))
    return precision


def encode(lat, lon, precision=12):
    """把点编成 precision 个字符的格子码。"""
    lat = check_lat(lat)
    lon = normalize_lon(check_lon(lon))
    precision = check_precision(precision)
    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    chars = []
    even = True
    while len(chars) < precision:
        value = 0
        for _ in range(5):
            value <<= 1
            if even:
                mid = (lon_lo + lon_hi) / 2.0
                if lon >= mid:
                    value |= 1
                    lon_lo = mid
                else:
                    lon_hi = mid
            else:
                mid = (lat_lo + lat_hi) / 2.0
                if lat >= mid:
                    value |= 1
                    lat_lo = mid
                else:
                    lat_hi = mid
            even = not even
        chars.append(BASE32[value])
    return "".join(chars)


def decode(code):
    """解出格子码覆盖的范围，返回 (lat_min, lat_max, lon_min, lon_max)。"""
    if not isinstance(code, str) or not code:
        raise InvalidCoordinate("格子码必须是非空字符串，收到 %r" % (code,))
    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    even = True
    for ch in code:
        if ch not in _DECODE_MAP:
            raise InvalidCoordinate("格子码含非法字符 %r" % (ch,))
        value = _DECODE_MAP[ch]
        for bit in range(4, -1, -1):
            if even:
                mid = (lon_lo + lon_hi) / 2.0
                if (value >> bit) & 1:
                    lon_lo = mid
                else:
                    lon_hi = mid
            else:
                mid = (lat_lo + lat_hi) / 2.0
                if (value >> bit) & 1:
                    lat_lo = mid
                else:
                    lat_hi = mid
            even = not even
    return (lat_lo, lat_hi, lon_lo, lon_hi)


def neighbors(code):
    """周边邻格，按 NW、N、NE、W、E、SW、S、SE 顺序返回同精度格子码。

    跨 180 度线时经度归一化接得上；极点外侧没有格子，返回不足 8 个。
    """
    lat_min, lat_max, lon_min, lon_max = decode(code)
    lat_step = lat_max - lat_min
    lon_step = lon_max - lon_min
    lat_center = (lat_min + lat_max) / 2.0
    lon_center = (lon_min + lon_max) / 2.0
    precision = len(code)
    found = []
    for dlat in (lat_step, 0.0, -lat_step):
        for dlon in (-lon_step, 0.0, lon_step):
            if dlat == 0.0 and dlon == 0.0:
                continue
            nlat = lat_center + dlat
            if nlat < -90.0 or nlat > 90.0:
                continue
            found.append(encode(nlat, lon_center + dlon, precision))
    return found
