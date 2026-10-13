import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(source, restored):
    source_root = Path(source).resolve()
    restored_root = Path(restored).resolve()
    source_files = {path.relative_to(source_root) for path in source_root.rglob("*") if path.is_file()}
    restored_files = {
        path.relative_to(restored_root) for path in restored_root.rglob("*") if path.is_file()
    }
    results = []

    for relative_path in sorted(source_files | restored_files):
        source_path = source_root / relative_path
        restored_path = restored_root / relative_path
        if relative_path not in source_files:
            status = "extra_in_restore"
            source_hash = None
            restored_hash = _sha256(restored_path)
        elif relative_path not in restored_files:
            status = "missing_in_restore"
            source_hash = _sha256(source_path)
            restored_hash = None
        else:
            source_hash = _sha256(source_path)
            restored_hash = _sha256(restored_path)
            status = "match" if source_hash == restored_hash else "hash_mismatch"
        results.append(
            {
                "path": relative_path.as_posix(),
                "status": status,
                "source_sha256": source_hash,
                "restored_sha256": restored_hash,
            }
        )

    return {
        "source_directory": str(source_root),
        "restored_directory": str(restored_root),
        "files_checked": len(results),
        "passed": all(item["status"] == "match" for item in results),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Compare source and restored file hashes.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--restored", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.source, args.restored)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()