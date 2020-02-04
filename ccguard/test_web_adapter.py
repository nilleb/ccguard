from unittest.mock import MagicMock
from . import ccguard


def test_web_adapter():
    adapter = ccguard.WebAdapter("rrr")
    requests_mock = MagicMock()
    data = "dump"
    requests_mock.get = MagicMock(return_value=MagicMock(json=data))
    ccguard.requests = requests_mock
    response = adapter.dump()
    assert requests_mock.get.called
    assert response == data
