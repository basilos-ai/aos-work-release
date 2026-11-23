"""Offline metadata write contract tests; never contact Library."""

import json
import copy
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import runtime
from library import cli
from library.metadata import OPERATIONS
from runtime import BasilError


class MetadataTests(unittest.TestCase):
    def run_operation(self, operation, value=None, include_value=True):
        body = {"operationType": operation, "fileId": "2097542604630659072",
                "fieldId": "2074577487546945536"}
        if include_value:
            body["value"] = value
        payload = {"operation": "file_metadata_operate", "body": body, "_confirm": True}
        with patch.object(cli, "read_json_stdin", return_value=payload), \
             patch.object(cli, "print_json"), \
             patch("runtime.openapi.request", return_value=(
                 '{"success": true, "code": 0, "data": 1}', "application/json"
             )) as request:
            try:
                cli.run_capability({"file_metadata_operate"})
            except BasilError:
                request.assert_not_called()
                raise
            return request.call_args

    def test_encoded_array_reaches_transport_unchanged(self):
        for operation in ("ADD", "UPDATE"):
            for values in (["nike"], ['品牌"A"', "路径\\B"]):
                with self.subTest(operation=operation, values=values):
                    value = json.dumps(values, ensure_ascii=False)
                    call = self.run_operation(operation, value)
                    self.assertEqual(call.args[:2], (
                        "POST", "/openapi/assets/file/metadata/operate"))
                    wire_body = json.loads(json.dumps(call.kwargs["body"]))
                    self.assertIsInstance(wire_body["value"], str)
                    self.assertEqual(wire_body["value"], value)
                    self.assertEqual(json.loads(wire_body["value"]), values)

    def test_invalid_values_are_rejected_before_transport(self):
        for operation in ("ADD", "UPDATE"):
            for value in ("nike", ["nike"], '"nike"', "{}", "null", "42", "[", None):
                with self.subTest(operation=operation, value=value):
                    with self.assertRaisesRegex(BasilError, "string containing a JSON array"):
                        self.run_operation(operation, value)
            with self.assertRaises(BasilError):
                self.run_operation(operation, include_value=False)

    def test_delete_does_not_require_or_validate_value(self):
        self.run_operation("DELETE", include_value=False)
        self.run_operation("DELETE", "ignored")


