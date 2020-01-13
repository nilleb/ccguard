#! /usr/bin/env python3

import io
import argparse
import logging
import shlex
import subprocess
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from pycobertura import Cobertura, CoberturaDiff, TextReporterDelta, TextReporter
from pycobertura.reporters import HtmlReporterDelta


HOME = Path.home()
DBNAME = HOME.joinpath(".ccguard.db")


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
    def iter_git_commits(repository_folder=None, ref="HEAD"):
        count = 0
        while True:
            skip = "--skip={}".format(100 * count) if count else ""
            command = "git rev-list {} --max-count=100 {}".format(skip, ref)
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

    @staticmethod
    def get_common_ancestor(repository_folder=None, base_branch="master", ref="HEAD"):
        command = "git merge-base {} {}".format(base_branch, ref)
        output = get_output(command, working_folder=repository_folder).rstrip()
        return output
        # at the moment, CircleCI does not provide the name of the base|target branch
        # https://ideas.circleci.com/ideas/CCI-I-894


class SqliteAdapter(object):
    def __init__(self, repository_id, dbname=DBNAME):
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


def main():
    parser = argparse.ArgumentParser(
        description="Display code coverage and verify regression."
    )

    parser.add_argument("report", help="the coverage report for the current commit ID")
    parser.add_argument(
        "--repository", dest="repository", help="the repository to analyze", default="."
    )
    parser.add_argument(
        "--target-branch",
        dest="target_branch",
        help="the branch to which this code will be merged",
        default="master",
    )
    parser.add_argument(
        "--fail-on-regression",
        dest="fail_on_regression",
        help="whether we should fail on regression",
        action="store_true",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        help="whether to print debug messages",
        action="store_true",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    repository_id = GitAdapter.get_repository_id(args.repository)

    diff = None
    challenger = Cobertura(args.report, source=args.repository)

    with SqliteAdapter(repository_id) as adapter:
        reference_commits = adapter.get_cc_commits()
        logging.debug("Found the following reference commits: %r", reference_commits)

        common_ancestor = GitAdapter().get_common_ancestor(
            args.repository, args.target_branch
        )

        def iter_callable():
            def call():
                return GitAdapter.iter_git_commits(args.repository, common_ancestor)

            return call

        commit_id = determine_parent_commit(
            reference_commits, GitAdapter.iter_git_commits
        )

        if commit_id:
            logging.info("Found reference data for commit %s", commit_id)
            cc_reference_data = adapter.retrieve_cc_data(commit_id)
            logging.debug("Reference data: %r", cc_reference_data)
            reference_fd = io.StringIO(cc_reference_data)

            reference = Cobertura(reference_fd, source=args.repository)
            diff = CoberturaDiff(reference, challenger)
        else:
            logging.warning("No reference code coverage data found.")

        if challenger:
            print(TextReporter(challenger).generate())

            with open(args.report) as fd:
                data = fd.read()
                current_commit = GitAdapter.get_current_commit_id()
                adapter.persist(current_commit, data)
                logging.info(
                    "Data for commit %s persisted successfully.", current_commit
                )
        else:
            logging.error("No recent code coverage data found.")

    if diff:
        if diff.has_better_coverage():
            print("Congratulations! You have improved the code coverage")
        else:
            print("Hey, there's still some unit testing to do before merging ;-)")

        if diff.has_all_changes_covered():
            print("Huge! all of your new code is fully covered!")

        reporter = TextReporterDelta
        delta = reporter(reference, challenger)
        print(delta.generate())

    if args.fail_on_regression and diff and not diff.has_better_coverage():
        exit(255)


if __name__ == "__main__":
    main()
