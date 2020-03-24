from pathlib import Path
from unittest.mock import MagicMock, patch

from . import ccguard_show


def test_ccguard_show():
    commit_id = "dcba"
    data = b'<coverage line-rate="0.791" />'
    adapter = MagicMock()
    adapter.get_cc_commits = MagicMock(return_value=[commit_id])
    adapter.retrieve_cc_data = MagicMock(return_value=data)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)

    def get_output(a, b):
        return a.split()[-1] + "\n"

    lines = []

    def log_function(x):
        lines.append(x)

    ccm = ccguard_show.ccguard

    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with patch.object(ccm, "get_output", side_effect=get_output):
            val = ccguard_show.main(args=[commit_id], log_function=log_function)
            assert not val
            assert lines
            assert commit_id in lines[0]
            assert "79.10%" in lines[-1]
            p = Path("cc-dcba.html")
            assert p.is_file()
            p.unlink()
