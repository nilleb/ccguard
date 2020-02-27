import os
from . import ccguard
import redis
from unittest.mock import MagicMock, patch
from pycobertura import Cobertura, CoberturaDiff
from shutil import copyfile


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

    path = "ccguard/test_data/fake_coverage.xml"
    with open(path, "rb") as fd:
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


def test_parse_common():
    parser = ccguard.parse_common_args()
    args = parser.parse_args(["--repository", "test", "--debug", "--adapter", "mine"])
    assert args.debug
    assert args.repository == "test"
    assert args.adapter == "mine"


def test_configuration():
    config = ccguard.configuration()
    assert config
    dbpath = config.get("sqlite.dbpath")
    config = ccguard.configuration("ccguard/test_data/configuration_override")
    assert config
    dbpath_override = config.get("sqlite.dbpath")
    assert dbpath != dbpath_override


def setup_redis_mock():
    data = {}

    def set_data(a, b, c):
        v = data.get(a, {})
        v[b] = c
        data[a] = v
        print(data)

    def hkeys(a):
        return data.get(a, {}).keys()

    def get_data(a, b):
        return data.get(a, {}).get(b)

    def dump(a):
        return data.get(a, {}).items()

    redis_client = MagicMock()
    redis_client.hkeys = MagicMock(side_effect=hkeys)
    redis_client.hset = MagicMock(side_effect=set_data)
    redis_client.hget = MagicMock(side_effect=get_data)
    redis_client.hgetall = MagicMock(side_effect=dump)

    return redis_client


def adapter_scenario(adapter: ccguard.ReferenceAdapter):
    commits = adapter.get_cc_commits()
    adapter.persist("one", b"<coverage>1</coverage>")
    adapter.persist("two", b"<coverage>2</coverage>")
    adapter.persist("thr", b"<coverage>3</coverage>")
    try:
        adapter.persist("four", "a string")  # we pretend only bytes
        assert False
    except ValueError:
        pass
    adapter.persist(
        "four", b"invalid xml"
    )  # we don't care about the data, it's just data
    commits = adapter.get_cc_commits()
    assert len(commits) == 4
    data = adapter.retrieve_cc_data("one")
    assert isinstance(data, bytes)
    assert data.find(b"1")
    data = adapter.retrieve_cc_data("two")
    assert data.find(b"2")
    data = adapter.retrieve_cc_data("thr")
    assert data.find(b"3")
    data = adapter.dump()
    assert len(data) == 4
    assert not adapter.retrieve_cc_data("not found")
    for commit_id, reference in data:
        assert isinstance(commit_id, str)
        assert reference.find(b"coverage"), reference


def test_sqladapter():
    abspath = os.path.abspath("test.xml")

    try:
        config = ccguard.configuration("ccguard/test_data/configuration_override")
        with ccguard.SqliteAdapter("test", config) as adapter:
            adapter_scenario(adapter)

            # lts scenario: the data has been exported to the
            # long term storage
            with open(abspath, "wb") as fd:
                fd.write(b"<coverage>1</coverage>")
            adapter._update_lts("one", abspath)
            data = adapter.retrieve_cc_data("one")
            assert data.find(b"1")
    finally:
        # rather an integration test: we need to cleanup
        os.unlink("./ccguard.db")
        os.unlink(abspath)


def test_redis_adapter():
    redis.Redis = MagicMock(return_value=setup_redis_mock())

    config = ccguard.configuration()
    with ccguard.RedisAdapter("test", config) as adapter:
        adapter_scenario(adapter)


def test_adapter_factory():
    config = dict(ccguard.DEFAULT_CONFIGURATION)
    adapter_class = ccguard.adapter_factory(None, config)
    assert adapter_class is ccguard.SqliteAdapter

    def scenario(keyword, clazz):
        adapter_class = ccguard.adapter_factory(keyword, config)
        assert adapter_class is clazz
        config["adapter.class"] = keyword
        adapter_class = ccguard.adapter_factory(None, config)
        assert adapter_class is clazz

    scenario("redis", ccguard.RedisAdapter)
    scenario("web", ccguard.WebAdapter)

    adapter_class = ccguard.adapter_factory("sqlite", config)
    assert adapter_class is ccguard.SqliteAdapter
    config["adapter.class"] = "sqlite"
    adapter_class = ccguard.adapter_factory("redis", config)
    assert adapter_class is ccguard.RedisAdapter


