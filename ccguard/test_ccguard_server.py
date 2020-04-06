import os
from unittest.mock import MagicMock, call, patch

from . import ccguard_server as csm
from .ccguard_server import ccguard as ccm


def test_home():
    with csm.app.test_client() as test_client:
        result = test_client.get("/")
        assert result.status_code == 200


def test_debug_repositories():
    config = {}
    adapter_class = MagicMock()
    adapter_class.list_repositories = MagicMock(return_value=frozenset(["abc"]))
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(csm, "SqliteServerAdapter", return_value=adapter_factory):
        with patch.object(ccm, "configuration", return_value=config):
            with csm.app.test_client() as test_client:
                result = test_client.get("/api/v1/repositories/debug")
                assert result.status_code == 200
                assert result.data
                assert adapter_class.list_repositories.called_with(config)


def test_choose_references():
    repository_id = "abcd"
    config = {}
    commits = ["a", "b", "c", "d"]
    data = "\n".join(commits)
    adapter = MagicMock()
    adapter.get_cc_commits = MagicMock(return_value=commits)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with patch.object(ccm, "configuration", return_value=config):
            with csm.app.test_client() as test_client:
                url = "/api/v1/references/{}/choose".format(repository_id)
                import logging

                logging.exception(url)
                result = test_client.post(url, data=data)
                assert result.status_code == 200
                assert result.data == b"a"
                assert adapter_factory.called_with(None, config)
                assert adapter.get_cc_commits.called


def test_choose_references_not_found():
    repository_id = "abcd"
    config = {}
    commits = []
    data = "\n".join(commits)
    adapter = MagicMock()
    adapter.get_cc_commits = MagicMock(return_value=commits)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with patch.object(ccm, "configuration", return_value=config):
            with csm.app.test_client() as test_client:
                url = "/api/v1/references/{}/choose".format(repository_id)
                result = test_client.post(url, data=data)
                assert result.status_code == 404
                assert adapter_factory.called_with(None, config)
                assert adapter.get_cc_commits.called


def test_compare_references():
    repository_id = "abcd"
    commit_id1 = "dcba"
    commit_id2 = "efgh"
    config = {}
    data = b"<coverage/>"
    adapter = MagicMock()
    adapter.retrieve_cc_data = MagicMock(return_value=data)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with patch.object(ccm, "configuration", return_value=config):
            with csm.app.test_client() as test_client:
                url = (
                    "/api/v1/references/{repository_id}/"
                    "{commit_id1}..{commit_id2}/comparison"
                ).format(**locals())
                result = test_client.get(url)
                assert result.status_code == 200
                assert result.data == b"0"
                assert adapter_factory.called_with(None, config)
                assert adapter.retrieve_cc_data.called


def test_compare_references_not_found():
    config = {}
    adapter = MagicMock()
    adapter.retrieve_cc_data = MagicMock(return_value=None)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with patch.object(ccm, "configuration", return_value=config):
            with csm.app.test_client() as test_client:
                url = (
                    "/api/v1/references/invalid/" "invalid..invalid/comparison"
                ).format(**locals())
                result = test_client.get(url)
                assert result.status_code == 404
                assert adapter_factory.called_with(None, config)
                assert adapter.retrieve_cc_data.called


def test_debug_download_reference():
    repository_id = "abcd"
    commit_id = "dcba"
    data = b"<coverage/>"
    adapter = MagicMock()
    adapter.retrieve_cc_data = MagicMock(return_value=data)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/api/v1/references/{}/{}/debug".format(repository_id, commit_id)
            result = test_client.get(url)
            assert result.status_code == 200
            assert result.json["commit_id"] == commit_id
            assert adapter.retrieve_cc_data.called_with(adapter, commit_id)


def test_debug_download_reference_commit_not_found():
    repository_id = "abcd"
    commit_id = "dcba"
    adapter = MagicMock()
    adapter.retrieve_cc_data = MagicMock(return_value=None)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/api/v1/references/{}/{}/debug".format(repository_id, commit_id)
            result = test_client.get(url)
            assert result.status_code == 200
            assert result.json["commit_id"] == commit_id
            assert result.json["data_len"] is None
            assert adapter.retrieve_cc_data.called_with(adapter, commit_id)


def test_download_reference():
    repository_id = "abcd"
    commit_id = "dcba"
    data = b"<coverage/>"
    adapter = MagicMock()
    adapter.retrieve_cc_data = MagicMock(return_value=data)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/api/v1/references/{}/{}/data".format(repository_id, commit_id)
            result = test_client.get(url)
            assert result.status_code == 200
            assert result.data == data
            assert adapter.retrieve_cc_data.called_with(adapter, commit_id)


