#! /usr/bin/env python3

import io
import argparse
import json
import logging
import shlex
import subprocess
import sqlite3
import redis
import lxml.etree as ET
from pathlib import Path
from datetime import datetime
import os
import requests
from typing import Optional, Callable
from pycobertura import Cobertura, CoberturaDiff, TextReporterDelta, TextReporter
from pycobertura.reporters import HtmlReporter, HtmlReporterDelta


HOME = Path.home()
DB_FILE_NAME = ".ccguard.db"
CONFIG_FILE_NAME = ".ccguard.config.json"

DEFAULT_CONFIGURATION = {
    "redis.host": "localhost",
    "redis.port": 6379,
    "redis.db": 0,
    "redis.password": None,
    "ccguard.server.address": "http://127.0.0.1:5000",
    "threshold.tolerance": 0,
    "threshold.hard-minimum": -1,
    "sqlite.dbpath": HOME.joinpath(DB_FILE_NAME),
}


def configuration(repository_path="."):
    user_config = HOME.joinpath(CONFIG_FILE_NAME)
    repository_config = Path(repository_path).joinpath(CONFIG_FILE_NAME)

    paths = [user_config, repository_config]
    config = dict(DEFAULT_CONFIGURATION)
    for path in paths:
        logging.debug("Considering %s as configuration file", path)
        try:
            with open(path) as config_fd:
                config.update(json.load(config_fd))
        except FileNotFoundError:
            logging.debug("File %s has not been found", path)
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

    def get_files(self):
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
        return get_output(command, working_folder=self.repository_folder).rstrip()
        # at the moment, CircleCI does not provide the name of the base|target branch
        # https://ideas.circleci.com/ideas/CCI-I-894

    def get_root_path(self):
        command = "git rev-parse --show-toplevel"
        return get_output(command, working_folder=self.repository_folder).rstrip()


class ReferenceAdapter(object):
    def __init__(self, repository_id, config):
        self.config = config
        self.repository_id = repository_id

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def get_cc_commits(self) -> frozenset:
        raise NotImplementedError()

    def retrieve_cc_data(self, commit_id: str) -> Optional[bytes]:
        raise NotImplementedError()

    def persist(self, commit_id: str, data: bytes):
        raise NotImplementedError()

    def dump(self) -> list:
        raise NotImplementedError()

    @staticmethod
    def list_repositories(config: dict) -> frozenset:
        raise NotImplementedError()


class SqliteAdapter(ReferenceAdapter):
    def __init__(self, repository_id, config):
        super().__init__(repository_id, config)
        dbpath = str(config.get("sqlite.dbpath"))
        self.conn = sqlite3.connect(dbpath)
        self._create_table()

    def __exit__(self, exc_type, exc_value, traceback):
        self.conn.close()

    def get_cc_commits(self) -> frozenset:
        commits_query = "SELECT commit_id FROM timestamped_coverage_{repository_id}".format(
            repository_id=self.repository_id
        )
        return frozenset(
            c for ct in self.conn.execute(commits_query).fetchall() for c in ct
        )

    def retrieve_cc_data(self, commit_id: str) -> Optional[bytes]:
        query = 'SELECT coverage_data FROM timestamped_coverage_{repository_id}\
                WHERE commit_id="{commit_id}"'.format(
            repository_id=self.repository_id, commit_id=commit_id
        )

        result = self.conn.execute(query).fetchone()

        if result:
            return next(iter(result))
        return None

    def persist(self, commit_id: str, data: bytes):
        if not data or not isinstance(data, bytes):
            raise Exception("Unwilling to persist invalid data.")

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

    def dump(self) -> list:
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

    @staticmethod
    def list_repositories(config) -> frozenset:
        dbpath = str(config.get("sqlite.dbpath"))
        conn = sqlite3.connect(dbpath)
        query = """SELECT name FROM sqlite_master
            WHERE type = "table" AND name LIKE "timestamped_coverage_%" """

        tuples = conn.execute(query).fetchall()
        return frozenset({row[0].lstrip("timestamped_coverage_") for row in tuples})


