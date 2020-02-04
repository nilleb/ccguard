import git
from . import ccguard_log
from unittest.mock import MagicMock


def mock_adapter_class(commit_id):
    class MockAdapter(object):
        def __init__(self, *args):
            super().__init__()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def dump(self):
            return [[commit_id, '<coverage line-rate="50"/>']]

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


def test_detailed_references():
    mit = fake_commit()

    refs = ccguard_log.detailed_references(adapter_class=mock_adapter_class(mit.hexsha))
    for ref in refs:
        assert isinstance(ref, ccguard_log.AnnotatedCommit)
        assert len(str(ref)) > 0
        assert str(ref) == repr(ref)


def test_list_references():
    ccguard_log.list_references()


def test_parse_no_args():
    args = ccguard_log.parse_args([])
    assert args.repository == "."


def test_parse_optionals():
    args = ccguard_log.parse_args(["--repository", "test"])
    assert args.repository == "test"


def test_parse_shortest():
    args = ccguard_log.parse_args(["--adapter", "sqlite"])
    assert args.adapter == "sqlite"