def test_download_reference_commit_not_found():
    repository_id = "abcd"
    commit_id = "dcba"
    adapter = MagicMock()
    adapter.retrieve_cc_data = MagicMock(return_value=None)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/api/v1/references/{}/{}/data".format(repository_id, commit_id)
            result = test_client.get(url)
            assert result.status_code == 404
            assert adapter.retrieve_cc_data.called_with(adapter, commit_id)


def test_status_badge():
    repository_id = "abcd"
    commit_id = "dcba"
    adapter = MagicMock()
    commits = frozenset([commit_id])
    adapter = MagicMock()
    adapter.get_cc_commits = MagicMock(return_value=commits)
    adapter.get_commit_info = MagicMock(return_value=[0.17, 17, 100])
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/api/v1/repositories/{}/status_badge".format(repository_id)
            result = test_client.get(url)
            assert result.status_code == 200
            assert b"17%" in result.data
            assert adapter.get_commit_info.called_with(adapter, commit_id)


def test_status_badge_unknown():
    repository_id = "abcd"
    adapter = MagicMock()
    commits = frozenset([])
    adapter = MagicMock()
    adapter.get_cc_commits = MagicMock(return_value=commits)
    adapter.get_commit_info = MagicMock(return_value=[0.17, 17, 100])
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/api/v1/repositories/{}/status_badge".format(repository_id)
            result = test_client.get(url)
            assert result.status_code == 200
            assert b"unknown" in result.data


def test_web_report():
    repository_id = "abcd"
    commit_id = "dcba"
    data = b"""<coverage line-rate="0.791" />"""
    adapter = MagicMock()
    adapter.retrieve_cc_data = MagicMock(return_value=data)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/web/report/{}/{}".format(repository_id, commit_id)
            result = test_client.get(url)
            assert result.status_code == 200
            assert adapter.retrieve_cc_data.called_with(adapter, commit_id)


def test_web_report_not_found():
    repository_id = "abcd"
    commit_id = "dcba"
    adapter = MagicMock()
    adapter.retrieve_cc_data = MagicMock(return_value=None)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/web/report/{}/{}".format(repository_id, commit_id)
            result = test_client.get(url)
            assert result.status_code == 404
            assert adapter.retrieve_cc_data.called_with(adapter, commit_id)


def test_web_diff():
    repository_id = "abcd"
    commit_id = "dcba"
    data = b"""<coverage line-rate="0.791" />"""
    adapter = MagicMock()
    adapter.retrieve_cc_data = MagicMock(return_value=data)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/web/diff/{}/{}..{}".format(repository_id, commit_id, commit_id)
            result = test_client.get(url)
            assert result.status_code == 200
            assert adapter.retrieve_cc_data.called_with(adapter, commit_id)


def test_web_diff_not_found():
    repository_id = "abcd"
    commit_id = "dcba"
    adapter = MagicMock()
    adapter.retrieve_cc_data = MagicMock(return_value=None)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/web/diff/{}/{}..{}".format(repository_id, commit_id, commit_id)
            result = test_client.get(url)
            assert result.status_code == 404
            assert adapter.retrieve_cc_data.called_with(adapter, commit_id)


def test_put_reference():
    repository_id = "abcd"
    commit_id = "dcba"
    data = "<coverage/>"
    adapter = MagicMock()
    adapter.persist = MagicMock(return_value=None)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/api/v1/references/{}/{}/data".format(repository_id, commit_id)
            result = test_client.put(url, data=data,)
            assert result.status_code == 200
            assert "received" in result.data.decode("utf-8")
            assert adapter.persist.called


def test_put_reference_raising():
    repository_id = "abcd"
    commit_id = "dcba"
    adapter = MagicMock()

    def raising(*args, **kwargs):
        raise Exception("expected")

    adapter.persist = MagicMock(side_effect=raising)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/api/v1/references/{}/{}/data".format(repository_id, commit_id)
            result = test_client.put(url, data=None,)
            assert result.status_code != 200


def test_parse_args():
    args = csm.parse_args(["--adapter", "web", "--port", "1234", "--token", "aaaa"])
    assert args.token == "aaaa"
    assert args.port == 1234
    assert args.adapter == "web"


