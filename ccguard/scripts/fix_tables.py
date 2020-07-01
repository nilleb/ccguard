import argparse
import re
import sqlite3
import lxml.etree as ET




def migrate_07_071(dbpath):
    print("Migrating database {} (0.6.2 to O.7)".format(dbpath))
    try:
        conn = sqlite3.connect(dbpath)
        migration_steps_07_071(conn)
    finally:
        conn.close()


def migration_steps_07_071(conn):
    all_repositories = (
        "SELECT name, sql FROM sqlite_master "
        'WHERE type="table" AND name LIKE "timestamped_coverage_%"'
    )

    MIGRATE_07_071 = """UPDATE timestamped_coverage_{repository_id}_v1 SET branch = trim(branch, "
");
"""
    tables = conn.execute(all_repositories).fetchall()

    for table, sql in tables:
        if not re.match(".*v1$", table):
            print("Skipping table {}".format(table))
            continue
        print("Processing table {}".format(table))
        tokens = table.split("_")[2:]
        if len(tokens) == 1:
            repository_id = tokens[0]
        else:
            limit = -1 if re.match("v[0-9]+", tokens[-1]) else None
            repository_id = "_".join(tokens[:limit])
        instructions = MIGRATE_07_071.format(repository_id=repository_id)
        conn.executescript(instructions)
        conn.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Maintenance scripts for the given SQLite database.")
    )
    parser.add_argument(
        "dbpath", help="The SQLite database to maintain",
    )
    args = parser.parse_args()
    migrate_07_071(args.dbpath)
