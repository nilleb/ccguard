import logging
import shlex
import subprocess
import sqlite3
from pathlib import Path
from dataclasses import dataclass

# requires:
# - python
# - git

home = Path.home()
dbname = home.joinpath(".ccguard.db")


def get_output(command, working_folder=None):
    try:
        output = subprocess.check_output(shlex.split(command), cwd=working_folder)
        return output.decode("utf-8")
    except OSError:
        logging.error("Command being executed: {}".format(command))
        raise


class GitAdapter(object):
    @staticmethod
    def get_repository_id(repository_folder=None):
        return get_output(
            "git rev-list --max-parents=0 HEAD", working_folder=repository_folder
        ).rstrip()

    @staticmethod
    def get_current_commit_id(repository_folder=None):
        return get_output(
            "git rev-parse HEAD", working_folder=repository_folder
        ).rstrip()

    @staticmethod
    def iter_git_commits(repository_folder=None):
        count = 0
        while True:
            skip = "--skip={}".format(100 * count) if count else ""
            command = "git rev-list {} --max-count=100 HEAD".format(skip)
            commits = get_output(command, working_folder=repository_folder).split("\n")
            commits = [commit for commit in commits if commit]
            if not commits:
                return
            count += 1
            yield commits

    @staticmethod
    def get_files(repository_folder=None):
        command = "git rev-parse --show-toplevel"
        root_folder = get_output(command, working_folder=repository_folder).rstrip()
        command = "git ls-files"
        output = get_output(command, working_folder=root_folder)
        files = output.split("\n")
        if not files[-1]:
            files = files[:-1]
        return set(files)


class SqliteAdapter(object):
    def __init__(self, repository_id):
        self.repository_id = repository_id
        self.conn = sqlite3.connect(dbname)
        self._create_table()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.conn.close()

    def get_cc_commits(self):
        commits_query = "SELECT commit_id FROM timestamped_coverage_{repository_id}".format(
            repository_id=self.repository_id
        )
        return set(self.conn.execute(commits_query))

    def retrieve_cc_data(self, commit_id):
        query = 'SELECT coverage_data FROM timestamped_coverage_{repository_id}\
                WHERE commit_id="{}"'.format(
            repository_id=self.repository_id, commit_id=commit_id
        )
        return self.conn.execute(query)

    def persist(self, commit_id, data):
        query = """INSERT INTO timestamped_coverage_{repository_id}
        (commit_id, coverage_data) VALUES (?, ?)""".format(repository_id=self.repository_id)
        data_tuple = (commit_id, data)
        self.conn.execute(query, data_tuple)
        self.conn.commit()

    def _create_table(self):
        ddl = """CREATE TABLE IF NOT EXISTS `timestamped_coverage_{repository_id}` (
    `commit_id` varchar(40) NOT NULL,
    `collected_at` ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `coverage_data` BLOB NOT NULL default '',
    PRIMARY KEY  (`commit_id`)
    );"""
        statement = ddl.format(repository_id=self.repository_id)
        self.conn.execute(statement)


def determine_parent_commit(db_commits, iter_callable):
    for commits_chunk in iter_callable():
        for commit in commits_chunk:
            if commit in db_commits:
                return commit


@dataclass
class EntityData:
    """Class for keeping track of an entity CC data."""

    statements: int
    miss: int
    branch: int = 0
    br_part: int = 0
    ec: int = 0

    def cover(self) -> float:
        return 1.0 - self.miss / self.statements


def cc_rep():
    rep = {
        "server/eventstream/init.py": EntityData(
            statements=10, miss=0, branch=0, br_part=0, ec=100
        ),
        "server/eventstream/eventstream_manager.py": EntityData(
            statements=533, miss=42, branch=130, br_part=21, ec=90
        ),
    }
    return rep


