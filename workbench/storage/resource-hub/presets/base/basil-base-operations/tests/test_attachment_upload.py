"""Offline attachment upload workflow regressions."""

import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from base import cli, records
from runtime import BasilError


def response(data=None):
    return json.dumps({"success": True, "code": 0, "data": data if data is not None else {}}), "application/json"


class AttachmentUploadTests(unittest.TestCase):
    def test_uploads_chunks_and_returns_record_ready_attachment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.pdf"
            path.write_bytes(b"abcdef")

            def request(method, endpoint, **kwargs):
                if endpoint.endswith("/init"):
                    return response({
                        "token": "12345",
                        "path": "multi-dim-table/attachments/7/12345.pdf",
                        "uploadId": "upload-1",
                        "chunkSize": 4,
                        "totalChunks": 2,
                    })
                if "/chunk/" in endpoint:
                    return response()
                return response({
                    "token": "12345",
                    "path": "multi-dim-table/attachments/7/12345.pdf",
                    "size": "6",
                    "mimetype": "application/pdf",
                    "presignedUrl": "https://signed.example/report.pdf",
                    "uploadId": None,
                    "chunkSize": None,
                    "totalChunks": None,
                })

            with patch.object(cli, "request", side_effect=request) as network:
                result = cli._upload_attachment({
                    "operation": "record_attachment_upload",
                    "baseId": "7",
                    "file_path": str(path),
                    "_confirm": True,
                })

        self.assertEqual([call.args[1] for call in network.call_args_list], [
            "/record/uploadAttachment/init",
            "/record/uploadAttachment/12345/chunk/1",
            "/record/uploadAttachment/12345/chunk/2",
            "/record/uploadAttachment/12345/complete",
        ])
        self.assertIn(b"abcd", network.call_args_list[1].kwargs["raw_body"])
        self.assertIn(b"ef", network.call_args_list[2].kwargs["raw_body"])
        attachment = result["data"]
        self.assertEqual(attachment["name"], "report.pdf")
        self.assertRegex(attachment["id"], re.compile(r"^act[0-9A-Za-z]{16}$"))
        self.assertEqual(attachment["path"], "multi-dim-table/attachments/7/12345.pdf")
        self.assertEqual(attachment["size"], 6)
        self.assertNotIn("uploadId", attachment)
        self.assertNotIn("chunkSize", attachment)
        self.assertNotIn("totalChunks", attachment)

    def test_records_entrypoint_routes_attachment_upload(self):
        result = {"success": True, "code": 0, "data": {"id": "actFixture"}}
        with patch.object(sys, "argv", ["records.py"]), \
                patch.object(cli, "read_json_stdin", return_value={"operation": "record_attachment_upload"}), \
                patch.object(cli, "_upload_attachment", return_value=result) as upload, \
                patch.object(cli, "print_json") as output:
            cli.run_capability(records.OPERATIONS)
        upload.assert_called_once_with({"operation": "record_attachment_upload"})
        output.assert_called_once_with(result)

    def test_chunk_failure_aborts_without_completing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.txt"
            path.write_bytes(b"content")

            def request(method, endpoint, **kwargs):
                if endpoint.endswith("/init"):
                    return response({
                        "token": "67890",
                        "path": "multi-dim-table/attachments/9/67890.txt",
                        "uploadId": "upload-2",
                        "chunkSize": 4,
                        "totalChunks": 2,
                    })
                if "/chunk/" in endpoint:
                    raise BasilError("chunk failed")
                if method == "DELETE":
                    return response()
                self.fail("complete must not be called after a chunk failure")

            with patch.object(cli, "request", side_effect=request) as network:
                with self.assertRaisesRegex(BasilError, "chunk failed"):
                    cli._upload_attachment({
                        "operation": "record_attachment_upload",
                        "baseId": 9,
                        "file_path": str(path),
                        "_confirm": True,
                    })

        self.assertEqual([call.args[1] for call in network.call_args_list], [
            "/record/uploadAttachment/init",
            "/record/uploadAttachment/67890/chunk/1",
            "/record/uploadAttachment/67890",
        ])

    def test_invalid_local_inputs_fail_before_network(self):
        with patch.object(cli, "request") as network:
            with self.assertRaisesRegex(BasilError, "_confirm=true"):
                cli._upload_attachment({"operation": "record_attachment_upload", "baseId": 1, "file_path": "/missing"})
            with self.assertRaisesRegex(BasilError, "existing regular file"):
                cli._upload_attachment({
                    "operation": "record_attachment_upload",
                    "baseId": 1,
                    "file_path": "/missing",
                    "_confirm": True,
                })
        network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
