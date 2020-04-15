import os
import json
from sqlite3 import IntegrityError
from unittest.mock import MagicMock, call, patch

from . import ccguard_server as csm
from . import ccguard_server_blueprints as cbm
from .ccguard_server import ccguard as ccm


def test_home():
    with csm.app.test_client() as test_client:
        result = test_client.get("/")
        assert result.status_code == 200


def test_put_token_missing_data():
    with patch.object(cbm, "PersonalAccessToken") as pat_mock:
        pat_mock.list_by_user_id = MagicMock(return_value=[])
        with csm.app.test_client() as test_client:
            result = test_client.put("/api/v1/personal_access_token/me@example.com")
            assert result.status_code == 400
            assert result.data


def test_put_token():
    name = "hello world!"
    data = '{"name": "%s"}' % name
    user_id = "me@example.com"
    with patch.object(cbm, "sqlite3") as sqlite_mock:
        sqlite_mock.connect = MagicMock()
        fetchone = MagicMock(fetchone=MagicMock(return_value=None))
        execute = MagicMock(execute=MagicMock(return_value=fetchone))
        enter = MagicMock(__enter__=MagicMock(return_value=execute))
        sqlite_mock.connect = MagicMock(return_value=enter)
        with csm.app.test_client() as test_client:
            result = test_client.put(
                "/api/v1/personal_access_token/{}".format(user_id),
                data=data,
                content_type="application/json",
            )
            assert result.status_code == 200
            assert user_id.encode("utf-8") in result.data
            assert name.encode("utf-8") in result.data


def test_put_token_already():
    name = "hello world!"
    data = '{"name": "%s"}' % name
    user_id = "me@example.com"
    with patch.object(cbm, "sqlite3") as sqlite_mock:

        def execute_mock(*args):
            if len(args) > 1:
                raise IntegrityError
            else:
                return fetchone

        fetchone = MagicMock(fetchone=MagicMock(return_value=None))
        execute = MagicMock(execute=MagicMock(side_effect=execute_mock))
        enter = MagicMock(__enter__=MagicMock(return_value=execute))
        sqlite_mock.connect = MagicMock(return_value=enter)
        sqlite_mock.IntegrityError = IntegrityError
        with csm.app.test_client() as test_client:
            result = test_client.put(
                "/api/v1/personal_access_token/{}".format(user_id),
                data=data,
                content_type="application/json",
            )
            assert result.status_code == 409


def test_delete_token_no_auth():
    name = "hello world!"
    data = '{"name": "%s"}' % name
    user_id = "me@example.com"
    with csm.app.test_client() as test_client:
        result = test_client.delete(
            "/api/v1/personal_access_token/{}".format(user_id),
            data=data,
            content_type="application/json",
        )
        assert result.status_code == 403


def test_delete_token():
    name = "hello world!"
    data = '{"name": "%s"}' % name
    user_id = "me@example.com"
    with patch.object(cbm, "sqlite3"):
        with patch.object(cbm, "check_auth") as mock_auth:

            def set_user(a, b, g):
                g.user = user_id

            mock_auth.side_effect = set_user

            with csm.app.test_client() as test_client:
                result = test_client.delete(
                    "/api/v1/personal_access_token/{}".format(user_id),
                    data=data,
                    content_type="application/json",
                )
                assert result.status_code == 200


def test_get_tokens_no_auth():
    user_id = "me@example.com"
    with patch.object(cbm, "sqlite3") as sqlite_mock:
        sqlite_mock.connect = MagicMock()
        with csm.app.test_client() as test_client:
            result = test_client.get(
                "/api/v1/personal_access_tokens/{}".format(user_id),
                content_type="application/json",
            )
            assert result.status_code == 403


def test_get_tokens():
    user_id = "me@example.com"
    with patch.object(cbm, "sqlite3") as sqlite_mock:
        with patch.object(cbm, "check_auth") as mock_auth:

            def set_user(a, b, g):
                g.user = user_id

            mock_auth.side_effect = set_user
            sqlite_mock.connect = MagicMock()

            with csm.app.test_client() as test_client:
                result = test_client.get(
                    "/api/v1/personal_access_tokens/{}".format(user_id),
                    content_type="application/json",
                )
                assert result.status_code == 200
                assert b"[]" in result.data


def test_get_tokens_some():
    name = "hello world!"
    user_id = "me@example.com"
    with patch.object(cbm, "sqlite3") as sqlite_mock:
        with patch.object(cbm, "check_auth") as mock_auth:

            def set_user(a, b, g):
                g.user = user_id

            mock_auth.side_effect = set_user

            def execute_fetchall_mock(*args):
                return [(user_id, name, 0)]

            previous, pprevious, ppprevious = MagicMock(), MagicMock(), MagicMock()
            ppprevious.fetchall = MagicMock(side_effect=execute_fetchall_mock)
            pprevious.execute = MagicMock(return_value=ppprevious)
            previous.__enter__ = MagicMock(return_value=pprevious)
            sqlite_mock.connect = MagicMock(return_value=previous)

            with csm.app.test_client() as test_client:
                result = test_client.get(
                    "/api/v1/personal_access_tokens/{}".format(user_id),
                    content_type="application/json",
                )
                assert result.status_code == 200
                assert b"[]" not in result.data
                assert name.encode("utf-8") in result.data


