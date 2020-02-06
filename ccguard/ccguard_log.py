# -*- coding: utf-8 -*-
import git
import argparse
import ccguard
import logging
from xml.etree import ElementTree


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

    return parser.parse_args(args)


def main():
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config = ccguard.configuration(args.repository)
    adapter_class = ccguard.adapter_factory(args.adapter, config)

    for ac in detailed_references(
        repo_folder=args.repository, limit=args.limit, adapter_class=adapter_class
    ):
        print(ac)


if __name__ == "__main__":
    main()
