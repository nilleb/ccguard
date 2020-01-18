from gitlog2json import GitLogger


def test_gitlogger():
    logger = GitLogger()
    commits = logger.log()
    assert commits
    first = next(iter(commits))
    assert isinstance(first, dict)
