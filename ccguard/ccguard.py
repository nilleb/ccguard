#! /usr/bin/env python3

import io
import argparse
import json
import logging
import shlex
import subprocess
import sqlite3
from datetime import datetime
from pathlib import Path
import redis
from pycobertura import Cobertura, CoberturaDiff, TextReporterDelta, TextReporter
from pycobertura.reporters import HtmlReporter, HtmlReporterDelta


HOME = Path.home()
DB_FILE_NAME = ".ccguard.db"
CONFIG_FILE_NAME = ".ccguard.config"

DEFAULT_CONFIGURATION = {
    "redis.host": "localhost",
    "redis.port": 6379,
    "redis.db": 0,
    "redis.password": None,
    "sqlite.dbpath": HOME.joinpath(DB_FILE_NAME),
}


def configuration(repository_path="."):
    user_config = HOME.joinpath(CONFIG_FILE_NAME)
    repository_config = Path(repository_path).joinpath(CONFIG_FILE_NAME)

    paths = [user_config, repository_config]
    config = dict(DEFAULT_CONFIGURATION)
    for path in paths:
        try:
            with open(path) as config_fd:
                config.update(json.load(config_fd))
        except FileNotFoundError:
            pass
    return config


def get_output(command, working_folder=None):
    try:
        output = subprocess.check_output(shlex.split(command), cwd=working_folder)
        return output.decode("utf-8")
    except OSError:
        logging.error("Command being executed: {}".format(command))
        raise


class GitAdapter(object):
    def __init__(self, repository_folder="."):
        self.repository_folder = repository_folder

    def get_repository_id(self):
        return get_output(
            "git rev-list --max-parents=0 HEAD", working_folder=self.repository_folder
        ).rstrip()

    def get_current_commit_id(self):
        return get_output(
            "git rev-parse HEAD", working_folder=self.repository_folder
        ).rstrip()

    def iter_git_commits(self, refs=None):
        if not refs:
            refs = ["HEAD^"]

        count = 0
        while True:
            skip = "--skip={}".format(100 * count) if count else ""
            command = "git rev-list {} --max-count=100 {}".format(skip, " ".join(refs))
            commits = get_output(command, working_folder=self.repository_folder).split(
                "\n"
            )
            commits = [commit for commit in commits if commit]
            if not commits:
                return
            count += 1
            logging.debug("Returning as previous revisions: %r", commits)
            yield commits

    def get_files(self,):
        command = "git rev-parse --show-toplevel"
        root_folder = get_output(
            command, working_folder=self.repository_folder
        ).rstrip()
        command = "git ls-files"
        output = get_output(command, working_folder=root_folder)
        files = output.split("\n")
        if not files[-1]:
            files = files[:-1]
        return set(files)

    def get_common_ancestor(self, base_branch="master", ref="HEAD"):
        command = "git merge-base {} {}".format(base_branch, ref)
        output = get_output(command, working_folder=self.repository_folder).rstrip()
        return output
        # at the moment, CircleCI does not provide the name of the base|target branch
        # https://ideas.circleci.com/ideas/CCI-I-894


class SqliteAdapter(object):
    def __init__(self, repository_id, config):
        dbpath = config.get("sqlite.dbpath")
        self.repository_id = repository_id
        self.conn = sqlite3.connect(dbpath)
        self._create_table()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.conn.close()

    def get_cc_commits(self):
        commits_query = "SELECT commit_id FROM timestamped_coverage_{repository_id}".format(
            repository_id=self.repository_id
        )
        return frozenset(
            c for ct in self.conn.execute(commits_query).fetchall() for c in ct
        )

    def retrieve_cc_data(self, commit_id):
        query = 'SELECT coverage_data FROM timestamped_coverage_{repository_id}\
                WHERE commit_id="{commit_id}"'.format(
            repository_id=self.repository_id, commit_id=commit_id
        )
        return self.conn.execute(query).fetchone()[0]

    def persist(self, commit_id, data):
        query = """INSERT INTO timestamped_coverage_{repository_id}
        (commit_id, coverage_data) VALUES (?, ?)""".format(
            repository_id=self.repository_id
        )
        data_tuple = (commit_id, data)
        try:
            self.conn.execute(query, data_tuple)
            self.conn.commit()
        except sqlite3.IntegrityError:
            logging.debug("This commit seems to have already been recorded.")

    def dump(self):
        query = """SELECT commit_id, coverage_data
        FROM timestamped_coverage_{repository_id}""".format(
            repository_id=self.repository_id
        )
        return self.conn.execute(query).fetchall()

    def _create_table(self):
        ddl = """CREATE TABLE IF NOT EXISTS `timestamped_coverage_{repository_id}` (
    `commit_id` varchar(40) NOT NULL,
    `collected_at` ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `coverage_data` BLOB NOT NULL default '',
    PRIMARY KEY  (`commit_id`)
    );"""
        statement = ddl.format(repository_id=self.repository_id)
        self.conn.execute(statement)