def test_debug_repositories():
    config = {}
    adapter_class = MagicMock()
    adapter_class.list_repositories = MagicMock(return_value=frozenset(["abc"]))
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(cbm, "SqliteServerAdapter", return_value=adapter_factory):
        with patch.object(ccm, "configuration", return_value=config):
            with csm.app.test_client() as test_client:
                result = test_client.get("/api/v1/repositories/debug")
                assert result.status_code == 200
                assert result.data
                assert adapter_class.list_repositories.called_with(config)


def test_debug_repositories_v2():
    config = {}
    adapter_class = MagicMock()
    adapter_class.list_repositories = MagicMock(return_value=frozenset(["abc"]))
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(cbm, "SqliteServerAdapter", return_value=adapter_factory):
        with patch.object(ccm, "configuration", return_value=config):
            with csm.app.test_client() as test_client:
                result = test_client.get("/api/v2/repositories/debug")
                assert result.status_code == 200
                assert result.data
                assert adapter_class.list_repositories.called_with(config)


def test_all_references():
    repository_id = "abcd"
    config = {}
    commits = ["a", "b", "c", "d"]
    adapter = MagicMock()
    adapter.get_cc_commits = MagicMock(return_value=commits)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with patch.object(ccm, "configuration", return_value=config):
            with csm.app.test_client() as test_client:
                url = "/api/v1/references/{}/all".format(repository_id)
                result = test_client.get(url)
                assert result.status_code == 200
                assert json.loads(result.data.decode("utf-8")) == commits
                assert adapter_factory.called_with(None, config)
                assert adapter.get_cc_commits.called


def test_all_references_v2():
    repository_id = "abcd"
    config = {}
    commits = ["a", "b", "c", "d"]
    adapter = MagicMock()
    adapter.get_cc_commits = MagicMock(return_value=commits)
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with patch.object(ccm, "configuration", return_value=config):
            with csm.app.test_client() as test_client:
                url = "/api/v2/references/{}/all".format(repository_id)
                result = test_client.get(url)
                assert result.status_code == 200
                response = json.loads(result.data)
                assert response["references"] == commits
                assert adapter_factory.called_with(None, config)
                assert adapter.get_cc_commits.called


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
            url = "/api/v1/repositories/{}/status_badge.svg".format(repository_id)
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
            url = "/api/v1/repositories/{}/status_badge.svg".format(repository_id)
            result = test_client.get(url)
            assert result.status_code == 200
            assert b"unknown" in result.data


def test_web_main():
    repository_id = "abcd"
    commit_id = "dcba"
    data = b"""<coverage line-rate="0.791" />"""
    adapter = MagicMock()
    adapter.retrieve_cc_data = MagicMock(return_value=data)
    commits = frozenset([commit_id])
    adapter.get_cc_commits = MagicMock(return_value=commits)
    adapter.get_commit_info = MagicMock(return_value=[0.17, 17, 100])
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccm, "adapter_factory", return_value=adapter_factory):
        with csm.app.test_client() as test_client:
            url = "/web/main/{}".format(repository_id)
            result = test_client.get(url)
            assert result.status_code == 200
            assert b"79.10%" in result.data
            assert adapter.get_commit_info.called_with(adapter, commit_id)


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
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter.list_repositories = MagicMock(return_value=frozenset([]))
    app = MagicMock()
    app.run = MagicMock()
    requests_mock = MagicMock()
    csm.requests = requests_mock
    with patch.object(cbm, "SqliteServerAdapter", return_value=adapter_class):
        csm.load_app("token", config={"telemetry.disable": False})
    assert csm.app.config["TOKEN"] == "token"
    adapter.list_repositories.assert_called_once()
    requests_mock.post.assert_called_once()


def test_main():
    adapter = MagicMock()
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter.list_repositories = MagicMock(return_value=frozenset([]))
    requests_mock = MagicMock()
    csm.requests = requests_mock
    app = MagicMock()
    app.run = MagicMock()
    with patch.object(cbm, "SqliteServerAdapter", return_value=adapter_class):
        csm.main([], app=app, config={"telemetry.disable": False})
    adapter.list_repositories.assert_called_once()
    app.run.assert_called_once()
    requests_mock.post.assert_called_once()


def test_telemetry_post_no_data():
    adapter = MagicMock()
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter.record = MagicMock()
    adapter.commits_count = MagicMock(side_effect=lambda x: len(x))
    with patch.object(cbm, "SqliteServerAdapter", return_value=adapter_class):
        with csm.app.test_client() as test_client:
            url = "/api/v1/telemetry"
            result = test_client.post(url, data={})
            assert result.status_code == 200
            adapter.record.assert_not_called


