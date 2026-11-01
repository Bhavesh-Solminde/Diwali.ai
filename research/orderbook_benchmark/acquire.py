"""Fetch a pinned subset of TLOB source/checkpoints, verifying Git blob hashes."""
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path("data/orderbook_benchmark")
REVISION = "f1c0af4d81067978914361766db0457a7d8b6a46"


def main():
    tree_path = ROOT / "sources/tlob-tree.json"
    if tree_path.exists():
        tree = json.loads(tree_path.read_text())
    elif Path("/tmp/tlob-tree.json").exists():
        tree = json.loads(Path("/tmp/tlob-tree.json").read_text())
    else:
        url = f"https://api.github.com/repos/LeonardoBerti00/TLOB/git/trees/{REVISION}?recursive=1"
        with urllib.request.urlopen(url, timeout=60) as response:
            tree = json.load(response)
    if tree["sha"] != REVISION:
        raise ValueError("Unexpected source revision")
    tree_path.parent.mkdir(parents=True, exist_ok=True)
    tree_path.write_text(json.dumps(tree, indent=2))
    paths = ["models/tlob.py", "models/bin.py", "models/mlplob.py", "models/deeplob.py", "constants.py",
             "utils/utils_data.py", "models/engine.py", "preprocessing/btc.py", "README.md", "LICENSE"]
    paths += [x["path"] for x in tree["tree"] if x["path"].endswith(".pt")
              and any(f"/{name}/BTC_seq_size_" in x["path"] for name in ("TLOB", "DEEPLOB"))
              and "horizon_100_" in x["path"]]
    records = []
    for path in paths:
        meta = next(x for x in tree["tree"] if x["path"] == path)
        url = f"https://raw.githubusercontent.com/LeonardoBerti00/TLOB/{REVISION}/" + urllib.parse.quote(path)
        dest = ROOT / "sources/TLOB-pinned" / path
        if dest.exists():
            content = dest.read_bytes()
        else:
            with urllib.request.urlopen(url, timeout=60) as response:
                content = response.read()
        blob = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
        if blob != meta["sha"]:
            raise ValueError(f"Git blob mismatch: {path}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        records.append({"path": path, "url": url, "git_blob_sha1": blob,
                        "sha256": hashlib.sha256(content).hexdigest()})
        print(f"Verified {path}", flush=True)
    (ROOT / "sources/tlob-manifest.json").write_text(json.dumps({"revision": REVISION, "files": records}, indent=2))


if __name__ == "__main__":
    main()
