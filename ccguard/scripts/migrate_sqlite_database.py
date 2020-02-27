import argparse
import sqlite3


def migrate_03_04(dbpath):
    print("Migrating database {}".format(dbpath))
    conn = sqlite3.connect(dbpath)
    all_repositories = (
        "SELECT name, sql FROM sqlite_master "
        'WHERE type="table" AND name LIKE "timestamped_coverage_%"'
    )

    tables = conn.execute(all_repositories).fetchall()

    new_columns = [
        ("count", "INT", "1"),
        ("line_rate", "REAL", "0.0"),
        ("lts", "INTEGER", "0"),
    ]
    for table, sql in tables:
        print("Processing table {}".format(table))
        for name, ctype, default in new_columns:
            if name not in sql:
                print("Adding {} {} DEFAULT {}".format(name, ctype, default))
                ddl = "ALTER TABLE {} ADD COLUMN `{}` {} DEFAULT {}".format(
                    table, name, ctype, default
                )
                conn.execute(ddl)
    conn.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Maintenance scripts for the given SQLite database.")
    )

    parser.add_argument(
        "dbpath", help="The SQLite database to maintain",
    )
    args = parser.parse_args()
    migrate_03_04(args.dbpath)