def test_load_app():
    adapter = MagicMock()
    SqliteServerAdapterClass = MagicMock()
    SqliteServerAdapterClass.__enter__ = MagicMock(return_value=adapter)
    adapter.list_repositories = MagicMock(return_value=frozenset([]))
    app = MagicMock()
    app.run = MagicMock()
    requests_mock = MagicMock()
    csm.requests = requests_mock
    with patch.object(
        csm, "SqliteServerAdapter", return_value=SqliteServerAdapterClass
    ):
        csm.load_app("token", config={"telemetry.disable": False})
    assert csm.app.config["TOKEN"] == "token"
    adapter.list_repositories.assert_called_once()
    requests_mock.post.assert_called_once()


def test_main():
    adapter = MagicMock()
    SqliteServerAdapterClass = MagicMock()
    SqliteServerAdapterClass.__enter__ = MagicMock(return_value=adapter)
    adapter.list_repositories = MagicMock(return_value=frozenset([]))
    requests_mock = MagicMock()
    csm.requests = requests_mock
    app = MagicMock()
    app.run = MagicMock()
    with patch.object(
        csm, "SqliteServerAdapter", return_value=SqliteServerAdapterClass
    ):
        csm.main([], app=app, config={"telemetry.disable": False})
    adapter.list_repositories.assert_called_once()
    app.run.assert_called_once()
    requests_mock.post.assert_called_once()


def test_send_event():
    adapter = MagicMock()
    SqliteServerAdapterClass = MagicMock()
    SqliteServerAdapterClass.__enter__ = MagicMock(return_value=adapter)
    adapter.list_repositories = MagicMock(
        return_value=frozenset(["one", "two", "three"])
    )
    adapter.commits_count = MagicMock(side_effect=lambda x: len(x))
    app = MagicMock()
    app.run = MagicMock()
    requests_mock = MagicMock()
    csm.requests = requests_mock
    with patch.object(
        csm, "SqliteServerAdapter", return_value=SqliteServerAdapterClass
    ):
        csm.load_app("token", config={"telemetry.disable": False})
    assert csm.app.config["TOKEN"] == "token"
    adapter.list_repositories.assert_called_once()
    adapter.commits_count.assert_has_calls(
        [call("three"), call("two"), call("one")], any_order=True
    )
    requests_mock.post.assert_called_once()


def test_send_event_telemetry_disabled():
    adapter = MagicMock()
    SqliteServerAdapterClass = MagicMock()
    SqliteServerAdapterClass.__enter__ = MagicMock(return_value=adapter)
    adapter.list_repositories = MagicMock(
        return_value=frozenset(["one", "two", "three"])
    )
    adapter.commits_count = MagicMock(side_effect=lambda x: len(x))
    app = MagicMock()
    app.run = MagicMock()
    requests_mock = MagicMock()
    csm.requests = requests_mock

    with patch.object(
        csm, "SqliteServerAdapter", return_value=SqliteServerAdapterClass
    ):
        with patch.object(
            csm.ccguard, "configuration", return_value={"telemetry.disable": True},
        ):
            csm.load_app("token", config={"telemetry.disable": True})

    adapter.record.assert_called_once()
    adapter.list_repositories.assert_called_once()
    adapter.commits_count.assert_has_calls(
        [call("three"), call("two"), call("one")], any_order=True
    )
    requests_mock.post.assert_not_called()


def test_sqlite_server_adapter():
    try:
        test_db_path = "./ccguard.server.db"
        config = {"sqlite.dbpath": test_db_path, "telemetry.disable": True}
        with csm.SqliteServerAdapter(config) as adapter:
            assert not adapter.list_repositories()
            with csm.ccguard.SqliteAdapter("test", config=config) as repo_adapter:
                repo_adapter.persist("fake_commit_id", b"<coverage/>")
            assert "test" in adapter.list_repositories()
            assert adapter.commits_count("test") == 1
            totals = adapter.totals()
            assert not totals.keys()
            csm.send_telemetry_event(config)
            totals = adapter.totals()
            version = list(totals.keys())[0]
            assert totals[version]["servers"] == 1
            assert totals[version]["served_repositories"] == 1
            assert totals[version]["recorded_commits"] == 1
            with csm.ccguard.SqliteAdapter("test", config=config) as repo_adapter:
                repo_adapter.persist("fake_commit_id2", b"<coverage/>")
            csm.send_telemetry_event(config)
            totals = adapter.totals()
            assert totals[version]["servers"] == 1
            assert totals[version]["served_repositories"] == 1
            assert totals[version]["recorded_commits"] == 2
    finally:
        os.unlink(test_db_path)
