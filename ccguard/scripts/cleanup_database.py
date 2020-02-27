import argparse
import logging
import sqlite3
import os


def _update_lts(conn, repository_id, commit_id, path):
    query = (
        "UPDATE timestamped_coverage_{repository_id} "
        "SET lts = 1, coverage_data = '{path}' "
        "WHERE commit_id = '{commit_id}';"
    ).format(repository_id=repository_id, path=path, commit_id=commit_id)
    try:
        conn.execute(query)
        conn.commit()
    except sqlite3.IntegrityError:
        logging.warning("Unable to update the commit lts.")


def _retrieve_commit_data(conn, repository_id, commit_id):
    query = 'SELECT coverage_data FROM timestamped_coverage_{repository_id}\
            WHERE commit_id="{commit_id}"'.format(
        repository_id=repository_id, commit_id=commit_id
    )

    result = conn.execute(query).fetchone()

    if result:
        return next(iter(result))
    return None


def cleanup_database(dbpath, dry_run=True):
    print("Processing database {}".format(dbpath))
    conn = sqlite3.connect(dbpath)
    all_repositories = (
        "SELECT name, sql FROM sqlite_master "
        'WHERE type="table" AND name LIKE "timestamped_coverage_%"'
    )

    tables = conn.execute(all_repositories).fetchall()

    for table, sql in tables:
        repository_id = table.lstrip("timestamped_coverage_")
        query = (
            "SELECT commit_id, length(coverage_data) "
            "FROM {} WHERE lts=0 and count = (select min(count) from {})"
        ).format(table, table)
        commits_len = conn.execute(query).fetchall()
        candidates = {commit: length for commit, length in commits_len}
        total_bytes = sum(candidates.values())
        candidates_no = len(candidates.keys())
        print(
            "Repository {}: {} candidates, for a total of {} bytes".format(
                repository_id, candidates_no, total_bytes,
            )
        )
        for candidate in candidates.keys():
            path = os.path.abspath(
                ".ccguard-lts/{repository_id}/{commit_id}/coverage.xml".format(
                    repository_id=repository_id, commit_id=candidate
                )
            )

            if dry_run:
                print("Would have copied {} data to {}".format(candidate, path))
                continue

            data = _retrieve_commit_data(conn, repository_id, candidate)
            os.mkdir(os.path.dirname(path))
            with open(path, "wb") as dest:
                dest.write(data)
            _update_lts(conn, repository_id, candidate, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Maintenance scripts for the given SQLite database.")
    )

    parser.add_argument(
        "dbpath", help="The SQLite database to maintain",
    )
    parser.add_argument(
        "--dry-run",
        help="Should we apply destructive operations?",
        dest="dry_run",
        action="store_true",
    )
    args = parser.parse_args()
    cleanup_database(args.dbpath, args.dry_run)
