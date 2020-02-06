import json
from . import ccguard_server
from unittest.mock import MagicMock, patch


def test_put_reference():
    repository_id = "abcd"
    commit_id = "dcba"
    data = "<coverage/>"
    adapter = MagicMock()
    adapter.persist = MagicMock(return_value=None)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(
        ccguard_server.ccguard, "adapter_factory", return_value=adapter_factory
    ):
        with ccguard_server.app.test_client() as test_client:
            result = test_client.put(
                "/api/v1/references/{}/{}/data".format(repository_id, commit_id),
                data=data,
            )
            assert result.status_code == 200
            assert "received" in result.data.decode("utf-8")
            assert adapter.persist.called


def test_dump():
    repository_id = "abcd"
    commit_id = "dcba"
    data = "<coverage/>"
    underlying = MagicMock()
    underlying.persist = MagicMock(return_value=None)
    underlying.dump = MagicMock(return_value=[(commit_id, data)])
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=underlying)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(
        ccguard_server.ccguard, "adapter_factory", return_value=adapter_factory
    ):
        with ccguard_server.app.test_client() as test_client:
            result = test_client.put(
                "/api/v1/references/{}/{}/data".format(repository_id, commit_id),
                data=data,
            )
            result = test_client.get(
                "/api/v1/references/{}/data".format(repository_id),
            )
            recvd_data = json.loads(result.data)
            assert len(recvd_data) == 1
            cid, dt = recvd_data[0]
            assert cid == commit_id
            assert dt == dt


def text_parse_args():
    args = ccguard_server.parse_args(
        ["--adapter", "web", "--port", "1234", "--token", "aaaa"]
    )
    assert args.token == "aaaa"
    assert args.port == 1234
    assert args.adapter == "web"


def test_main():
    app = MagicMock()
    app.run = MagicMock()
    ccguard_server.main([], app=app)
    app.run.assert_called_once()
