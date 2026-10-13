import argparse
import hashlib
import json
import time
from pathlib import Path, PurePosixPath

import boto3


def _safe_destination(root, object_key, object_prefix):
    relative_key = object_key[len(object_prefix) :]
    relative_path = PurePosixPath(relative_key)
    if not relative_key or relative_path.is_absolute():
        raise ValueError(f"Unsafe or empty object key: {object_key}")
    destination = (root / Path(*relative_path.parts)).resolve()
    if destination != root and root not in destination.parents:
        raise ValueError(f"Object key escapes restore directory: {object_key}")
    return destination


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def restore(bucket, prefix, destination, region, profile):
    object_prefix = prefix.rstrip("/") + "/"
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    session = boto3.Session(profile_name=profile)
    s3 = session.client("s3", region_name=region)
    started_at = time.perf_counter()
    restored = []

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=object_prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            target = _safe_destination(root, key, object_prefix)
            target.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(target))
            restored.append(
                {
                    "key": key,
                    "path": str(target),
                    "size_bytes": target.stat().st_size,
                    "sha256": _sha256(target),
                }
            )

    return {
        "bucket": bucket,
        "prefix": object_prefix,
        "destination": str(root),
        "objects_restored": len(restored),
        "elapsed_seconds": round(time.perf_counter() - started_at, 3),
        "files": restored,
    }


def main():
    parser = argparse.ArgumentParser(description="Restore one S3 recovery point locally.")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", required=True, help="Full recovery run prefix, e.g. recovery/<run-id>")
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile", default="dr-lab")
    args = parser.parse_args()
    result = restore(
        args.bucket,
        args.prefix,
        args.destination,
        args.region,
        args.profile,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()