class WebAdapter(ReferenceAdapter):
    def __init__(self, repository_id, config={}):
        conf_key = "ccguard.server.address"
        token_key = "ccguard.token"
        env_server = os.environ.get(conf_key.replace(".", "_"), None)
        self.server = env_server if env_server else config.get(conf_key)
        self.server = (
            self.server.rstrip("/") if self.server else "http://localhost:5000"
        )
        token = os.environ.get(token_key.replace(".", "_"), None)
        self.token = token if token else config.get(conf_key, None)
        super().__init__(repository_id, config)

    def get_cc_commits(self) -> frozenset:
        r = requests.get(
            "{p.server}/api/v1/references/{p.repository_id}/all".format(p=self)
        )
        try:
            return frozenset(r.json())
        except json.decoder.JSONDecodeError:
            logging.warning(
                "Got unexpected server response. Is the server configuration correct?\n%s",
                r.content.decode("utf-8"),
            )
            return frozenset()

    def retrieve_cc_data(self, commit_id: str) -> Optional[bytes]:
        r = requests.get(
            "{p.server}/api/v1/references/{p.repository_id}/{commit_id}/data".format(
                p=self, commit_id=commit_id
            )
        )
        return r.content.decode("utf-8")

    def persist(self, commit_id: str, data: bytes):
        if not data or not isinstance(data, bytes):
            raise Exception("Unwilling to persist invalid data.")

        headers = {}
        if self.token:
            headers["Authorization"] = self.token

        requests.put(
            "{p.server}/api/v1/references/{p.repository_id}/{commit_id}/data".format(
                p=self, commit_id=commit_id
            ),
            headers=headers,
            data=data,
        )

    def dump(self) -> list:
        r = requests.get(
            "{p.server}/api/v1/references/{p.repository_id}/data".format(p=self)
        )
        if r.ok:
            logging.debug("Response\n%r", r)
            return r.json()
        logging.error("Unexpected failure on dump: %s", r.text)
        return []


class RedisAdapter(ReferenceAdapter):
    def __init__(self, repository_id: str, config={}):
        self.repository_id = repository_id
        self.redis = self._build_redis(config)
        self.redis.sadd("ccguardrepositories", repository_id)

    @staticmethod
    def _build_redis(config: dict):
        host = config.get("redis.host")
        port = config.get("redis.port")
        db = config.get("redis.db")
        password = config.get("redis.password")
        return redis.Redis(host=host, port=port, db=db, password=password)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.redis.close()

    def get_cc_commits(self) -> frozenset:
        return frozenset(self.redis.hkeys(self.repository_id))

    def retrieve_cc_data(self, commit_id: str) -> Optional[bytes]:
        return self.redis.hget(self.repository_id, commit_id)

    def persist(self, commit_id: str, data: bytes):
        if not data or not isinstance(data, bytes):
            raise Exception("Unwilling to persist invalid data.")

        self.redis.hset(self.repository_id, commit_id, data)
        self.redis.hset(
            "{}:time".format(self.repository_id), commit_id, str(datetime.now())
        )

    def dump(self) -> list:
        return self.redis.hgetall(self.repository_id)

    @staticmethod
    def list_repositories(config: dict) -> frozenset:
        redis = RedisAdapter._build_redis(config)
        return redis.smembers("ccguardrepositories")


def determine_parent_commit(
    db_commits: frozenset, iter_callable: Callable
) -> Optional[str]:
    for commits_chunk in iter_callable():
        for commit in commits_chunk:
            if commit in db_commits:
                return commit
    return None


def persist(
    repo_adapter: GitAdapter, reference_adapter: ReferenceAdapter, report_file: str
):
    with open(report_file, "rb") as fd:
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
    parser.add_argument(
        "--tolerance",
        type=int,
        dest="tolerance",
        help="Define a tolerance (percentage).",
    )

    parser.add_argument(
        "--hard-minimum",
        type=int,
        dest="hard_minimum",
        help="Define a hard miniùum threshold (percentage).",
    )

    return parser.parse_args(args)


def adapter_factory(adapter, config):
    if adapter:
        if adapter == "sqlite":
            adapter_class = SqliteAdapter
        if adapter == "redis":
            adapter_class = RedisAdapter
        if adapter == "web":
            adapter_class = WebAdapter

        if adapter_class:
            return adapter_class

    if config.get("adapter.class", None) == "redis":
        adapter_class = RedisAdapter
    elif config.get("adapter.class", None) == "web":

        adapter_class = WebAdapter
    else:
        adapter_class = SqliteAdapter

    return adapter_class


def iter_callable(git, ref):
    def call():
        return git.iter_git_commits([ref])

    return call


def print_cc_report(challenger: Cobertura, report_file=None, log_function=print):
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

    if report_file and report_file.endswith("html"):
        report = HtmlReporter(challenger)
        with open(report_file, "w") as ccfile:
            ccfile.write(report.generate())


