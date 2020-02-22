import git
from unittest.mock import MagicMock

import ccguard
from ccguard import ccguard_sync


def mock_adapter_class(commit_id_):
    class MockAdapter(object):
        def __init__(self, *args):
            super().__init__()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def get_cc_commits(self):
            return [commit_id_]

        def retrieve_cc_data(self, commit_id):
            assert commit_id == commit_id_

        def persist(self, commit_id, data):
            assert commit_id == commit_id_

    return MockAdapter


def fake_commit():
    mit = git.Commit(
        repo=MagicMock(), binsha=bytes("a" * 20, "utf-8"), message="message(aaa)"
    )
    mock = MagicMock()
    mock.iter_commits = MagicMock(side_effect=lambda: [mit])
    mock.commit = MagicMock(return_value=mit)
    git.Repo = MagicMock(return_value=mock)
    return mit


def test_transfer():
    mit = fake_commit()

    ccguard_sync.transfer(
        commit_id=None,
        source_adapter_class=mock_adapter_class(mit.hexsha),
        dest_adapter_class=mock_adapter_class(mit.hexsha),
    )


def test_transfer_single():
    mit = fake_commit()

    ccguard_sync.transfer(
        commit_id=mit.hexsha,
        source_adapter_class=mock_adapter_class(mit.hexsha),
        dest_adapter_class=mock_adapter_class(mit.hexsha),
    )


def test_parse_no_args():
    try:
        ccguard_sync.parse_args([])
        assert False
    except SystemExit:
        pass


def test_parse_optionals():
    try:
        ccguard_sync.parse_args(["--repository", "."])
        assert False
    except SystemExit:
        pass


def test_parse_shortest():
    args = ccguard_sync.parse_args(["redis", "sqlite"])
    assert args.source_adapter == "redis"
    assert args.dest_adapter == "sqlite"


def test_main():
    commit = fake_commit()
    ccguard.adapter_factory = lambda a, b: mock_adapter_class(commit.hexsha)
    lines = []
    ccguard_sync.main(["redis", "redis"], log_function=lambda *x: lines.append(x))
    assert lines


def test_main_debug():
    commit = fake_commit()
    ccguard.adapter_factory = lambda a, b: mock_adapter_class(commit.hexsha)
    lines = []
    ccguard_sync.main(
        ["--debug", "redis", "redis"], log_function=lambda *x: lines.append(x)
    )
    assert lines
