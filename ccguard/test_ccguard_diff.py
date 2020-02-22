from unittest.mock import MagicMock, patch
from pathlib import Path
from . import ccguard_diff


def test_ccguard_diff():
    commit1 = "dcba"
    commit2 = "abcd"

    data = {
        commit1: b'<coverage line-rate="0.791" />',
        commit2: b'<coverage line-rate="0.821" />',
    }

    adapter = MagicMock()

    adapter.get_cc_commits = MagicMock(return_value=[commit1, commit2])
    adapter.retrieve_cc_data = MagicMock(side_effect=lambda commit: data[commit])
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)

    with patch.object(
        ccguard_diff.ccguard, "adapter_factory", return_value=adapter_factory
    ):
        lines = []
        val = ccguard_diff.main(
            args=[commit2, commit1], log_function=lambda x: lines.append(x)
        )
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
