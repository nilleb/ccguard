import argparse
import sqlite3
import lxml.etree as ET


def _get_line_coverage(data: bytes) -> (float, int, int):
    try:
        tree = ET.fromstring(data)
        return {
            "line_rate": float(tree.get("line-rate", 0.0)),
            "lines_covered": int(tree.get("lines-covered", 0)),
            "lines_valid": int(tree.get("lines-valid", 0)),
        }
    except ET.XMLSyntaxError:
        return 0.0, 0, 0


def _alter_table(conn, new_columns, table, sql):
    for name, ctype, default in new_columns:
        if name not in sql:
            print("Adding {} {} DEFAULT {}".format(name, ctype, default))
            ddl = "ALTER TABLE {} ADD COLUMN `{}` {} DEFAULT {}".format(
                table, name, ctype, default
            )
            conn.execute(ddl)


def _update_data(conn, table):
    query = "SELECT commit_id, coverage_data " "FROM {} where line_rate = 0.0".format(
        table
    )
    rows = conn.execute(query).fetchall()
    for row in rows:
        commit, data = row
        data_tuple = _get_line_coverage(data)
        update = (
            "UPDATE {table} "
            "SET line_rate = {line_rate}, "
            "lines_covered = {lines_covered}, "
            "lines_valid = {lines_valid} "
            'WHERE commit_id = "{commit}";'
        ).format(**data_tuple, table=table, commit=commit)

        print(
            "{} {line_rate} {lines_covered} {lines_valid}".format(commit, **data_tuple)
        )
        cursor = conn.execute(update)
        conn.commit()
        cursor.close()


def migration_steps_03_04(conn):
    all_repositories = (
        "SELECT name, sql FROM sqlite_master "
        'WHERE type="table" AND name LIKE "timestamped_coverage_%"'
    )

    tables = conn.execute(all_repositories).fetchall()

    new_columns = [
        ("count", "INT", "1"),
        ("line_rate", "REAL", "0.0"),
        ("lts", "INTEGER", "0"),
        ("lines_covered", "INTEGER", "0"),
        ("lines_valid", "INTEGER", "0"),
    ]

    for table, sql in tables:
        print("Processing table {}".format(table))
        _alter_table(conn, new_columns, table, sql)
        _update_data(conn, table)
        conn.commit()


def migrate_03_04(dbpath):
    print("Migrating database {}".format(dbpath))
    try:
        conn = sqlite3.connect(dbpath)
        migration_steps_03_04(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Maintenance scripts for the given SQLite database.")
    )

    parser.add_argument(
        "dbpath", help="The SQLite database to maintain",
    )
    args = parser.parse_args()
    migrate_03_04(args.dbpath)
