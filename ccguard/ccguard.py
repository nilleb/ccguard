#! /usr/bin/env python3

import io
import argparse
import json
import logging
import sys
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
from contextlib import contextmanager
from pycobertura import Cobertura, CoberturaDiff, TextReporterDelta, TextReporter
from pycobertura.reporters import HtmlReporter, HtmlReporterDelta
from pycobertura.filesystem import FileSystem


HOME = Path.home()
DB_FILE_NAME = ".ccguard.db"
CONFIG_FILE_NAME = ".ccguard.config.json"

KNOWN_ADAPTERS = {
    "web": "WebAdapter",
    "redis": "RedisAdapter",
    "sqlite": "SqliteAdapter",
    "default": "SqliteAdapter",
}


DEFAULT_CONFIGURATION = {
    "redis.host": "localhost",
    "redis.port": 6379,
    "redis.db": 0,
    "redis.password": None,
    "ccguard.server.address": "http://127.0.0.1:5000",
    "threshold.tolerance": 0,
    "threshold.hard-minimum": -1,
    "sqlite.dbpath": HOME.joinpath(DB_FILE_NAME),
    "known.adapters": KNOWN_ADAPTERS,
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
    logging.debug("Executing %s in %s", command, working_folder)

    try:
        output = subprocess.check_output(shlex.split(command), cwd=working_folder)
        return output.decode("utf-8")
    except OSError:
        logging.error("Command being executed: {}".format(command))
        raise


class GitFileSystem(FileSystem):
    def __init__(self, repo_folder, commit_id=None):
        self.repository = repo_folder
        self.commit_id = commit_id
        self.repository_root = GitAdapter(repo_folder).get_root_path()
        self.prefix = self.repository.replace(self.repository_root, "").lstrip("/")

    def real_filename(self, filename):
        prefix = "{}/".format(self.prefix) if self.prefix else ""
        return "{p.commit_id}:{prefix}{filename}".format(
            prefix=prefix, p=self, filename=filename
        )

    def has_file(self, filename):
        command = "git --no-pager show {}".format(self.real_filename(filename))
        return_code = subprocess.call(
            command,
            cwd=self.repository,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logging.debug("%s: %d", command, return_code)
        return not bool(return_code)

    @contextmanager
    def open(self, filename):
        """
        Yield a file-like object for file `filename`.

        This function is a context manager.
        """
        filename = self.real_filename(filename)

        try:
            output = get_output(
                "git --no-pager show {}".format(filename), self.repository
            )
        except Exception:
            raise self.FileNotFound(filename)

        yield io.StringIO(output)


class VersionedCobertura(Cobertura):
    def __init__(self, report, source=None, commit_id=None):
        super().__init__(report, source=source)
        if source is None:
            if isinstance(report, str):
                # get the directory in which the coverage file lives
                source = os.path.dirname(report)
        self.filesystem = GitFileSystem(source, commit_id=commit_id)


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

    def get_common_ancestor(self, base_branch="origin/master", ref="HEAD"):
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
        commits_query = (
            "SELECT commit_id "
            "FROM timestamped_coverage_{repository_id} "
            "ORDER BY collected_at DESC"
        ).format(repository_id=self.repository_id)
        return frozenset(
            c for ct in self.conn.execute(commits_query).fetchall() for c in ct
        )

    def _update_lts(self, commit_id, path):
        query = (
            "UPDATE timestamped_coverage_{repository_id} "
            "SET lts = 1, coverage_data = '{path}' "
            "WHERE commit_id = '{commit_id}';"
        ).format(repository_id=self.repository_id, commit_id=commit_id, path=path)
        self.conn.execute(query)
        self.conn.commit()

    def retrieve_cc_data(self, commit_id: str) -> Optional[bytes]:
        query = 'SELECT coverage_data, lts FROM timestamped_coverage_{repository_id}\
                WHERE commit_id="{commit_id}"'.format(
            repository_id=self.repository_id, commit_id=commit_id
        )

        self._update_count(commit_id)

        result = self.conn.execute(query).fetchall()

        if result:
            data, lts = next(iter(result))
            if lts == 0:
                return data
            else:
                with open(data, "rb") as fd:
                    return fd.read()
        return None

    def _update_count(self, commit_id):
        query = (
            "UPDATE timestamped_coverage_{repository_id} "
            "SET count = count + 1 WHERE commit_id = '{commit_id}';"
        ).format(repository_id=self.repository_id, commit_id=commit_id)
        try:
            self.conn.execute(query)
            self.conn.commit()
        except sqlite3.IntegrityError:
            logging.warning("Unable to update the commit count.")

    def _get_line_rate(self, data: bytes) -> float:
        try:
            tree = ET.fromstring(data)
            return float(tree.get("line-rate", 0.0))
        except ET.XMLSyntaxError:
            return 0.0

    def persist(self, commit_id: str, data: bytes):
        if not data or not isinstance(data, bytes):
            raise ValueError("Unwilling to persist invalid data.")

        query = (
            "INSERT INTO timestamped_coverage_{repository_id} "
            "(commit_id, coverage_data, line_rate) VALUES (?, ?, ?) "
        ).format(repository_id=self.repository_id)
        data_tuple = (commit_id, data, self._get_line_rate(data))
        try:
            self.conn.execute(query, data_tuple)
            self.conn.commit()
        except sqlite3.IntegrityError:
            logging.debug("This commit seems to have already been recorded.")

    def dump(self) -> list:
        query = """SELECT commit_id, coverage_data
        FROM timestamped_coverage_{repository_id}
        ORDER BY collected_at DESC""".format(
            repository_id=self.repository_id
        )
        return self.conn.execute(query).fetchall()

    def _create_table(self):
        ddl = (
            "CREATE TABLE IF NOT EXISTS `timestamped_coverage_{repository_id}` ("
            "`commit_id` varchar(40) NOT NULL, "
            "`collected_at` ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "`count` INT DEFAULT 1, "
            "`line_rate` REAL DEFAULT 0.0, "
            "`lts` INT DEFAULT 0, "
            "`coverage_data` BLOB NOT NULL default '', "
            "PRIMARY KEY  (`commit_id`) );"
        )
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
        return r.content

    def persist(self, commit_id: str, data: bytes):
        if not data or not isinstance(data, bytes):
            raise ValueError("Unwilling to persist invalid data.")

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
        references = requests.get(
            "{p.server}/api/v1/references/{p.repository_id}/all".format(p=self)
        )
        if references.ok:
            logging.debug("References: \n%r", references)
            data = {
                commit_id: self.retrieve_cc_data(commit_id)
                for commit_id in references.json()[:30]
            }
            return data.items()

        logging.error("Unexpected failure on dump: %s", references.text)
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
            raise ValueError("Unwilling to persist invalid data.")

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


def parse_common_args(parser=None):
    if not parser:
        parser = argparse.ArgumentParser(
            description=(
                "You can only improve! Compare Code Coverage and prevent regressions."
            )
        )

    parser.add_argument(
        "--adapter",
        help="Choose the adapter to use (choices: sqlite or redis)",
        dest="adapter",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        help="whether to print debug messages",
        action="store_true",
    )
    parser.add_argument(
        "--repository", dest="repository", help="the repository to analyze", default="."
    )

    return parser


def parse_args(args=None, parser=None):
    if not parser:
        parser = argparse.ArgumentParser(
            description=(
                "You can only improve! Compare Code Coverage and prevent regressions."
            )
        )

    parse_common_args(parser)

    parser.add_argument("report", help="the coverage report for the current commit ID")
    parser.add_argument(
        "--target-branch",
        dest="target_branch",
        help="the branch to which this code will be merged (default: master)",
        default="origin/master",
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


def str_to_class(classname):
    return getattr(sys.modules[__name__], classname)


def adapter_factory(adapter: str, config: dict) -> ReferenceAdapter:
    selected = adapter or config.get("adapter.class", None) or "default"
    return str_to_class(KNOWN_ADAPTERS[selected])


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

    # existing files should have a line rate at least equal to their past line rate..
    # ..minus the tolerance..
    # ..but always greater than the hard minimum, if any
    for fi in challenger_files.intersection(reference_files):
        if not diff.diff_total_misses(fi) and diff.diff_total_statements(fi) < 0:
            logging.debug(
                "Skipping %s, because of its number of missing statements.", fi
            )
            continue
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


def print_delta_report(reference, challenger, report_file=None, log_function=print):
    delta = TextReporterDelta(reference, challenger)
    log_function(delta.generate())

    if report_file and report_file.endswith(".html"):
        delta = HtmlReporterDelta(reference, challenger)
        with open(report_file, "w") as diff_file:
            diff_file.write(delta.generate())


def normalize_report_paths(report, repository_root):
    tree = ET.parse(report)
    xml = tree.getroot()

    if xml.xpath('/coverage/sources/source[@class="ccguard-meta-sources-root"]'):
        logging.debug("The report has already been processed.")
        return None

    _normalize_report_paths(xml, repository_root)

    return tree


def guess_relative_path(repository_root, abs_file_path, prefix=None):
    best_hypothesis_with_prefix = None

    if prefix:
        best_hypothesis_with_prefix = str(abs_file_path).replace(prefix, "").lstrip("/")
        guess = Path(repository_root).joinpath(best_hypothesis_with_prefix)
        if guess.exists():
            logging.debug(
                "The prefix %s is good, hence the best guess is %s.",
                prefix,
                best_hypothesis_with_prefix,
            )
            return prefix, best_hypothesis_with_prefix

    parts = str(abs_file_path).lstrip("/").split("/")
    relative_file_path = ""

    for part in parts[::-1]:
        relative_file_path = (
            part + "/" + relative_file_path if relative_file_path else part
        )
        guess = Path(repository_root).joinpath(relative_file_path)
        logging.warning(guess)
        if guess.exists():
            logging.debug("We have a good guess at %s", guess)
            prefix = str(abs_file_path).replace(relative_file_path, "").rstrip("/")
            return prefix, relative_file_path

    logging.debug("No valid guesses for %s", abs_file_path)
    return prefix, best_hypothesis_with_prefix


def _normalize_report_paths(xml, repository_root):
    sources = xml.xpath("/coverage/sources/source/text()")
    classes = xml.xpath("packages/package/classes/class")

    prefix = None
    for klass in classes:
        filename = klass.attrib["filename"]
        possible_paths = [
            Path(source).joinpath(filename)
            for source in sources
            if Path(source).joinpath(filename).exists()
        ]

        if not possible_paths:
            logging.warning(
                "The file %s is not anymore present. Its path will be guessed.",
                filename,
            )
            # should check the VersionedCobertura GitFileSystem
            possible_paths = [Path(source).joinpath(filename) for source in sources]

        abs_file_path = next(iter(possible_paths))

        if str(abs_file_path).startswith(repository_root):
            rel = str(abs_file_path).replace(repository_root, "").lstrip("/")
            logging.debug("%s -> %s (%s)", abs_file_path, rel, repository_root)
            klass.attrib["filename"] = rel
        else:
            logging.debug("The report has been collected somewhere else.")
            prefix, rel = guess_relative_path(repository_root, abs_file_path, prefix)
            if rel:
                klass.attrib["filename"] = rel

    sources_elem = xml.xpath("/coverage/sources")
    source_xml = '<source class="ccguard-meta-sources-root">{}</source>'.format(
        repository_root
    )
    if sources_elem:
        sources_elem[0].append(ET.XML(source_xml))
    else:
        xml.append(ET.XML("<sources>{}</sources>".format(source_xml)))
    return xml


def main(args=None, log_function=print, logging_module=logging):
    args = parse_args(args)

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    git = GitAdapter(args.repository)
    repository_id = git.get_repository_id()

    source = git.get_root_path()
    tree = normalize_report_paths(args.report, source)
    tree.write(args.report)

    diff, reference = None, None
    challenger = Cobertura(args.report, source=source)

    config = configuration(args.repository)

    with adapter_factory(args.adapter, config)(repository_id, config) as adapter:
        reference_commits = adapter.get_cc_commits()
        logging_module.debug(
            "Found the following reference commits: %r", reference_commits
        )

        common_ancestor = git.get_common_ancestor(args.target_branch)
        current_commit_id = git.get_current_commit_id()

        if common_ancestor == current_commit_id and not args.uncommitted:
            ref = "{}^".format(common_ancestor)
        else:
            ref = common_ancestor

        commit_id = determine_parent_commit(reference_commits, iter_callable(git, ref))

        if commit_id:
            logging_module.info("Retrieving data for reference commit %s.", commit_id)
            cc_reference_data = adapter.retrieve_cc_data(commit_id)
            logging_module.debug("Reference data: %r", cc_reference_data)
            if cc_reference_data:
                reference_fd = io.BytesIO(cc_reference_data)
                normalize_report_paths(reference_fd, source)
                reference_fd.seek(0, 0)
                reference = VersionedCobertura(
                    reference_fd, source=source, commit_id=commit_id
                )
                diff = CoberturaDiff(reference, challenger)
            else:
                logging_module.error("No data for the selected reference.")
        else:
            logging_module.warning("No reference code coverage data found.")

        if challenger:
            print_cc_report(challenger, report_file="cc.html" if args.html else None)

            if not args.uncommitted:
                persist(git, adapter, args.report)
        else:
            logging_module.error("No recent code coverage data found.")

    if diff:
        tolerance = args.tolerance or config.get("threshold.tolerance", 0)
        hard_minimum = args.hard_minimum or config.get("threshold.hard-minimum", -1)
        hard_minimum = hard_minimum * 1.0 / 100

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
