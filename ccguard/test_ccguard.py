import ccguard
import redis
from unittest.mock import MagicMock


def test_get_repository_id():
    assert (
        ccguard.GitAdapter().get_repository_id()
        == "a8858db8a0d483f8f6c8e74a5dc03b84bc9674f8"
    )


def test_get_current_commit_id():
    val = ccguard.GitAdapter().get_current_commit_id()
    assert isinstance(val, str)
    assert "\n" not in val


def test_get_common_ancestor():
    val = ccguard.GitAdapter().get_common_ancestor()
    assert isinstance(val, str)
    assert "\n" not in val


def test_iter_get_commits():
    val = list(ccguard.GitAdapter().iter_git_commits())
    assert isinstance(val, list)
    for vv in val:
        assert isinstance(vv, list)
        assert vv  # no empty lists
        for commit in vv:
            assert commit  # no empty strings


def test_get_files():
    val = ccguard.GitAdapter().get_files()
    assert isinstance(val, set)
    assert val
    for vv in val:
        assert "\n" not in val


def test_persist():
    commit_id = "test"
    repo = MagicMock()
    repo.get_current_commit_id = MagicMock(return_value=commit_id)

    reference = MagicMock()
    reference.persist = MagicMock()

    data = "<coverage/>"
    path = "ccguard/test_data/fake_coverage.xml"
    with open(path) as fd:
        data = fd.read()

    ccguard.persist(repo, reference, path)

    repo.get_current_commit_id.assert_called()
    reference.persist.assert_called_with(commit_id, data)


def test_parse():
    args = ccguard.parse_args(
        ["--consider-uncommitted-changes", "--debug", "coverage.xml"]
    )
    assert args.debug
    assert args.uncommitted
    assert args.report == "coverage.xml"


def test_configuration():
    config = ccguard.configuration()
    assert config
    dbpath = config.get("sqlite.dbpath")
    config = ccguard.configuration("ccguard/test_data/configuration_override")
    assert config
    dbpath_override = config.get("sqlite.dbpath")
    assert dbpath != dbpath_override


def adapter_scenario(adapter):
    commits = adapter.get_cc_commits()
    adapter.persist("one", "<coverage>1</coverage>")
    adapter.persist("two", "<coverage>2</coverage>")
    adapter.persist("thr", "<coverage>3</coverage>")
    commits = adapter.get_cc_commits()
    assert len(commits) == 3
    data = adapter.retrieve_cc_data("one")
    assert "1" in data
    data = adapter.retrieve_cc_data("two")
    assert "2" in data
    data = adapter.retrieve_cc_data("thr")
    assert "3" in data


def test_sqladapter():
    config = ccguard.configuration("ccguard/test_data/configuration_override")
    with ccguard.SqliteAdapter("test", config) as adapter:
        adapter_scenario(adapter)


def setup_redis_mock():
    data = {}

    def set_data(a, b, c):
        v = data.get(a, {})
        v[b] = c
        data[a] = v
        print(data)

    hkeys = lambda a: data.get(a, {}).keys()
    get_data = lambda a, b: data.get(a, {}).get(b)

    redis_client = MagicMock()
    redis_client.hkeys = MagicMock(side_effect=hkeys)
    redis_client.hset = MagicMock(side_effect=set_data)
    redis_client.hget = MagicMock(side_effect=get_data)

    return redis_client


def test_redis_adapter():
    redis.Redis = MagicMock(return_value=setup_redis_mock())

    config = ccguard.configuration("ccguard/test_data/configuration_override")
    with ccguard.RedisAdapter("test", config) as adapter:
        adapter_scenario(adapter)
