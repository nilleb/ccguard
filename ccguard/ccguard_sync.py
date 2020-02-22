import logging
import argparse
import ccguard


def transfer(
    commit_id,
    repo_folder=".",
    source_adapter_class=ccguard.SqliteAdapter,
    dest_adapter_class=ccguard.RedisAdapter,
    log_function=logging.debug,
):
    inner_callable = prepare_inner_callable(commit_id)
    config = ccguard.configuration(repo_folder)
    repo_id = ccguard.GitAdapter(repo_folder).get_repository_id()
    with source_adapter_class(repo_id, config) as source_adapter:
        with dest_adapter_class(repo_id, config) as dest_adapter:
            inner_callable(source_adapter, dest_adapter, log_function=log_function)


def prepare_inner_callable(commit_id):
    inner_callable = None

    if commit_id:

        def inner_callable(source_adapter, dest_adapter, log_function=logging.debug):
            log_function("⌛ Start retrieving data for %s...", commit_id)
            data = source_adapter.retrieve_cc_data(commit_id=commit_id)
            log_function("✅ (%s) data retrieved!", commit_id)
            dest_adapter.persist(commit_id, data)

    else:

        def inner_callable(
            source_adapter: ccguard.ReferenceAdapter,
            dest_adapter: ccguard.ReferenceAdapter,
            log_function=logging.debug,
        ):
            log_function("Start retrieving data...")
            for commit_id in source_adapter.get_cc_commits():
                log_function("⌛ Start retrieving data for %s...", commit_id)
                data = source_adapter.retrieve_cc_data(commit_id)
                log_function("✅ (%s) data retrieved!", commit_id)
                dest_adapter.persist(commit_id, data)

    return inner_callable


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Transfer ccguard reference data from an adapter to another."
    )

    parser.add_argument(
        "source_adapter", help="Choose the adapter to use (choices: sqlite or redis)",
    )
    parser.add_argument(
        "dest_adapter", help="Choose the adapter to use (choices: sqlite or redis)",
    )
    parser.add_argument(
        "--repository", dest="repository", help="the repository to analyze", default="."
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        help="whether to print debug messages",
        action="store_true",
    )
    parser.add_argument(
        "--commit_id", dest="commit_id", help="Limit the transfer to this commit only",
    )

    return parser.parse_args(args)


def main(args=None, log_function=logging.debug):
    args = parse_args(args)

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config = ccguard.configuration(args.repository)
    source_class = ccguard.adapter_factory(args.source_adapter, config)
    dest_class = ccguard.adapter_factory(args.dest_adapter, config)

    transfer(
        args.commit_id,
        repo_folder=args.repository,
        source_adapter_class=source_class,
        dest_adapter_class=dest_class,
        log_function=log_function,
    )


if __name__ == "__main__":
    main()
