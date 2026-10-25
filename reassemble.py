"""Join published parts and check every file against MANIFEST.json."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        if "parts" in item:
            data = b"".join((ROOT / part).read_bytes() for part in item["parts"])
            target = ROOT / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        else:
            data = (ROOT / item["path"]).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != item["sha256"] or len(data) != item["bytes"]:
            raise SystemExit("mismatch " + item["path"])
    print("verified", len(manifest["files"]))


if __name__ == "__main__":
    main()
