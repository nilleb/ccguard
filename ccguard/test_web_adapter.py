from unittest.mock import MagicMock
from . import ccguard


def test_web_adapter_retrieve_cc_data():
    adapter = ccguard.WebAdapter("repository")
    requests_mock = MagicMock()
    data = b"dump"
    requests_mock.get = MagicMock(return_value=MagicMock(content=data))
    ccguard.requests = requests_mock
    response = adapter.retrieve_cc_data("abc")
    assert requests_mock.get.called_with(
        "http://localhost:5000/api/v1/references/repository/abc/data"
    )
    assert response == data


def test_web_adapter_get_cc_commits():
    adapter = ccguard.WebAdapter("repository")
    requests_mock = MagicMock()
    requests_mock.get = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=["abc", "def"]))
    )
    ccguard.requests = requests_mock
    response = adapter.get_cc_commits()
    assert requests_mock.get.called_with(
        "http://localhost:5000/api/v1/references/repository/all"
    )
    assert len(response) == 2