class MetadataCreateTests(unittest.TestCase):
    def payload(self):
        return {"operation": "metadata_field_create", "_confirm": True,
                "body": {"name": "色调", "description": "记录主色调",
                         "type": "SINGLE_SELECT",
                         "enumOptionList": [{"value": "深蓝色"},
                                            {"value": '品牌"A"', "description": "描述"}]}}

    def run_create(self, payload, raw=None, error=None):
        response = raw or '{"success":true,"code":0,"data":true,"addition":null}'
        with patch.object(cli, "read_json_stdin", return_value=payload), \
             patch.object(cli, "print_json") as output, \
             patch("runtime.openapi.request", return_value=(response, "application/json"),
                   side_effect=error) as request:
            try:
                cli.run_capability(OPERATIONS)
            except BasilError:
                if error or raw:
                    self.assertEqual(request.call_count, 1)
                else:
                    request.assert_not_called()
                output.assert_not_called()
                raise
            self.assertEqual(request.call_count, 1)
            return request.call_args, output.call_args.args[0]

    def test_create_defaults_route_and_boolean_result(self):
        call, result = self.run_create(self.payload())
        self.assertEqual(call.args, ("PUT", "/assets/metadata/field/save"))
        body = json.loads(json.dumps(call.kwargs["body"], ensure_ascii=False))
        self.assertEqual(body["planType"], "PRO")
        self.assertIsNone(body["groupId"])
        self.assertEqual(body["enumOptionList"][1]["value"], '品牌"A"')
        self.assertIs(result["data"], True)
        self.assertNotIn("id", result)

    def test_transport_allows_create_route(self):
        with patch.object(runtime, "service_api_base", return_value="https://example.test/typekey/api/v1"), \
             patch.object(runtime, "auth_headers", return_value={}), \
             patch.object(runtime, "_perform_request", return_value=("{}", "application/json")) as send:
            runtime.request("PUT", "/assets/metadata/field/save", body={"planType": "PRO"})
            self.assertEqual(send.call_args.args[1],
                             "https://example.test/typekey/api/v1/assets/metadata/field/save")
            send.assert_called_once()

    def test_create_rejects_data_false_or_missing_data(self):
        for raw in ('{"success":true,"code":0,"data":false}',
                    '{"success":true,"code":0,"data":null}',
                    '{"success":true,"code":0}'):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(BasilError, "data!=true"):
                    self.run_create(self.payload(), raw=raw)

    def test_data_false_exits_nonzero_with_a_structured_error(self):
        with patch.object(cli, "read_json_stdin", return_value=self.payload()), \
             patch("runtime.openapi.request", return_value=(
                 '{"success":true,"code":0,"data":false}', "application/json")), \
             patch.object(runtime.sys, "argv", ["metadata.py"]), \
             redirect_stdout(StringIO()) as output:
            code = runtime.run_script(lambda: cli.run_capability(OPERATIONS))
        self.assertEqual(code, 1)
        error = json.loads(output.getvalue())
        self.assertIs(error["success"], False)
        self.assertIn("data!=true", error["error"])
        self.assertIn("OpenAPI field page is LITE-only", error["next_action"]["action"])

    def test_pro_types_and_group_id_precision(self):
        for field_type in ("SINGLE_SELECT", "MULTI_SELECT", "NOT_ENUM", "NUMBER", "STRING", "TIME"):
            payload = self.payload()
            payload["body"].update(type=field_type, groupId="2097542604630659072", planType="PRO")
            del payload["body"]["enumOptionList"]
            call, _ = self.run_create(payload)
            self.assertEqual(call.kwargs["body"]["groupId"], "2097542604630659072")
            self.assertEqual(call.kwargs["body"]["type"], field_type)

    def test_lite_accepts_only_lite_types(self):
        for field_type in ("SINGLE_SELECT", "MULTI_SELECT", "NOT_ENUM"):
            payload = self.payload()
            payload["body"].update(type=field_type, planType="LITE")
            del payload["body"]["enumOptionList"]
            call, _ = self.run_create(payload)
            self.assertEqual(call.kwargs["body"]["planType"], "LITE")
        for field_type in ("NUMBER", "STRING", "TIME"):
            payload = self.payload()
            payload["body"].update(type=field_type, planType="LITE")
            with self.assertRaisesRegex(BasilError, "LITE fields support"):
                self.run_create(payload)

    def test_invalid_inputs_never_write(self):
        bad_bodies = [None, [], {},
                      {"name": " "}, {"description": ""}, {"type": "NUMBER"},
                      {"planType": "OTHER"}, {"planType": None},
                      {"groupId": " "}, {"groupId": 2097542604630659072},
                      {"groupId": True}, {"extra": 1},
                      {"enumOptionList": None}, {"enumOptionList": {}},
                      {"enumOptionList": [None]},
                      {"enumOptionList": [{"value": " "}]},
                      {"enumOptionList": [{"value": "蓝", "id": "123"}]},
                      {"enumOptionList": [{"value": "蓝", "description": 1}]},
                      {"enumOptionList": [{"value": "蓝"}, {"value": "蓝"}]},
                      {"type": "NOT_ENUM"}]
        for change in bad_bodies:
            with self.subTest(change=change):
                payload = self.payload()
                if isinstance(change, dict) and change:
                    payload["body"].update(change)
                else:
                    payload["body"] = change
                with self.assertRaises(BasilError):
                    self.run_create(payload)
        for key in ("name", "description", "type"):
            payload = self.payload()
            del payload["body"][key]
            with self.assertRaises(BasilError):
                self.run_create(payload)

    def test_confirmation_and_parameter_location(self):
        for change in ({"_confirm": False}, {"_confirm": "true"},
                       {"query": {"planType": "LITE"}}, {"path": {"id": "123"}}):
            payload = self.payload()
            payload.update(change)
            with self.assertRaises(BasilError):
                self.run_create(payload)
        payload = self.payload()
        del payload["_confirm"]
        with self.assertRaises(BasilError):
            self.run_create(payload)

    def test_failures_are_not_replayed_or_reported_as_success(self):
        for raw in ('{"success":false,"code":1,"message":"conflict"}', 'not JSON'):
            with self.assertRaises(BasilError):
                self.run_create(self.payload(), raw=raw)
        with self.assertRaises(BasilError):
            self.run_create(self.payload(), error=BasilError("timeout; result unknown"))

    def test_normalization_does_not_mutate_callers_body(self):
        payload = self.payload()
        original = copy.deepcopy(payload["body"])
        body = payload["body"]
        self.run_create(payload)
        self.assertEqual(body, original)


class MetadataNameResolutionTests(unittest.TestCase):
    def test_exact_name_resolves_id_and_never_guesses(self):
        for names in (["season"], ["season-other"], [], ["season", "season"]):
            fields = [{"id": str(2074577487546945536 + i), "name": name}
                      for i, name in enumerate(names)]
            payload = {"operation": "file_metadata_operate", "_confirm": True,
                       "body": {"operationType": "ADD", "fileId": "2097542604630659072",
                                "fieldName": "season", "value": '["summer"]'}}
            with self.subTest(names=names), \
                 patch.object(cli, "read_json_stdin", return_value=payload), \
                 patch.object(cli, "print_json"), \
                 patch("library.metadata_catalog.request", return_value=(json.dumps({
                     "success": True, "code": 0, "data": fields,
                     "addition": {"page": 1, "size": 1000, "total": len(fields)}
                 }), "application/json")) as lookup, \
                 patch("runtime.openapi.request", return_value=(
                     '{"success":true,"code":0,"data":"1"}', "application/json")) as write:
                if names == ["season"]:
                    cli.run_capability(OPERATIONS)
                    body = write.call_args.kwargs["body"]
                    self.assertEqual(body["fieldId"], "2074577487546945536")
                    self.assertNotIn("fieldName", body)
                    self.assertEqual(body["value"], '["summer"]')
                    write.assert_called_once()
                else:
                    with self.assertRaisesRegex(BasilError, "exactly one"):
                        cli.run_capability(OPERATIONS)
                    write.assert_not_called()
                lookup.assert_called_once()

    def test_missing_confirmation_blocks_lookup_and_write(self):
        payload = {"operation": "file_metadata_operate", "body": {
            "operationType": "ADD", "fileId": "123", "fieldName": "season", "value": '["summer"]'}}
        with patch.object(cli, "read_json_stdin", return_value=payload), \
             patch.object(cli, "fetch_metadata_catalog") as lookup, \
             patch("runtime.openapi.request") as write:
            with self.assertRaisesRegex(BasilError, "_confirm"):
                cli.run_capability(OPERATIONS)
            lookup.assert_not_called()
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
