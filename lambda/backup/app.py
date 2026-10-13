import json
import logging
import os
import re
from datetime import datetime, timezone

import boto3


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    source_bucket = os.environ["SOURCE_BUCKET"]
    destination_bucket = os.environ["DESTINATION_BUCKET"]
    source_region = os.environ["SOURCE_REGION"]
    destination_region = os.environ["DESTINATION_REGION"]
    backup_prefix = os.environ.get("BACKUP_PREFIX", "recovery").strip("/")

    source_s3 = boto3.client("s3", region_name=source_region)
    destination_s3 = boto3.client("s3", region_name=destination_region)
    run_id = _run_id(context.aws_request_id)
    result = {
        "run_id": run_id,
        "source_bucket": source_bucket,
        "destination_bucket": destination_bucket,
        "objects_seen": 0,
        "objects_copied": 0,
        "objects_failed": 0,
        "failure_samples": [],
    }

    paginator = source_s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=source_bucket):
        for item in page.get("Contents", []):
            result["objects_seen"] += 1
            source_key = item["Key"]
            destination_key = f"{backup_prefix}/{run_id}/{source_key}"
            try:
                destination_s3.copy(
                    {"Bucket": source_bucket, "Key": source_key},
                    destination_bucket,
                    destination_key,
                    ExtraArgs={"MetadataDirective": "COPY"},
                )
                copied = destination_s3.head_object(
                    Bucket=destination_bucket,
                    Key=destination_key,
                )
                if copied["ContentLength"] != item["Size"]:
                    raise ValueError("copied object size does not match source")
                result["objects_copied"] += 1
            except Exception as error:
                result["objects_failed"] += 1
                if len(result["failure_samples"]) < 20:
                    result["failure_samples"].append(
                        {"key": source_key, "error": str(error)[:500]}
                    )

    logger.info(json.dumps({"backup_result": result}, sort_keys=True))
    if result["objects_failed"]:
        raise RuntimeError(
            f"Backup {run_id} completed with {result['objects_failed']} failed object(s)"
        )
    return result


def _run_id(request_id):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_request_id = re.sub(r"[^A-Za-z0-9-]", "-", request_id)
    return f"{timestamp}-{safe_request_id}"