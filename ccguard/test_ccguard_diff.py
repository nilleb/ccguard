from pathlib import Path
from unittest.mock import MagicMock, patch

from . import ccguard_diff


def test_ccguard_diff():
    commit1 = "dcba"
    commit2 = "abcd"

    data = {
        commit1: b'<coverage line-rate="0.791" />',
        commit2: b'<coverage line-rate="0.821" />',
    }

    adapter = MagicMock()

    adapter.get_cc_commits = MagicMock(return_value=[commit1, "aaaa", commit2, "bbbb"])
    adapter.retrieve_cc_data = MagicMock(side_effect=lambda commit: data[commit])
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)

    def get_output(a, b):
        return a.split()[-1] + "\n"

    lines = []

    def log_function(x):
        lines.append(x)

    ccm = ccguard_diff.ccguard

    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with patch.object(ccm, "get_output", side_effect=get_output):
            args = [commit2, commit1]
            val = ccguard_diff.main(args=args, log_function=log_function)
            assert not val
            assert lines
            assert commit1 in lines[0]
            assert commit2 in lines[0]
            assert "-3.00%" in lines[-1]
            p = Path("diff-abcd-dcba.html")
            assert p.is_file()
            p.unlink()


def test_ccguard_diff_not_enough_arguments():
    lines = []
    val = ccguard_diff.main(args=[], log_function=lambda x: lines.append(x))
    assert val
    assert "fatal: insufficient arguments" in lines
