# courtesy of mrVanDalo (https://gist.github.com/mrVanDalo/6a1d1aed4bd613fbdf1fa751fca47c6a)
from git import Repo


class GitLogger:
    """to provide a log as dict of commits which are json printable"""

    def __init__(self, path="."):
        """Create a GitStepper with the path to the git repository (not a bare repository)"""
        self.repo = Repo(path)

    def log(self):
        """return a list of commits, each being a dictionary"""
        commits = (self.repo.commit(logEntry) for logEntry in self.repo.iter_commits())
        return (self.to_dict(x) for x in commits)

    def to_dict(self, commit):
        """create a dict out of a commit that is easy to json serialize"""
        return {
            "author_email": commit.author.email,
            "author_name": commit.author.name,
            "authored_date": commit.authored_datetime.isoformat(),
            "changes": commit.stats.files,
            "committed_date": commit.committed_datetime.isoformat(),
            "committer_email": commit.committer.email,
            "committer_name": commit.committer.name,
            "encoding": commit.encoding,
            "hash": commit.hexsha,
            "message": commit.message,
            "summary": commit.summary,
            "size": commit.size,
            "stats_total": commit.stats.total,
            "parents": [parent.hexsha for parent in commit.parents],
        }