class RedisAdapter(object):
    def __init__(self, repository_id, config={}):
        self.repository_id = repository_id
        host = config.get("redis.host")
        port = config.get("redis.port")
        db = config.get("redis.db")
        password = config.get("redis.password")
        self.redis = redis.Redis(host=host, port=port, db=db, password=password)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.redis.close()

    def get_cc_commits(self):
        return frozenset(self.redis.hkeys(self.repository_id))

    def retrieve_cc_data(self, commit_id):
        return self.redis.hget(self.repository_id, commit_id)

    def persist(self, commit_id, data):
        self.redis.hset(self.repository_id, commit_id, data)
        self.redis.hset(
            "{}:time".format(self.repository_id), commit_id, str(datetime.now())
        )

    def dump(self):
        return self.redis.hgetall(self.repository_id)


def determine_parent_commit(db_commits, iter_callable):
    for commits_chunk in iter_callable():
        for commit in commits_chunk:
            if commit in db_commits:
                return commit


def persist(repo_adapter, reference_adapter, report_file):
    with open(report_file) as fd:
        data = fd.read()
        current_commit = repo_adapter.get_current_commit_id()
        reference_adapter.persist(current_commit, data)
        logging.info("Data for commit %s persisted successfully.", current_commit)


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="You can only improve! Compare Code Coverage and prevent regressions."
    )

    parser.add_argument("report", help="the coverage report for the current commit ID")
    parser.add_argument(
        "--repository", dest="repository", help="the repository to analyze", default="."
    )
    parser.add_argument(
        "--target-branch",
        dest="target_branch",
        help="the branch to which this code will be merged (default: master)",
        default="master",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        help="whether to print debug messages",
        action="store_true",
    )
    parser.add_argument(
        "--html",
        dest="html",
        help="whether to produce a html report (cc.html and diff.html)",
        action="store_true",
    )
    parser.add_argument(
        "--consider-uncommitted-changes",
        dest="uncommitted",
        help="whether to consider uncommitted changes. reference will not be persisted.",
        action="store_true",
    )
    parser.add_argument(
        "--adapter",
        dest="adapter",
        help="Choose the adapter to use (choices: sqlite or redis)",
    )

    return parser.parse_args(args)


def adapter_factory(adapter, config):
    if adapter:
        if adapter == "sqlite":
            adapter_class = SqliteAdapter
        if adapter == "redis":
            adapter_class = RedisAdapter
        if adapter_class:
            return adapter_class

    adapter_class = (
        RedisAdapter if config.get("adapter.class", None) == "redis" else SqliteAdapter
    )

    return adapter_class


def iter_callable(git, ref):
    def call():
        return git.iter_git_commits([ref])

    return call


def print_cc_report(challenger, html_too=False, log_function=print):
    if len(challenger.files()) > 5:
        log_function("Filename      Stmts    Miss  Cover")
        log_function("----------  -------  ------  -------")
        log_function("..details omissed..")
        log_function(
            "{}\t\t{}\t{}\t{}\n".format(
                "TOTAL",
                challenger.total_statements(),
                challenger.total_misses(),
                challenger.line_rate(),
            )
        )
    else:
        log_function("{}{}".format(TextReporter(challenger).generate(), "\n"))

    if html_too:
        report = HtmlReporter(challenger)
        with open("cc.html", "w") as ccfile:
            ccfile.write(report.generate())


def print_diff_message(diff, log_function=print):
    if diff.has_better_coverage():
        log_function(
            "✨ 🍰 ✨  Congratulations! "
            "You have improved the code coverage (or kept it stable)."
        )
    else:
        log_function(
            "💥 💔 💥  Hey, there's still some unit testing to do before merging 😉 "
        )

    if diff.has_all_changes_covered():
        log_function("💯 Huge! all of your new code is fully covered!")

    if diff.diff_total_misses() < 0:
        log_function(
            "🙏🏻 🙏🏻 🙏🏻 Kudos! you have reduced the number of uncovered statements!"
        )


def print_delta_report(reference, challenger, html_too=False, log_function=print):
    delta = TextReporterDelta(reference, challenger)
    log_function(delta.generate())

    if html_too:
        delta = HtmlReporterDelta(reference, challenger)
        with open("diff.html", "w") as diff_file:
            diff_file.write(delta.generate())


def main():
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    git = GitAdapter(args.repository)
    repository_id = git.get_repository_id()

    diff, reference = None, None
    challenger = Cobertura(args.report, source=args.repository)

    config = configuration(args.repository)

    with adapter_factory(args.adapter, config)(repository_id, config) as adapter:
        reference_commits = adapter.get_cc_commits()
        logging.debug("Found the following reference commits: %r", reference_commits)

        common_ancestor = git.get_common_ancestor(args.target_branch)

        ref = common_ancestor if args.uncommitted else "{}^".format(common_ancestor)

        commit_id = determine_parent_commit(reference_commits, iter_callable(git, ref))

        if commit_id:
            logging.info("Retrieving data for refrence commit %s.", commit_id)
            cc_reference_data = adapter.retrieve_cc_data(commit_id)
            logging.debug("Reference data: %r", cc_reference_data)
            reference_fd = io.StringIO(cc_reference_data)
            reference = Cobertura(reference_fd, source=args.repository)
            diff = CoberturaDiff(reference, challenger)
        else:
            logging.warning("No reference code coverage data found.")

        if challenger:
            print_cc_report(challenger, args.html)

            if not args.uncommitted:
                persist(git, adapter, args.report)
        else:
            logging.error("No recent code coverage data found.")

    if diff:
        print_diff_message(diff)
        print_delta_report(reference, challenger, args.html)

    if diff and not diff.has_better_coverage():
        exit(255)


if __name__ == "__main__":
    main()
