import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import runtime
from admin_console import cli
from admin_console.contracts import OPERATIONS, endpoint_allowed

OK = json.dumps({"success": True, "code": 0, "data": True, "addition": None})
AUTH = {"APP_OAUTH_BASILOS_ACCESS_TOKEN": "test-oauth-token"}


class OperationsTests(unittest.TestCase):
    def setUp(self):
        runtime.RUNTIME_DOMAIN = "https://example.invalid"
        runtime.AUTH_MODE = "auto"
        self.env = patch.dict(os.environ, AUTH, clear=True)
        self.env.start()
        self.transport = patch.object(runtime, "_perform_request", return_value=(OK, "application/json"))
        self.wire = self.transport.start()

    def tearDown(self):
        self.transport.stop()
        self.env.stop()

    def call(self, name, **kwargs):
        return cli.execute({"operation": name, **kwargs})

    def reject(self, name, **kwargs):
        with self.assertRaises(runtime.BasilError):
            self.call(name, **kwargs)
        self.wire.assert_not_called()

    def test_large_id_and_query_mutation(self):
        self.call("user_status", query={"userId": "9223372036854775807123", "userStatus": "DISABLE"}, _confirm=True, _target="selected account")
        args, kwargs = self.wire.call_args
        self.assertEqual(args[:2], ("PUT", "https://example.invalid/typekey/api/v1/system/updateStatus?userId=9223372036854775807123&userStatus=DISABLE"))
        self.assertIsNone(kwargs["payload"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-oauth-token")
        self.assertNotIn("auth-token", kwargs["headers"])

    def test_boolean_and_repeated_query_encoding(self):
        self.call("department_tree", query={"withUser": False})
        self.assertTrue(self.wire.call_args.args[1].endswith("withUser=false"))
        self.call("folder_page", query={"folderId": "0", "page": 1, "size": 20, "fileTypeFilter": ["IMAGE", "DOC"]})
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.wire.call_args.args[1]).query)
        self.assertEqual(query["fileTypeFilter"], ["IMAGE", "DOC"])

    def test_top_level_batch_array_and_defaults_preserved(self):
        body = [{"nickname": "Demo", "username": "demo", "systemRoleIdList": ["0"]}]
        self.call("user_batch_create", body=body, _confirm=True)
        self.assertEqual(json.loads(self.wire.call_args.kwargs["payload"]), body)

    def test_wrong_batch_shape_rejected(self):
        self.reject("user_batch_create", body={"users": []}, _confirm=True)

    def test_batch_nonroot_departments_not_silently_ignored(self):
        self.reject("user_batch_create", body=[{"nickname": "Demo", "username": "demo", "departmentIdList": ["12"]}], _confirm=True)

    def test_user_partial_update_blocked_before_network(self):
        self.reject("user_update", body={"id": "1", "systemRoleIdList": ["2"]}, _confirm=True)

    def test_user_complete_update_preserves_null_and_arrays(self):
        body = {"id": "1", "username": "demo", "nickname": "Demo", "jobTitle": None, "leaderId": None, "email": None, "departmentIdList": ["3"], "systemRoleIdList": ["2", "4"]}
        self.call("user_update", body=body, _confirm=True)
        self.assertEqual(json.loads(self.wire.call_args.kwargs["payload"]), body)

    def test_role_omitted_permissions_blocked(self):
        self.reject("system_role_update", body={"id": "1", "name": "Demo", "description": "Test"}, _confirm=True)

    def test_role_explicit_empty_permissions_sent(self):
        body = {"id": "1", "name": "Demo", "description": "Test", "permissionList": []}
        self.call("system_role_update", body=body, _confirm=True)
        self.assertEqual(json.loads(self.wire.call_args.kwargs["payload"])["permissionList"], [])

    def test_menu_permission_rejects_user_level_ids(self):
        self.reject("system_role_create", body={"name": "Demo", "description": "Test", "permissionList": ["114001"]}, _confirm=True)

    def test_acl_requires_complete_update(self):
        self.reject("acl_update", body={"id": "8", "name": "Demo", "description": "Test", "systemRoleIdList": ["2"]}, _confirm=True)

    def test_acl_none_and_inherit_remain_distinct(self):
        for preset in ("NONE", "INHERIT"):
            body = {"id": "8", "name": "Demo", "description": "Test", "systemRoleIdList": [], "departmentIdList": ["3"], "ruleList": [{"folderId": "12", "presetType": preset}]}
            self.call("acl_update", body=body, _confirm=True)
            self.assertEqual(json.loads(self.wire.call_args.kwargs["payload"]), body)

    def test_acl_invalid_nested_rule_rejected(self):
        self.reject("acl_create", body={"name": "Demo", "description": "Test", "systemRoleIdList": ["2"], "ruleList": [{"presetType": "VIEW"}]}, _confirm=True)

    def test_acl_unknown_action_rejected(self):
        self.reject("acl_create", body={"name": "Demo", "description": "Test", "systemRoleIdList": ["2"], "ruleList": [{"folderId": "0", "presetType": "CUSTOM", "permissionIdList": ["134000"]}]}, _confirm=True)

    def test_direct_share_requires_one_subject(self):
        self.reject("share_create", body={"targetId": "1", "targetType": "FILE", "presetType": "VIEW", "userId": "2", "departmentId": "3"}, _confirm=True)

    def test_direct_share_cannot_grant_manage(self):
        self.reject("share_create", body={"targetId": "1", "targetType": "FILE", "presetType": "MANAGE", "userId": "2"}, _confirm=True)

    def test_share_delete_is_json_body_with_exact_version(self):
        body = {"targetId": "1", "targetType": "FILE", "grantId": "2", "version": 7}
        self.call("share_delete", body=body, _confirm=True, _target="selected grant")
        self.assertEqual(self.wire.call_args.args[0], "DELETE")
        self.assertEqual(json.loads(self.wire.call_args.kwargs["payload"]), body)

    def test_missing_confirmation_and_target_rejected(self):
        self.reject("department_delete", path={"id": "7"})
        self.reject("department_delete", path={"id": "7"}, _confirm=True)

    def test_root_and_self_move_blocked(self):
        self.reject("department_delete", path={"id": "0"}, _confirm=True, _target="root")
        self.reject("department_update", body={"id": "3", "parentId": "3"}, _confirm=True)

    def test_query_body_confusion_rejected(self):
        self.reject("user_status", body={"userId": "1", "userStatus": "DISABLE"}, _confirm=True, _target="user")

    def test_numeric_and_injected_path_ids_rejected(self):
        self.reject("department_detail", path={"id": 9007199254740993})
        self.reject("department_detail", path={"id": "1/../tree"})

    def test_unknown_query_and_envelope_fields_rejected(self):
        self.reject("effective_permissions", query={"targetId": "1", "targetType": "FILE", "userId": "2"})
        self.reject("current_user", headers={"Authorization": "anything"})

    def test_oauth_incompatible_password_route_blocked(self):
        self.reject("password_update", query={"oldPassword": "placeholder", "newPassword": "placeholder"}, _confirm=True)
        self.assertFalse(endpoint_allowed("PUT", "/user/updatePassword"))

    def test_shared_and_desc_and_file_are_valid_despite_source_enum_excerpt(self):
        self.call("directory_children", query={"spaceType": "SHARED", "entryRootId": "5"})
        self.call("share_page", query={"page": 1, "size": 10, "sortDirection": "DESC", "targetType": "FILE", "targetId": "1"})

    def test_shared_requires_entry_root(self):
        self.reject("directory_children", query={"spaceType": "SHARED"})

    def test_folder_post_is_read_query_plus_unwrapped_filter(self):
        body = {"metadataLogicType": "AND", "metadataFilterList": [{"fieldId": "2", "operator": "EQUALS", "value": ["blue"]}]}
        self.call("folder_page_post", query={"folderId": "1", "page": 1, "size": 20}, body=body)
        self.assertEqual(self.wire.call_args.args[0], "POST")
        self.assertEqual(json.loads(self.wire.call_args.kwargs["payload"]), body)

    def test_multipart_upload_and_raw_url(self):
        self.wire.return_value = ("https://storage.invalid/icon.png", "text/plain")
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "icon.png"
            file.write_bytes(b"fixture image bytes")
            result = self.call("icon_upload", file_path=str(file), filename="chosen.png", _confirm=True)
        self.assertEqual(result["data"], "https://storage.invalid/icon.png")
        payload = self.wire.call_args.kwargs["payload"]
        self.assertIn(b'name="file"', payload)
        self.assertIn(b'name="filename"', payload)
        self.assertIn(b"chosen.png", payload)

    def test_sensitive_nested_entity_fields_removed(self):
        self.wire.return_value = (json.dumps({"success": True, "code": 0, "data": {"leader": {"id": "1", "password": "hash", "salt": "s", "tokenVersion": 4}}, "addition": {"total": 1}}), "application/json")
        result = self.call("user_page", query={"page": 1, "size": 20})
        self.assertEqual(result["data"]["leader"], {"id": "1"})
        self.assertEqual(result["addition"], {"total": 1})

    def test_reset_password_result_is_not_removed(self):
        self.wire.return_value = (json.dumps({"success": True, "code": 0, "data": {"resetPassword": "synthetic-result"}}), "application/json")
        self.assertEqual(self.call("user_reset_password", query={"userId": "1"}, _confirm=True, _target="Demo")["data"]["resetPassword"], "synthetic-result")

    def test_empty_and_null_results_are_preserved(self):
        for data in ([], None):
            self.wire.return_value = (json.dumps({"success": True, "code": 0, "data": data}), "application/json")
            self.assertEqual(self.call("department_detail", path={"id": "1"})["data"], data)

    def test_conflict_failure_has_details_and_no_retry(self):
        error = urllib.error.HTTPError("https://example.invalid", 400, "Conflict", {}, io.BytesIO(json.dumps({"success": False, "code": 4001, "errorKey": "version.conflict"}).encode()))
        self.wire.side_effect = error
        with self.assertRaises(runtime.BasilError) as caught:
            self.call("share_delete", body={"targetType": "FILE", "targetId": "1", "grantId": "2", "version": 7}, _confirm=True, _target="grant")
        self.assertEqual(caught.exception.details["errorKey"], "version.conflict")
        self.assertEqual(self.wire.call_count, 1)

    def test_timeout_does_not_replay_write(self):
        self.wire.side_effect = TimeoutError()
        with self.assertRaises(runtime.BasilError):
            self.call("department_create", body={"name": "Demo", "parentId": "0"}, _confirm=True)
        self.assertEqual(self.wire.call_count, 1)

    def test_401_never_switches_to_injected_personal_token(self):
        os.environ["APP_BASILOS_PERSONAL_TOKEN"] = "test-personal"
        self.wire.side_effect = urllib.error.HTTPError("https://example.invalid", 401, "Unauthorized", {}, io.BytesIO(b""))
        with self.assertRaises(runtime.BasilError):
            self.call("current_user")
        self.assertEqual(self.wire.call_count, 1)
        self.assertNotIn("auth-token", self.wire.call_args.kwargs["headers"])

    def test_explicit_personal_mode_uses_single_header(self):
        runtime.AUTH_MODE = "personal_token"
        os.environ["APP_BASILOS_PERSONAL_TOKEN"] = "test-personal"
        self.call("current_user")
        headers = self.wire.call_args.kwargs["headers"]
        self.assertEqual(headers["auth-token"], "test-personal")
        self.assertNotIn("Authorization", headers)

    def test_refresh_only_and_missing_domain_do_not_send(self):
        os.environ.pop("APP_OAUTH_BASILOS_ACCESS_TOKEN")
        os.environ["APP_OAUTH_BASILOS_REFRESH_TOKEN"] = "refresh-only"
        self.reject("current_user")
        runtime.RUNTIME_DOMAIN = None
        self.reject("current_user")

    def test_transport_allowlist_excludes_legacy_and_wrong_methods(self):
        for method, endpoint in [("DELETE", "/department/deleteUserDepartment/1"), ("GET", "/assets/folder/optional"), ("POST", "/department/1"), ("GET", "/department/1?bad=true")]:
            with self.assertRaises(runtime.BasilError):
                runtime.request(method, endpoint)
        self.wire.assert_not_called()

    def test_redirect_handler_refuses_forwarding(self):
        self.assertIsNone(runtime.NoRedirect().redirect_request(None, None, 302, "Redirect", {}, "https://other.invalid"))


class PackageTests(unittest.TestCase):
    def test_standalone_status_and_validation_without_parent_app(self):
        with tempfile.TemporaryDirectory() as temp:
            isolated = Path(temp) / "member"
            shutil.copytree(ROOT, isolated, ignore=shutil.ignore_patterns("__pycache__"))
            env = {"PATH": os.environ.get("PATH", ""), **AUTH, "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run([sys.executable, "scripts/auth/status.py"], cwd=isolated, input=json.dumps({"_runtimeDomain": "https://example.invalid"}), text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["configured"])
            self.assertNotIn("test-oauth-token", result.stdout)
            result = subprocess.run([sys.executable, "scripts/admin_console/cli.py"], cwd=isolated, input=json.dumps({"operation": "user_update", "body": {"id": "1"}}), text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["success"])
            self.assertNotIn("Traceback", result.stderr)



if __name__ == "__main__":
    unittest.main()
