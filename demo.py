"""End to end demo of the sealstore batch digest.

Run with: python3 demo.py
"""

import os
import tempfile

from sealstore import SealStore, empty_digest, record_digest
from sealstore import journal


def sample_records():
    return [
        {"id": 1, "kind": "payment", "amount": 12.5, "currency": "CNY"},
        {"id": 2, "kind": "refund", "amount": 3, "currency": "CNY", "note": "逾期退回"},
        {"id": 3, "kind": "payment", "amount": 88, "currency": "USD"},
    ]


def main():
    store = SealStore()
    for record in sample_records():
        digest = store.append(record)
        print("appended id=%s digest=%s..." % (record["id"], digest[:16]))

    print()
    print("store stats:", store.stats())
    print("record digest stable:", record_digest(sample_records()[0]) == record_digest(sample_records()[0]))
    print("empty store digest:", empty_digest())

    with tempfile.TemporaryDirectory(prefix="sealstore-demo-") as tmp:
        path = os.path.join(tmp, "batch.jsonl")
        lines = journal.save(store, path)
        print()
        print("journal written:", lines, "lines")
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                print("  " + line.rstrip())

        rebuilt = journal.load(path)
        print()
        print("reloaded records:", len(rebuilt))
        print("digest matches original:", rebuilt.digest() == store.digest())
        print("claimed digest:", journal.verify(path)[:16] + "...")

        # ---- extension demo slot ----
        # Hook new per-record proof capabilities in here once they land.


if __name__ == "__main__":
    main()
