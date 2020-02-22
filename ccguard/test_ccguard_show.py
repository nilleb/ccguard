from unittest.mock import MagicMock, patch
from pathlib import Path
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
    with patch.object(
        ccguard_show.ccguard, "adapter_factory", return_value=adapter_factory
    ):
        lines = []
        val = ccguard_show.main(
            args=[commit_id], log_function=lambda x: lines.append(x)
        )
        assert not val
        assert lines
        assert commit_id in lines[0]
        assert "79.10%" in lines[-1]
        p = Path("cc-dcba.html")
        assert p.is_file()
        p.unlink()
