import io
import argparse
import ccguard
import logging
from pycobertura import Cobertura


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
    ccguard.print_delta_report(fcc, scc, report_file=dest)


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Display diff between two ccguard reference coverages."
    )
    ccguard.parse_common_args(args, parser)

    parser.add_argument(
        "commit_id",
        nargs="*",
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


def main(args=None):
    args = parse_args(args)

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config = ccguard.configuration(args.repository)
    adapter_class = ccguard.adapter_factory(args.adapter, config)

    try:
        first, second = args.commit_id
    except ValueError:
        logging.error("fatal: insufficient arguments")
        return

    config = ccguard.configuration(args.repository)
    repo_id = ccguard.GitAdapter(args.repository).get_repository_id()

    with adapter_class(repo_id, config) as adapter:
        refs = adapter.get_cc_commits()
        first_ref, second_ref = None, None

        for ref in refs:
            if first_ref and second_ref:
                logging.info("Building diff between %s and %s", first_ref, second_ref)
                break
            if ref.startswith(first):
                first_ref = ref
            if ref.startswith(second):
                second_ref = ref

        if first_ref and second_ref:
            print_diff_report(
                first_ref,
                second_ref,
                adapter=adapter,
                repository=args.repository,
                pattern=args.report_file,
            )
        else:
            print("fatal: can't find matching references.")

    return
