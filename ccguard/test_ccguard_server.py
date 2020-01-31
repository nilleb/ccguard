import ccguard_server
from unittest.mock import MagicMock, patch


def test_put_reference():
    repository_id = "abcd"
    commit_id = "dcba"
    data = "<coverage/>"
    adapter = MagicMock()
    adapter.persist = MagicMock(return_value=None)
    adapter_class = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(
        ccguard_server.ccguard, "adapter_factory", return_value=adapter_factory
    ) as mock_method:
        with ccguard_server.app.test_client() as test_client:
            result = test_client.put(
                "/api/v1/references/{}/{}/data".format(repository_id, commit_id),
                data=data,
            )
            assert result.status_code == 200
            assert result.data.decode("utf-8") == "OK"
