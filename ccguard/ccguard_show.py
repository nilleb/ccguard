import io
import sys
import argparse
import ccguard
import logging
from pycobertura import Cobertura


def print_report(commit_id, adapter, repository=".", pattern=None, log_function=print):
    dest = (pattern or "cc-{}.html").format(commit_id)
    log_function(
        "Printing the coverage report for the commit {} to {}".format(commit_id, dest)
    )

    data = adapter.retrieve_cc_data(commit_id)
    reference_fd = io.BytesIO(data)
    source = ccguard.GitAdapter(repository).get_root_path()
    fdata = Cobertura(reference_fd, source=source)

    ccguard.print_cc_report(fdata, report_file=dest, log_function=log_function)


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Display a ccguard reference coverage."
    )
    ccguard.parse_common_args(parser)

    parser.add_argument(
        "commit_id",
        help=(
            "Specify one commit ID to display the corresponding coverage report, "
            "two commit IDs to inspect their diff coverage"
        ),
    )

    parser.add_argument(
        "--report-file",
        dest="report_file",
        help="the file that will contain the report",
    )

    return parser.parse_args(args)


def main(args=None, log_function=print):
    args = parse_args(args)

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config = ccguard.configuration(args.repository)
    adapter_class = ccguard.adapter_factory(args.adapter, config)

    config = ccguard.configuration(args.repository)
    repo_id = ccguard.GitAdapter(args.repository).get_repository_id()
    with adapter_class(repo_id, config) as adapter:
        refs = adapter.get_cc_commits()

        first_ref = None
        for ref in refs:
            if ref.startswith(args.commit_id):
                first_ref = ref
                break

        if first_ref:
            print_report(
                first_ref,
                adapter=adapter,
                repository=args.repository,
                pattern=args.report_file,
                log_function=log_function,
            )
        else:
            log_function("fatal: can't find matching references.")
            return -1

    return 0


if __name__ == "__main__":
    sys.exit(main())