"""
Name                                                                  Stmts   Miss Branch BrPart  Cover
-------------------------------------------------------------------------------------------------------
server/eventstream/__init__.py                                           10      0      0      0   100%
server/eventstream/eventstream_endpoints.py                              35     35      2      0     0%
server/eventstream/eventstream_manager.py                               533     42    130     21    90%
server/eventstream/eventstream_messages.py                               29     29      0      0     0%
server/eventstream/eventstream_model.py                                  12      0      0      0   100%
server/search/__init__.py                                                15      0      0      0   100%
server/search/business_logic_dispatcher.py                               37     23      8      0    31%
server/search/cloudsearch/__init__.py                                     0      0      0      0   100%
server/search/cloudsearch/cloudsearch_endpoints.py                      166     66     66      8    59%
server/search/cloudsearch/cloudsearch_manager.py                        523    416    200      1    15%
server/search/cloudsearch/cloudsearch_messages.py                       362      5     18      5    97%
server/search/cloudsearch/cloudsearch_model.py                            7      7      0      0     0%
server/search/cloudsearch/cloudsearch_queries.py                         57     27      2      0    51%
server/search/cloudsearch/cloudsearch_task.py                            48     33     18      0    23%
server/search/cloudsearch/cloudsearch_tools.py                           69     54     22      0    16%
server/search/cloudsearch/test_cloudsearch_manager.py                    37     21      4      0    39%
server/search/dumper.py                                                  46     46     22      0     0%
server/search/elasticsearch/__init__.py                                  94     71     32      0    18%
server/search/elasticsearch/config.py                                     9      2      0      0    78%
server/search/elasticsearch/converters/__init__.py                        0      0      0      0   100%
server/search/elasticsearch/converters/base_converter.py                171    137     74      0    14%
server/search/elasticsearch/converters/community_converter.py            31     22      8      0    23%
server/search/elasticsearch/converters/content_converter.py              59     49     36      0    11%
server/search/elasticsearch/converters/directory_entry_converter.py      38     26     12      0    24%
server/search/elasticsearch/converters/media_converter.py                30     21     22      0    17%
server/search/elasticsearch/converters/post_converter.py                 31     22     12      0    21%
server/search/elasticsearch/converters/user_converter.py                 21     14      4      0    28%
server/search/elasticsearch/elasticsearch_manager.py                    107     48     26      2    49%
server/search/elasticsearch/elasticsearch_task.py                        54     54     16      0     0%
server/search/indexer.py                                                 35     26     22      0    16%
server/search/microservice_tools.py                                      49     14     12      2    61%
server/search/omnisearch/__init__.py                                      0      0      0      0   100%
"""


def read_cc_data_from_file(fp):
    # select the right cc reader according to the format
    # rehydrate our EntityData according to the data in the format
    return cc_rep()


def rehydrate(blob):
    return cc_rep()


class Report(object):
    def __init__(self, reference, challenger):
        """
        for each mesurable object in the challenger,

        - compute the path
        - read the coverage value
        - save both to a dictionary

        for each mesurable object in the reference,

        - compute the path
        - read the coverage value
        - get the corresponding value in the challenger

        - if the value does not exist, then we have no coverage for this item
        - has it been deleted?
        - has it been excluded from coverage?
        - else (if the value exists)
        - v(challenger) >= v(reference) => OK
        - v(challenger) < v(reference) => NOK (regression detected)
        """

    def pretty_print(self):
        pass


@dataclass
class CommitData:
    """Class for keeping track of an entity CC data."""

    commit_id: str
    coverage_data: bytes

    def persist(self, repository_id, commit_id):
        conn.execute(
            "insert into timestamped_coverage_{repository_id}(p) values (?)".format(
                repository_id=repository_id
            ),
            (self,),
        )


def main():
    fp = "cc_data_file"
    repo_folder = "."
    should_fail_on_regression = True

    repository_id = get_repository_id(repo_folder)
    create_table(repository_id)
    db_commits = yield get_cc_commits()
    most_recent_commit_with_data = None

    def iter_callable():
        # FIXME implement a wrapper here
        return iter_git_commits(repo_folder)

    commit_id = determine_parent_commit(db_commits, iter_git_commits)
    cc_reference_data = rehydrate(retrieve_cc_data(repository_id, commit_id))

    cc_challenger_data = read_cc_data_from_file(fp)
    cc_challenger_data.persist(repository_id, get_current_commit_id())

    report = Report(cc_reference_data, cc_challenger_data, get_git_files(repo_folder))
    report.pretty_print()

    if should_fail_on_regression and report.regression_detected():
        exit(255)


if __name__ == "__main__":
    main()
