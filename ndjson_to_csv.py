from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

DROP_FIELDS = {"raw"}


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python ndjson_to_csv.py input.ndjson output.csv", file=sys.stderr)
        raise SystemExit(2)

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    rows = []
    fields = []

    with src.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            flat = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in row.items() if k not in DROP_FIELDS}
            rows.append(flat)
            for key in flat.keys():
                if key not in fields:
                    fields.append(key)

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} rows to {dst}")


if __name__ == "__main__":
    main()
