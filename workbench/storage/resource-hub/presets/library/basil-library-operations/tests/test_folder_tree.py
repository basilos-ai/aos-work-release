"""Directory-tree wire contract; no remote API calls or mutations."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from library import folder_tree


class FolderTreeTests(unittest.TestCase):
    def test_markdown_attributes_preserved_for_new_and_legacy_inputs(self):
        responses = (
            '# Directory Tree\n\n'
            '- **Root/** — `folder_id=0` · `parent_folder_id=null` · `version=null` · `parentVersion=null`\n'
            '  - **Campaigns/** — `folder_id=1001` · `parent_folder_id=0` · `version=3` · `parentVersion=0`\n',
            # A subtree root's parent ID is trimmed, not its actual parent version.
            '# Directory Tree\n\n'
            '- **项目\\*/** — `folder_id=2089982124722622490` · `parent_folder_id=null` · `version=7` · `parentVersion=2`\n',
            # Old servers remain browsable; missing versions cannot authorize writes.
            '# Directory Tree\n\n- **10/** — `folder_id=2089982124722622490` · `parent_folder_id=null`\n',
        )
        for raw in responses:
            for payload in (
                {'operation': 'folder_tree', 'query': {'spaceType': 'MY'}},
                {'spaceType': 'MY'},
            ):
                with self.subTest(raw=raw, payload=payload):
                    output = StringIO()
                    with patch.object(folder_tree, 'read_json_stdin', return_value=payload), \
                            patch('runtime.openapi.request', return_value=(raw, 'text/markdown;charset=UTF-8')) as network, \
                            redirect_stdout(output):
                        folder_tree.main()
                    self.assertEqual(output.getvalue(), raw)
                    network.assert_called_once_with(
                        'GET', '/openapi/assets/folder/tree',
                        query={'spaceType': 'MY'}, body=None, timeout=30.0,
                    )


if __name__ == '__main__':
    unittest.main()
