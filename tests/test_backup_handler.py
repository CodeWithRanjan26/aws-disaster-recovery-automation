import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambda" / "backup"))
import app


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self, **kwargs):
        return iter(self.pages)


class FakeSourceS3:
    def __init__(self, pages):
        self.paginator = FakePaginator(pages)

    def get_paginator(self, operation):
        if operation != "list_objects_v2":
            raise AssertionError(operation)
        return self.paginator


class FakeDestinationS3:
    def __init__(self, sizes=None, failed_keys=()):
        self.sizes = sizes or {}
        self.failed_keys = set(failed_keys)
        self.copies = []

    def copy(self, source, bucket, key, ExtraArgs):
        if source["Key"] in self.failed_keys:
            raise RuntimeError("simulated copy failure")
        self.copies.append((source, bucket, key, ExtraArgs))

    def head_object(self, Bucket, Key):
        source_key = Key.split("/", 2)[-1]
        return {"ContentLength": self.sizes[source_key]}


class BackupHandlerTests(unittest.TestCase):
    def invoke(self, pages, destination, request_id="request-123"):
        source = FakeSourceS3(pages)
        clients = {"us-east-1": source, "us-west-2": destination}

        def get_client(service_name, region_name=None):
            return clients[region_name]

        environment = {
            "SOURCE_BUCKET": "source-test",
            "DESTINATION_BUCKET": "destination-test",
            "SOURCE_REGION": "us-east-1",
            "DESTINATION_REGION": "us-west-2",
        }
        with patch.dict(os.environ, environment, clear=False):
            with patch.object(app.boto3, "client", side_effect=get_client):
                return app.handler({}, SimpleNamespace(aws_request_id=request_id)), destination

    def test_copies_paginated_objects_to_a_run_specific_prefix(self):
        pages = [
            {"Contents": [{"Key": "reports/a.csv", "Size": 12}]},
            {"Contents": [{"Key": "logs/b.json", "Size": 34}]},
        ]
        destination = FakeDestinationS3(
            {"reports/a.csv": 12, "logs/b.json": 34}
        )

        result, destination = self.invoke(pages, destination)

        self.assertEqual(result["objects_seen"], 2)
        self.assertEqual(result["objects_copied"], 2)
        self.assertEqual(result["objects_failed"], 0)
        self.assertEqual(len(destination.copies), 2)
        self.assertTrue(
            all(copy[2].startswith(f"recovery/{result['run_id']}/") for copy in destination.copies)
        )

    def test_empty_bucket_is_a_successful_backup(self):
        result, destination = self.invoke([{}], FakeDestinationS3())

        self.assertEqual(result["objects_seen"], 0)
        self.assertEqual(result["objects_copied"], 0)
        self.assertEqual(destination.copies, [])

    def test_partial_copy_failure_fails_the_invocation_after_other_copies(self):
        pages = [
            {
                "Contents": [
                    {"Key": "good.txt", "Size": 5},
                    {"Key": "bad.txt", "Size": 7},
                ]
            }
        ]
        destination = FakeDestinationS3({"good.txt": 5}, failed_keys={"bad.txt"})

        with self.assertRaisesRegex(RuntimeError, "1 failed object"):
            self.invoke(pages, destination)

        self.assertEqual(len(destination.copies), 1)

    def test_size_mismatch_is_reported_as_a_failed_copy(self):
        pages = [{"Contents": [{"Key": "report.csv", "Size": 12}]}]
        destination = FakeDestinationS3({"report.csv": 10})

        with self.assertRaisesRegex(RuntimeError, "1 failed object"):
            self.invoke(pages, destination)


if __name__ == "__main__":
    unittest.main()