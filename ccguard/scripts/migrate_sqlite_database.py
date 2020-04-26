import argparse
import re
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
    for name, ctype, default, not_null in new_columns:
        if name == "branch" and name not in sql:
            print(sql)
        if name not in sql:
            default_clause = "DEFAULT {}" if default else ""
            not_null_clause = "NOT NULL" if not_null else ""
            print("Adding {} {} {} {}".format(name, ctype, default_clause, not_null_clause))
            ddl = "ALTER TABLE {} ADD COLUMN `{}` {} {} {}".format(
                table, name, ctype, default_clause, not_null_clause,
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
        ("count", "INT", "1", False),
        ("line_rate", "REAL", "0.0", False),
        ("lts", "INTEGER", "0", False),
        ("lines_covered", "INTEGER", "0", False),
        ("lines_valid", "INTEGER", "0", False),
        ("branch", "VARCHAR(70)", "", False),
    ]

    for table, sql in tables:
        if re.match(".*v[0-9]+$", table):
            print("Skipping table {}".format(table))
            continue
        print("Processing table {}".format(table))
        _alter_table(conn, new_columns, table, sql)
        _update_data(conn, table)
        conn.commit()


def migrate_03_04(dbpath):
    print("Migrating database {} (0.3 to 0.6.2)".format(dbpath))
    try:
        conn = sqlite3.connect(dbpath)
        migration_steps_03_04(conn)
    finally:
        conn.close()

MIGRATE_06_07 = """
BEGIN TRANSACTION;

ALTER TABLE timestamped_coverage_{repository_id} RENAME TO timestamped_coverage_{repository_id}_v0;

CREATE TABLE IF NOT EXISTS `timestamped_coverage_{repository_id}_v1` (
    `commit_id` varchar(40) NOT NULL,
    `type` varchar(40) NOT NULL DEFAULT 'default',
    `branch` varchar(70),
    `collected_at` ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `count` INT DEFAULT 1,
    `lts` INT DEFAULT 0,
    `data` BLOB NOT NULL default '',
    `line_rate` REAL DEFAULT 0.0,
    `lines_covered` INT DEFAULT 0,
    `lines_valid` INT DEFAULT 0,
    PRIMARY KEY  (`commit_id`, `type`)
);

INSERT INTO timestamped_coverage_{repository_id}_v1
    (commit_id, collected_at, count, lts, data,
    line_rate, lines_covered, lines_valid)
SELECT 
    commit_id, collected_at, count, lts, coverage_data,
    line_rate, lines_covered, lines_valid
FROM timestamped_coverage_{repository_id}_v0;

COMMIT;
"""


def migrate_06_07(dbpath):
    print("Migrating database {} (0.6.2 to O.7)".format(dbpath))
    try:
        conn = sqlite3.connect(dbpath)
        migration_steps_06_07(conn)
    finally:
        conn.close()


def migration_steps_06_07(conn):
    all_repositories = (
        "SELECT name, sql FROM sqlite_master "
        'WHERE type="table" AND name LIKE "timestamped_coverage_%"'
    )

    tables = conn.execute(all_repositories).fetchall()

    for table, sql in tables:
        if re.match(".*v[0-9]+$", table):
            print("Skipping table {}".format(table))
            continue
        print("Processing table {}".format(table))
        tokens = table.split("_")[2:]
        if len(tokens) == 1:
            repository_id = tokens[0]
        else:
            limit = -1 if re.match("v[0-9]+", tokens[-1]) else None
            repository_id = "_".join(tokens[:limit])
        instructions = MIGRATE_06_07.format(repository_id=repository_id)
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
    migrate_03_04(args.dbpath)
    migrate_06_07(args.dbpath)
