# -*- coding: utf-8 -*-
import io
import git
import argparse
import ccguard
import logging
from xml.etree import ElementTree
from pycobertura import Cobertura
from pycobertura.reporters import HtmlReporter, HtmlReporterDelta


def dump(repo_folder=".", adapter_class=ccguard.SqliteAdapter):
    config = ccguard.configuration(repo_folder)
    repo_id = ccguard.GitAdapter(repo_folder).get_repository_id()
    with adapter_class(repo_id, config) as adapter:
        return adapter.dump()


def list_references(repo_folder=".", adapter_class=ccguard.SqliteAdapter):
    config = ccguard.configuration(repo_folder)
    repo_id = ccguard.GitAdapter(repo_folder).get_repository_id()
    with adapter_class(repo_id, config) as adapter:
        return adapter.get_cc_commits()


class AnnotatedCommit(git.Commit):
    def __init__(self, commit, data):
        self.commit = commit
        self.has_ref = bool(data)
        if data:
            tree = ElementTree.fromstring(data)
            self.ccrate = float(tree.get("line-rate"))

    @property
    def shortsha(self):
        return self.commit.hexsha[:7]

    @property
    def message(self):
        return next(iter(self.commit.message.split("\n")))[:70]

    @property
    def ccrate_pretty(self):
        if self.has_ref:
            return "({:.2f}%) ".format(self.ccrate * 100)
        else:
            return "{:9}".format("")

    @property
    def pretty(self):
        return "{}  {}{} {}".format(
            "✅" if self.has_ref else "❌",
            self.ccrate_pretty,
            self.shortsha,
            self.message,
        )

    def __str__(self):
        return self.pretty

    def __repr__(self):
        return self.pretty


def detailed_references(repo_folder=".", limit=30, adapter_class=ccguard.SqliteAdapter):
    repo = git.Repo(repo_folder, search_parent_directories=True)
    dumps = dump(repo_folder=repo_folder, adapter_class=adapter_class)
    references = {ref: data for ref, data in dumps}
    logging.debug(references)

    def enrich_commit(commit):
        logging.debug(commit.hexsha)
        return AnnotatedCommit(commit, references.get(commit.hexsha, None))

    return [
        enrich_commit(repo.commit(logEntry))
        for logEntry in list(repo.iter_commits())[:limit]
    ]


def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Display ccguard reference log.")

    parser.add_argument(
        "commit_id",
        nargs="*",
        help=(
            "Specify one commit ID to display the corresponding coverage report, "
            "two commit IDs to inspect their diff coverage"
        ),
    )
    parser.add_argument(
        "--adapter-class",
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
        "-n",
        dest="limit",
        help="limit the log to this number of commits",
        type=int,
        default=30,
    )
    parser.add_argument(
        "--repository", dest="repository", help="the repository to analyze", default="."
    )
    parser.add_argument(
        "--report-file",
        dest="report_file",
        help="the file that will contain the report",
    )

    return parser.parse_args(args)


def print_diff_report(first_ref, second_ref, adapter, repository=".", pattern=None):
    dest = (pattern or "diff-{}-{}.html").format(first_ref, second_ref)
    fdata = adapter.retrieve_cc_data(first_ref)
    sdata = adapter.retrieve_cc_data(second_ref)
    first_fd = io.BytesIO(fdata)
    second_fd = io.BytesIO(sdata)
    source = ccguard.detect_source(first_fd, repository)
    print(
        "Printing the diff report for the commits {} and {} to {}".format(
            first_ref, second_ref, dest
        )
    )
    fcc = Cobertura(first_fd, source=source)
    scc = Cobertura(second_fd, source=source)
    delta = HtmlReporterDelta(fcc, scc)
    with open(dest, "w") as diff_file:
        diff_file.write(delta.generate())


def print_report(commit_id, adapter, repository=".", pattern=None):
    dest = (pattern or "cc-{}.html").format(commit_id)
    print(
        "Printing the coverage report for the commit {} to {}".format(commit_id, dest)
    )

    data = adapter.retrieve_cc_data(commit_id)
    reference_fd = io.BytesIO(data)
    source = ccguard.detect_source(reference_fd, repository)
    fdata = Cobertura(reference_fd, source=source)
    report = HtmlReporter(fdata)
    with open(dest, "w") as ccfile:
        ccfile.write(report.generate())


def main():
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config = ccguard.configuration(args.repository)
    adapter_class = ccguard.adapter_factory(args.adapter, config)

    if args.commit_id:
        first, second = None, None

        if len(args.commit_id) == 1:
            first = args.commit_id[0]
        else:
            first, second, *_ = args.commit_id

        config = ccguard.configuration(args.repository)
        repo_id = ccguard.GitAdapter(args.repository).get_repository_id()
        with adapter_class(repo_id, config) as adapter:
            refs = adapter.get_cc_commits()
            first_ref, second_ref = None, None

            for ref in refs:
                if first and ref.startswith(first):
                    first_ref = ref
                if second and ref.startswith(second):
                    second_ref = ref

            if first_ref and second_ref:
                print_diff_report(
                    first_ref,
                    second_ref,
                    adapter=adapter,
                    repository=args.repository,
                    pattern=args.report_file,
                )

            elif first_ref:
                print_report(
                    first_ref,
                    adapter=adapter,
                    repository=args.repository,
                    pattern=args.report_file,
                )
            elif second_ref:
                print_report(
                    second_ref,
                    adapter=adapter,
                    repository=args.repository,
                    pattern=args.report_file,
                )
            else:
                print("Sorry, can't find a matching reference.")
        return

    for ac in detailed_references(
        repo_folder=args.repository, limit=args.limit, adapter_class=adapter_class
    ):
        print(ac)


if __name__ == "__main__":
    main()
