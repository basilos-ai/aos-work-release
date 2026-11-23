"""Batch field-key selection must be explicit and consistent before transport."""

import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from base.cli import run_capability
from runtime import BasilError


TABLE_ID = "2066348680000180224"
FIELD_ID = "2066348765152940032"


def payload():
    return {
        "operation": "record_batch_create",
        "_confirm": True,
        "body": {
            "tableId": TABLE_ID,
            "fieldKeyType": "ID",
            "records": [{"fields": {FIELD_ID: "First value"}}],
        },
    }


class RecordBatchCreateTests(unittest.TestCase):
    def invoke(self, source):
        with patch("base.cli.read_json_stdin", return_value=source), \
                patch.object(sys, "argv", ["records.py"]), \
                patch("base.cli.print_json"):
            run_capability({"record_batch_create", "record_create"})

    def assert_rejected(self, source, message):
        with patch("runtime.openapi.request") as network:
            with self.assertRaisesRegex(BasilError, message) as caught:
                self.invoke(source)
        network.assert_not_called()
        return str(caught.exception)

    def test_each_key_type_is_sent_at_body_level_without_changing_field_keys(self):
        for key_type, key in [("ID", FIELD_ID), ("NAME", "Title"),
                              ("DB_FIELD_NAME", "field" + FIELD_ID)]:
            with self.subTest(key_type=key_type):
                source = payload()
                source["body"]["fieldKeyType"] = key_type
                source["body"]["records"] = [{"fields": {key: "First value"}},
                                              {"fields": {key: "Second value"}}]
                before = copy.deepcopy(source)
                with patch("runtime.openapi.request", return_value=(
                    json.dumps({"success": True, "code": 0, "data": {}}), "application/json"
                )) as network:
                    self.invoke(source)
                network.assert_called_once()
                self.assertEqual(network.call_args.args,
                                 ("POST", "/openapi/record/batchSaveRecordList"))
                self.assertEqual(network.call_args.kwargs["body"],
                                 {**before["body"], "tableId": int(TABLE_ID)})
                self.assertEqual(source, before)

    def test_record_only_setting_is_rejected_even_on_later_record(self):
        for key_type in ["ID", "NAME", "DB_FIELD_NAME"]:
            with self.subTest(key_type=key_type):
                source = payload()
                del source["body"]["fieldKeyType"]
                source["body"]["records"].append({"fieldKeyType": key_type, "fields": {}})
                error = self.assert_rejected(source, r"body\.records\[1\]\.fieldKeyType")
                self.assertIn("alongside body.tableId and body.records", error)
                self.assertIn('body.fieldKeyType="ID"', error)

    def test_missing_batch_setting_is_rejected_for_name_and_id_keys(self):
        for key in [FIELD_ID, "Title"]:
            source = payload()
            del source["body"]["fieldKeyType"]
            source["body"]["records"] = [{"fields": {key: "value"}}]
            self.assert_rejected(source, r"body\.fieldKeyType is required")

    def test_cli_root_and_query_do_not_replace_body_setting(self):
        for misplaced in [{"fieldKeyType": "ID"}, {"query": {"fieldKeyType": "ID"}}]:
            source = payload()
            del source["body"]["fieldKeyType"]
            source.update(misplaced)
            self.assert_rejected(source, r"body\.fieldKeyType is required")

    def test_conflicts_are_rejected_for_all_batch_types_and_later_records(self):
        for key_type in ["ID", "NAME", "DB_FIELD_NAME"]:
            for nested in ["ID", "NAME", "DB_FIELD_NAME", None, [], {}]:
                if nested == key_type:
                    continue
                with self.subTest(key_type=key_type, nested=nested):
                    source = payload()
                    source["body"]["fieldKeyType"] = key_type
                    source["body"]["records"].append({"fieldKeyType": nested, "fields": {}})
                    self.assert_rejected(source, r"body\.records\[1\]\.fieldKeyType conflicts")

    def test_identical_nested_setting_is_accepted(self):
        source = payload()
        source["body"]["records"][0]["fieldKeyType"] = "ID"
        with patch("runtime.openapi.request", return_value=(
            json.dumps({"success": True, "code": 0, "data": {}}), "application/json"
        )) as network:
            self.invoke(source)
        network.assert_called_once()
        self.assertEqual(network.call_args.kwargs["body"]["fieldKeyType"], "ID")

    def test_invalid_batch_enum_is_rejected_without_type_errors(self):
        for value in [None, "", "id", "UNKNOWN", [], {}, True, 1]:
            with self.subTest(value=value):
                source = payload()
                source["body"]["fieldKeyType"] = value
                self.assert_rejected(source, r"body\.fieldKeyType")

    def test_invalid_records_structure_cannot_bypass_validation(self):
        for records in [None, [], {}, "records", {"fieldKeyType": "ID"}, [None], ["record"]]:
            with self.subTest(records=records):
                source = payload()
                source["body"]["records"] = records
                self.assert_rejected(source, r"body\.records")

    def test_single_create_keeps_optional_field_key_type(self):
        source = payload()
        source["operation"] = "record_create"
        source["body"] = {"tableId": TABLE_ID, "fields": {"Title": "value"}}
        with patch("runtime.openapi.request", return_value=(
            json.dumps({"success": True, "code": 0, "data": {}}), "application/json"
        )) as network:
            self.invoke(source)
        network.assert_called_once()
        self.assertNotIn("fieldKeyType", network.call_args.kwargs["body"])


if __name__ == "__main__":
    unittest.main()