def has_better_coverage(diff: CoberturaDiff, tolerance=0, hard_minimum=-1) -> bool:
    if diff.has_better_coverage():
        return True

    challenger_files = set(diff.cobertura2.files())
    reference_files = set(diff.cobertura1.files())
    reference_rate = diff.cobertura1.line_rate()
    ret = True

    # new files should have a line rate at least equal to the reference line rate..
    # ..minus the tolerance..
    # ..but always greater than the hard minimum, if any
    for fi in challenger_files.difference(reference_files):
        if diff.cobertura2.line_rate(fi) < reference_rate - tolerance:
            message = (
                "File {} has a line rate ({:.2f}) "
                "inferior than the reference line rate ({:.2f})"
            ).format(fi, diff.cobertura2.line_rate(fi), reference_rate)
            if tolerance:
                message += "minus the tolerance ({:.2f})".format(tolerance)
            logging.warning(message)
            ret = False
        if hard_minimum >= 0 and diff.cobertura2.line_rate(fi) < hard_minimum:
            logging.warning(
                "File %s has a line rate (%.2f) inferior than "
                "the hard minimum (%.2f)",
                fi,
                diff.cobertura2.line_rate(fi),
                hard_minimum,
            )
            ret = False

    # existing files shoudl have a line rate at least equal to their past line rate..
    # ..minus the tolerance..
    # ..but always greater than the hard minimum, if any
    for fi in challenger_files.intersection(reference_files):
        if diff.cobertura2.line_rate(fi) < diff.cobertura1.line_rate(fi) - tolerance:
            message = (
                "File {} has a line rate ({:.2f}) "
                "inferior than its past line rate ({:.2f})"
            ).format(fi, diff.cobertura2.line_rate(fi), diff.cobertura1.line_rate(fi))
            if tolerance:
                message += "minus the tolerance ({:.2f})".format(tolerance)

            logging.warning(message)
            ret = False
        if hard_minimum >= 0 and diff.cobertura2.line_rate(fi) < hard_minimum:
            logging.warning(
                "File %s has a line rate (%.2f) inferior than "
                "the hard minimum (%.2f)",
                fi,
                diff.cobertura2.line_rate(fi),
                hard_minimum,
            )
            ret = False

    return ret


def print_diff_message(
    diff: CoberturaDiff, log_function=print, has_coverage_improved=False
):
    if has_coverage_improved:
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


def print_delta_report(reference, challenger, log_function=print, report_file=None):
    delta = TextReporterDelta(reference, challenger)
    log_function(delta.generate())

    if report_file and report_file.endswith(".html"):
        delta = HtmlReporterDelta(reference, challenger)
        with open(report_file, "w") as diff_file:
            diff_file.write(delta.generate())


def detect_source(report, repository_path="."):
    if repository_path != ".":
        return repository_path

    xml = ET.parse(report).getroot()
    paths = xml.xpath("/coverage/sources/source/text()")
    logging.debug("detected as paths:")
    for path in paths:
        logging.debug("- %s", path)

    return next(iter(paths))


def main():
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    git = GitAdapter(args.repository)
    repository_id = git.get_repository_id()

    source = detect_source(args.report, args.repository)

    diff, reference = None, None
    challenger = Cobertura(args.report, source=source)

    config = configuration(args.repository)

    with adapter_factory(args.adapter, config)(repository_id, config) as adapter:
        reference_commits = adapter.get_cc_commits()
        logging.debug("Found the following reference commits: %r", reference_commits)

        common_ancestor = git.get_common_ancestor(args.target_branch)

        ref = common_ancestor if args.uncommitted else "{}^".format(common_ancestor)

        commit_id = determine_parent_commit(reference_commits, iter_callable(git, ref))

        if commit_id:
            logging.info("Retrieving data for reference commit %s.", commit_id)
            cc_reference_data = adapter.retrieve_cc_data(commit_id)
            logging.debug("Reference data: %r", cc_reference_data)
            if cc_reference_data:
                reference_fd = io.BytesIO(cc_reference_data)
                reference = Cobertura(reference_fd, source=source)
                diff = CoberturaDiff(reference, challenger)
            else:
                logging.error("No data for the selected reference.")
        else:
            logging.warning("No reference code coverage data found.")

        if challenger:
            print_cc_report(challenger, report_file="cc.html" if args.html else None)

            if not args.uncommitted:
                persist(git, adapter, args.report)
        else:
            logging.error("No recent code coverage data found.")

    tolerance = args.tolerance or config.get("threshold.tolerance", 0)
    hard_minimum = args.hard_minimum or config.get("threshold.hard-minimum", -1)
    hard_minimum = hard_minimum * 1.0 / 100

    if diff:
        has_coverage_improved = has_better_coverage(
            diff, tolerance=tolerance, hard_minimum=hard_minimum
        )

        print_diff_message(diff, has_coverage_improved=has_coverage_improved)

        print_delta_report(
            reference, challenger, report_file="diff.html" if args.html else None
        )

        if not has_coverage_improved:
            exit(255)


if __name__ == "__main__":
    main()