def test_print_cc_report():
    report = Cobertura("ccguard/test_data/sample_coverage.xml")
    output = []

    def log_function(a):
        return output.append(a)

    ccguard.print_cc_report(report, log_function=log_function)


def test_print_cc_report_longer():
    report = Cobertura("ccguard/test_data/sample_coverage_longer.xml")
    output = []

    def log_function(a):
        return output.append(a)

    ccguard.print_cc_report(report, log_function=log_function)
    assert "..details omissed.." in output


def test_print_delta_report():
    reference = Cobertura(
        "ccguard/test_data/sample_coverage.xml",
        source=ccguard.GitAdapter().get_root_path() + "/ccguard",
    )
    challenger = Cobertura(
        "ccguard/test_data/sample_coverage_longer.xml",
        source=ccguard.GitAdapter().get_root_path() + "/ccguard",
    )
    output = []

    def log_function(a):
        return output.append(a)

    ccguard.print_delta_report(reference, challenger, log_function=log_function)
    assert output


def test_iter_callable():
    mock = MagicMock()
    ref = "test"
    refs = []
    mock.iter_git_commits = MagicMock(side_effect=lambda aList: refs.extend(aList))
    ccguard.iter_callable(mock, ref)()
    assert ref in refs
    assert len(refs) == 1


def test_has_better_coverage_failure():
    ref = Cobertura("ccguard/test_data/has_better_coverage/reference-code-coverage.xml")
    cha = Cobertura(
        "ccguard/test_data/has_better_coverage/failing-new-code-coverage.xml"
    )
    diff = CoberturaDiff(ref, cha)
    assert not ccguard.has_better_coverage(diff)


def test_has_better_coverage_same_file():
    ref = Cobertura("ccguard/test_data/has_better_coverage/reference-code-coverage.xml")
    cha = Cobertura("ccguard/test_data/has_better_coverage/reference-code-coverage.xml")
    diff = CoberturaDiff(ref, cha)
    assert ccguard.has_better_coverage(diff)


def test_has_better_coverage_success():
    ref = Cobertura("ccguard/test_data/has_better_coverage/reference-code-coverage.xml")
    cha = Cobertura(
        "ccguard/test_data/has_better_coverage/successful-new-code-coverage.xml"
    )
    diff = CoberturaDiff(ref, cha)
    assert ccguard.has_better_coverage(diff)


def test_has_better_coverage_new_file_failure():
    ref = Cobertura("ccguard/test_data/has_better_coverage/reference-code-coverage.xml")
    cha = Cobertura(
        "ccguard/test_data/has_better_coverage/new-file-new-code-coverage-fail.xml"
    )
    diff = CoberturaDiff(ref, cha)
    assert not ccguard.has_better_coverage(diff)


def test_determine_parent_commit():
    def iter_callable():
        yield [1, 2, 3]
        yield [4, 5, 6]

    assert 4 == ccguard.determine_parent_commit(frozenset([4, 7]), iter_callable)


def test_determine_parent_commit_none():
    def iter_callable():
        yield [1, 2, 3]
        yield [4, 5, 6]

    assert not ccguard.determine_parent_commit(frozenset([7]), iter_callable)


def test_get_root_path():
    current_folder = os.path.dirname(__file__)
    assert current_folder.startswith(ccguard.GitAdapter(".").get_root_path())


def test_main():
    adapter_class = MagicMock()
    adapter_factory = MagicMock(return_value=adapter_class)
    with patch.object(ccguard, "adapter_factory", return_value=adapter_factory):
        logging_module = MagicMock()
        output = []
        logging_module.warning = MagicMock(
            side_effect=lambda *args: output.append(args[0] % args[1:])
        )
        sample_file = "ccguard/test_data/sample_coverage.xml"
        test_file = os.path.splitext(sample_file)[0] + "-1.xml"
        copyfile(sample_file, test_file)
        ccguard.main(["--debug", test_file], logging_module=logging_module)
        assert [
            line for line in output if line == "No reference code coverage data found."
        ]
