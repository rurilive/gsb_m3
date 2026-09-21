"""stampkit 演示：把一批报表采样点对齐到分钟桶，打印桶信息与相邻间隔。"""

from stampkit import (
    align_many,
    bucket_index,
    duration_between,
    floor_bucket,
    format_duration,
    pack_duration,
    to_millis,
    unpack_duration,
)

# 采样点原始时间戳，单位毫秒。
SAMPLES_MS = [
    1_700_000_000_123,
    1_700_000_002_450,
    1_700_000_061_000,
    1_700_000_120_999,
    1_700_000_181_500,
]

BUCKET_MS = 60_000


def main():
    buckets = align_many(SAMPLES_MS, BUCKET_MS, unit="ms")

    print("bucket size: %d ms" % BUCKET_MS)
    header = "%16s  %16s  %8s  %12s" % ("raw ms", "bucket ms", "index", "since prev")
    print(header)
    print("-" * len(header))

    previous = None
    for raw, bucket in zip(SAMPLES_MS, buckets):
        if previous is None:
            since_prev = "-"
        else:
            since_prev = format_duration(duration_between(previous, raw, "ms"))
        print("%16d  %16d  %8d  %12s" % (raw, bucket, bucket_index(raw, BUCKET_MS), since_prev))
        previous = raw

    total = duration_between(SAMPLES_MS[0], SAMPLES_MS[-1], "ms")
    blob = pack_duration(total)
    print()
    print("total span: %s" % format_duration(total))
    print("archive blob: %s -> %d ms" % (blob.hex(), unpack_duration(blob)))
    print("seconds source: %d -> %d ms" % (1_700_000_000, to_millis(1_700_000_000, unit="s")))
    print("floor of last sample: %d ms" % floor_bucket(SAMPLES_MS[-1], 15 * 60_000))


if __name__ == "__main__":
    main()
