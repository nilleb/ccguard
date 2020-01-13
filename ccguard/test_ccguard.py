import ccguard


def test_get_repository_id():
    assert (
        ccguard.GitAdapter.get_repository_id()
        == "3c399795297536f1d2145672d69c94d8ad10326b"
    )


def test_get_current_commit_id():
    val = ccguard.GitAdapter.get_current_commit_id()
    assert isinstance(val, str)
    assert "\n" not in val


def test_get_common_ancestor():
    val = ccguard.GitAdapter.get_common_ancestor()
    assert isinstance(val, str)
    assert "\n" not in val


def test_iter_get_commits():
    val = list(ccguard.GitAdapter.iter_git_commits())
    assert isinstance(val, list)
    for vv in val:
        assert isinstance(vv, list)
        assert vv  # no empty lists
        for commit in vv:
            assert commit  # no empty strings


def test_get_files():
    val = ccguard.GitAdapter.get_files()
    assert isinstance(val, set)
    assert val
    for vv in val:
        assert "\n" not in val

def sample_sqladapter():
    with ccguard.SqliteAdapter('test') as adapter:
        commits = adapter.get_cc_commits()
