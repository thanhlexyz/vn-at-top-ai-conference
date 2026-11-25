"""Installs the AI-text detector (MELD v8, MIT licence) outside the repository, pinned and checksum verified.

The weights are about 4 GB: they go to $VN_AI_MODEL_DIR (default ~/.cache/vn-ai-ranking/models/meld-v8), never into
the working tree. The script refuses a target inside the repository.

    python3 fetch_detector_model.py
"""
import hashlib
import json
import os
from datetime import datetime, timezone

from common import BACKEND, DETECTOR_ID, DETECTOR_REVISION, detector_dir

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
from huggingface_hub import HfApi, snapshot_download  # noqa: E402


def main():
    target = detector_dir().resolve()
    if BACKEND.parent in target.parents:
        raise SystemExit(f"{target} is inside the repository: set VN_AI_MODEL_DIR to a folder outside it")
    snapshot_download(DETECTOR_ID, revision=DETECTOR_REVISION, local_dir=target, max_workers=3)
    info = HfApi().model_info(DETECTOR_ID, revision=DETECTOR_REVISION, files_metadata=True)
    files = {}
    for entry in info.siblings:
        path = target / entry.rfilename
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                sha.update(chunk)
        digest = sha.hexdigest()
        if entry.lfs and digest != entry.lfs.sha256:
            raise SystemExit(f"Checksum mismatch: {entry.rfilename}")
        files[entry.rfilename] = {"bytes": path.stat().st_size, "sha256": digest}
    manifest = {"repo_id": DETECTOR_ID, "revision": DETECTOR_REVISION, "files": files, "license": "MIT",
                "downloaded_at": datetime.now(timezone.utc).isoformat()}
    (target / "download-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"model": DETECTOR_ID, "revision": DETECTOR_REVISION, "dir": str(target),
                      "verified_bytes": sum(f["bytes"] for f in files.values())}))


if __name__ == "__main__":
    main()