def test_telemetry_post_data():
    adapter = MagicMock()
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter.record = MagicMock()
    adapter.commits_count = MagicMock(side_effect=lambda x: len(x))
    with patch.object(cbm, "SqliteServerAdapter", return_value=adapter_class):
        with csm.app.test_client() as test_client:
            url = "/api/v1/telemetry"
            result = test_client.post(
                url, data='{"repositories_count": 1}', content_type="application/json"
            )
            assert result.status_code == 200
            adapter.record.assert_called_once


def test_telemetry_get():
    adapter = MagicMock()
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter.totals = MagicMock(
        return_value={
            "0.4.2": {
                "servers": 1,
                "served_repositories": 0,
                "recorded_commits": 0,
            }  # noqa
        }
    )
    adapter.commits_count = MagicMock(side_effect=lambda x: len(x))
    with patch.object(cbm, "SqliteServerAdapter", return_value=adapter_class):
        with csm.app.test_client() as test_client:
            url = "/api/v1/telemetry"
            result = test_client.get(url)
            assert result.status_code == 200
            adapter.totals.assert_called_once


def test_send_event():
    adapter = MagicMock()
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter.list_repositories = MagicMock(
        return_value=frozenset(["one", "two", "three"])
    )
    adapter.commits_count = MagicMock(side_effect=lambda x: len(x))
    app = MagicMock()
    app.run = MagicMock()
    requests_mock = MagicMock()
    csm.requests = requests_mock
    with patch.object(cbm, "SqliteServerAdapter", return_value=adapter_class):
        csm.load_app("token", config={"telemetry.disable": False})
    assert csm.app.config["TOKEN"] == "token"
    adapter.list_repositories.assert_called_once()
    adapter.commits_count.assert_has_calls(
        [call("three"), call("two"), call("one")], any_order=True
    )
    requests_mock.post.assert_called_once()


def test_send_event_telemetry_disabled():
    adapter = MagicMock()
    adapter_class = MagicMock()
    adapter_class.__enter__ = MagicMock(return_value=adapter)
    adapter.list_repositories = MagicMock(
        return_value=frozenset(["one", "two", "three"])
    )
    adapter.commits_count = MagicMock(side_effect=lambda x: len(x))
    app = MagicMock()
    app.run = MagicMock()
    requests_mock = MagicMock()
    csm.requests = requests_mock

    config = {"telemetry.disable": True}
    with patch.object(cbm, "SqliteServerAdapter", return_value=adapter_class):
        with patch.object(ccm, "configuration", return_value=config):
            csm.load_app("token", config=config)

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
        with cbm.SqliteServerAdapter(config) as adapter:
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


def test_personal_access_token():
    try:
        test_db_path = "./ccguard.server.db"
        config = {"sqlite.dbpath": test_db_path}
        pato = cbm.PersonalAccessToken("ivo", "test name", value="aaa")
        pato.commit(config)
        patr = cbm.PersonalAccessToken.get_by_value("aaa", config=config)
        assert patr.user_id == pato.user_id
    finally:
        os.unlink(test_db_path)


def test_personal_access_token_generate():
    try:
        test_db_path = "./ccguard.server.db"
        config = {"sqlite.dbpath": test_db_path}
        pato = cbm.PersonalAccessToken("ivo", "test name", "aaa")
        pato.commit(config)
        patr = cbm.PersonalAccessToken.get_by_value(pato.value, config=config)
        assert patr.user_id == pato.user_id
    finally:
        os.unlink(test_db_path)


def test_check_auth():
    pat = cbm.PersonalAccessToken("ivo", "toto")
    flask_global = MagicMock()
    with patch.object(cbm, "PersonalAccessToken") as pat_mock:
        config = {}
        headers = {}
        assert not cbm.check_auth(headers, config, flask_global)
        assert not flask_global.user

        config = {"TOKEN": "toto"}
        headers = {}
        code, message = cbm.check_auth(headers, config, flask_global)
        assert code == 401
        assert not flask_global.user

        config = {"TOKEN": "toto"}
        headers = {"authorization": "toto"}
        assert not cbm.check_auth(headers, config, flask_global)
        assert flask_global.user == cbm.ADMIN

        config = {}
        headers = {"authorization": "none"}
        code, message = cbm.check_auth(headers, config, flask_global)
        assert code == 403
        assert not flask_global.user

        config = {"TOKEN": "toto"}
        headers = {"authorization": "none"}
        code, message = cbm.check_auth(headers, config, flask_global)
        assert code == 403
        assert not flask_global.user

        pat_mock.get_by_value = MagicMock(return_value=pat)
        config = {}
        headers = {"authorization": "toto"}
        assert not cbm.check_auth(headers, config, flask_global)
        assert flask_global.user == pat.user_id
