from unittest.mock import MagicMock, patch
from ccguard.web_adapter import WebAdapter
import ccguard


def test_web_adapter():
    adapter = WebAdapter("rrr")
    requests_mock = MagicMock()
    data = "dump"
    requests_mock.get = MagicMock(return_value=MagicMock(json=data))
    ccguard.web_adapter.requests = requests_mock
    response = adapter.dump()
    assert requests_mock.get.called
    assert response == data
