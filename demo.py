"""End to end demo of the sealstore batch digest.

Run with: python3 demo.py
"""

import os
import tempfile

from sealstore import SealStore, empty_digest, record_digest
from sealstore import journal
from sealstore import (
    MerkleTree,
    proof_from_bytes,
    verify_consistency,
    verify_inclusion,
)


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
        # Per-record proofs: build the same batch as a Merkle tree.
        tree = MerkleTree(sample_records())
        print()
        print("merkle root:", tree.root()[:16] + "...")

        proof = tree.inclusion_proof(1)
        print(
            "inclusion proof for id=2: %d hashes, verifies %s"
            % (len(proof.path), verify_inclusion(tree.root(), sample_records()[1], proof))
        )
        wrong = dict(sample_records()[1])
        wrong["amount"] = 9999
        print("tampered record verifies:", verify_inclusion(tree.root(), wrong, proof))

        reloaded = proof_from_bytes(proof.to_bytes())
        print("proof survives a bytes round trip:", reloaded == proof)

        old_root = MerkleTree(sample_records()[:2]).root()
        consistency = tree.consistency_proof(2)
        print(
            "consistency 2 -> %d records: %s"
            % (
                len(tree),
                verify_consistency(old_root, tree.root(), consistency),
            )
        )

        changed = list(sample_records())
        changed[0] = {"id": 1, "kind": "payment", "amount": 42.0, "currency": "CNY"}
        rebuilt = MerkleTree(changed)
        count = tree.update(0, changed[0])
        print(
            "single update recomputed %d nodes, root matches full rebuild: %s"
            % (count, tree.root() == rebuilt.root())
        )


if __name__ == "__main__":
    main()
