import runpy
import unittest
from pathlib import Path


script = Path(__file__).resolve().parents[1] / "scripts" / "prepare-image-release.py"
update_image_row = runpy.run_path(str(script))["update_image_row"]


class ImageReleaseNotesTest(unittest.TestCase):
    def test_preserves_group_other_rows_and_formatting(self):
        for group in ("Workbench", "AOS Work"):
            with self.subTest(group=group):
                before = (
                    "Previous version: `v1.8.25`\r\n"
                    f"| {group} | `workbench-runtime-sandbox` | `v1.8.25` |\r\n"
                    f"| {group} | `workbench-runtime` |\t`v1.8.25`  |\r\n"
                )
                expected = before.replace("\t`v1.8.25`", "\t`v1.8.31`")
                self.assertEqual(update_image_row(before, "workbench-runtime", "v1.8.25", "v1.8.31"), expected)

    def test_rejects_missing_duplicate_and_stale_versions(self):
        row = "| AOS Work | `workbench-backend` | `v1.8.57` |"
        stale = row.replace("v1.8.57", "v1.8.55")
        for notes, error in (
            (row.replace("workbench-backend", "studio-backend"), "found 0"),
            (row + "\n" + row, "found 2"),
            (row + "\n" + stale, "found 2"),
            (stale, "expected v1.8.57"),
        ):
            with self.subTest(notes=notes), self.assertRaisesRegex(ValueError, error):
                update_image_row(notes, "workbench-backend", "v1.8.57", "v1.8.59")
