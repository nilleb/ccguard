import argparse
import datetime
import hashlib
import io
import logging
import socket
import sqlite3
import threading

import flask
import lxml
import requests
from flask import abort, jsonify, request
from pycobertura import Cobertura
from pycobertura.reporters import HtmlReporter, HtmlReporterDelta

import ccguard

app = flask.Flask(__name__)
app.config["DEBUG"] = True


def authenticated(func):
    def inner(*args, **kwargs):
        halt = check_auth()
        if halt:
            abort(*halt)
        return func(*args, **kwargs)

    # Renaming the function name:
    inner.__name__ = func.__name__
    return inner


def check_auth():
    token = app.config.get("TOKEN", None)
    if token:
        auth = request.headers.get("authorization", None)
        if not auth:
            return (401, "Authentication required")
        if auth != token:
            return (403, "Forbidden")


@app.route("/", methods=["GET"])
def home():
    return (
        "<h1>CCGuard Server</h1>"
        '<p>The <a href="{}">CCGuard</a> prototype API.</p>'
        "<p>CCGuard allows you to upload code coverage reports, "
        "list and download the past reports.</p>"
        '<p>Please read <a href="{}">the documentation</a> about '
        "how to setup your CircleCI workflow.</p>"
        "<p>Contact the owner of this server (me at nilleb dot com) "
        "in order to get an access token.</p>"
    ).format(
        "https://github.com/nilleb/ccguard",
        "https://github.com/nilleb/ccguard/blob/master/"
        "docs/how%20to%20integrate%20ccguard%20in%20your%20CircleCI%20job.md",
    )


class SqliteServerAdapter(object):
    def __init__(self, config):
        config = config or ccguard.configuration()
        dbpath = str(config.get("sqlite.dbpath"))
        logging.debug(dbpath)
        self.conn = sqlite3.connect(dbpath)
        self._create_table()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.conn.close()

    def _create_table(self):
        statement = (
            "CREATE TABLE IF NOT EXISTS `ccguard_server_stats` ("
            "`ip` varchar(40) NOT NULL, "
            "`collected_at` ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "`repositories_count` INT DEFAULT 0, "
            "`commits_count` INT DEFAULT 0, "
            "`last_updated` ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY  (`ip`) );"
        )
        self.conn.execute(statement)

    def record(self, data: dict):
        if not data or not isinstance(data, dict) or "ip" not in data:
            raise ValueError("Unwilling to persist invalid data.")

        statement = (
            "INSERT INTO ccguard_server_stats "
            "(ip, repositories_count, commits_count) VALUES (?, ?, ?)"
        )
        data_tuple = (
            data["ip"],
            data.get("repositories_count", 0),
            data.get("commits_count", 0),
        )
        try:
            self.conn.execute(statement, data_tuple)
            self.conn.commit()
        except sqlite3.IntegrityError:
            logging.exception("This IP seems to have already been recorded.")
            statement = (
                "UPDATE ccguard_server_stats "
                f'SET repositories_count = {data["repositories_count"]}, '
                f'commits_count = {data["commits_count"]}, '
                f'last_updated = "{datetime.datetime.now()}" '
                f'WHERE ip = "{data["ip"]}"'
            )
            logging.debug(statement)
            self.conn.execute(statement)
            self.conn.commit()

    def totals(self) -> dict:
        query = (
            "SELECT count(*), sum(repositories_count), sum(commits_count) "
            "FROM ccguard_server_stats"
        )
        rows = self.conn.execute(query).fetchall()

        data = {
            "servers": rows[0][0],
            "served_repositories": rows[0][1] or 0,
            "recorded_commits": rows[0][2] or 0,
        }

        return data

    def list_repositories(self) -> frozenset:
        query = (
            "SELECT name FROM sqlite_master "
            'WHERE type = "table" AND name LIKE "timestamped_coverage_%"'
        )

        tuples = self.conn.execute(query).fetchall()

        prefix_len = len("timestamped_coverage_")
        return frozenset({row[0][prefix_len:] for row in tuples})

    def commits_count(self, repository_id) -> frozenset:
        query = "SELECT count(*) FROM timestamped_coverage_{repository_id} ".format(
            repository_id=repository_id
        )
        tuples = self.conn.execute(query).fetchone()
        return next(iter(tuples))


def record_telemetry_event(data: dict, remote_addr: str, config: dict = None):
    ip_bytes = socket.inet_aton(remote_addr)
    data["ip"] = hashlib.sha224(ip_bytes).hexdigest()
    with SqliteServerAdapter(config) as adapter:
        adapter.record(data)


@app.route("/api/v1/telemetry", methods=["POST"])
@authenticated
def api_telemetry_collect():
    data = request.get_json()
    record_telemetry_event(data, remote_addr=request.remote_addr)
    return "OK, Thanks!"


@app.route("/api/v1/telemetry", methods=["GET"])
@authenticated
def api_telemetry_get():
    with SqliteServerAdapter() as server_adapter:
        data = server_adapter.totals()
    return jsonify(data)


def api_repositories_debug_common():
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    return adapter_class.list_repositories(config)


@app.route("/api/v1/repositories/debug", methods=["GET"])
@authenticated
def api_repositories_debug_v1():
    response = api_repositories_debug_common()
    return jsonify(list(response))


@app.route("/api/v2/repositories/debug", methods=["GET"])
@authenticated
def api_repositories_debug_v2():
    response = api_repositories_debug_common()
    return jsonify({"repositories": list(response)})


def api_references_all_common(repository_id):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        return adapter.get_cc_commits()


@app.route("/api/v1/references/<string:repository_id>/all", methods=["GET"])
def api_references_all_v1(repository_id):
    commits = api_references_all_common(repository_id)
    return jsonify(list(commits))


@app.route("/api/v2/references/<string:repository_id>/all", methods=["GET"])
def api_references_all_v2(repository_id):
    commits = api_references_all_common(repository_id)
    return jsonify({"references": list(commits)})


def dump_data(repository_id):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        return adapter.dump()


@app.route("/api/v1/references/<string:repository_id>/debug", methods=["GET"])
@authenticated
def api_references_debug(repository_id):
    dump = dump_data(repository_id)

    output = []
    for commit, data in dump:
        output.append(
            {
                "commit_id": commit,
                "data_type": type(data).__name__,
                "data_lenght": len(data) if data else None,
            }
        )

    return jsonify({"repository_id": repository_id, "data": output})


@app.route(
    "/api/v1/references/<string:repository_id>/<string:commit_id>/data",
    methods=["GET"],
)
def api_reference_download_data(repository_id, commit_id):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        response = adapter.retrieve_cc_data(commit_id)
        if not response:
            abort(404)
        return response


@app.route(
    "/api/v1/references/<string:repository_id>/<string:commit_id>/debug",
    methods=["GET"],
)
@authenticated
def api_reference_download_data_debug(repository_id, commit_id):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        cc_reference_data = adapter.retrieve_cc_data(commit_id)
        return {
            "commit_id": commit_id,
            "data_len": len(cc_reference_data) if cc_reference_data else None,
            "data_type": type(cc_reference_data).__name__,
        }


@app.route(
    "/api/v1/references/<string:repository_id>/<string:commit_id>/data", methods=["PUT"]
)
@authenticated
def api_upload_reference(repository_id, commit_id):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        data = request.get_data()
        try:
            adapter.persist(commit_id, data)
        except Exception:
            abort(400, "Invalid request.")
        return "{} bytes ({}) received".format(len(data), type(data).__name__)


@app.route("/web/report/<string:repository_id>/<string:commit_id>", methods=["GET"])
def web_generate_report(repository_id, commit_id):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        reference = retrieve(adapter, commit_id)
        if not reference:
            abort(404, b"<html><h1>Huh-oh</h1><p>Sorry, no data found.</p></html>")
        report = HtmlReporter(reference)
        return report.generate()


def retrieve(adapter, commit_id, source="ccguard"):
    cc_reference_data = adapter.retrieve_cc_data(commit_id)
    reference_fd = io.BytesIO(cc_reference_data)

    try:
        return Cobertura(reference_fd, source=source)
    except lxml.etree.XMLSyntaxError:
        return


@app.route(
    "/web/diff/<string:repository_id>/<string:commit_id1>..<string:commit_id2>",
    methods=["GET"],
)
def web_generate_diff(repository_id, commit_id1, commit_id2):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        reference = retrieve(adapter, commit_id1)
        challenger = retrieve(adapter, commit_id2)
        if not reference or not challenger:
            abort(404, b"<html><h1>Huh-oh</h1><p>Sorry, no data found.</p></html>")
        delta = HtmlReporterDelta(reference, challenger)
        return delta.generate()


def parse_args(args=None):
    parser = argparse.ArgumentParser(description="ccguard web server")

    ccguard.parse_common_args(parser)

    parser.add_argument(
        "--token", dest="token", help="the access token for this server"
    )
    parser.add_argument(
        "--host",
        dest="host",
        help=(
            "the IP address we are going to listen on "
            "(default: 127.0.0.1, public: 0.0.0.0)"
        ),
        default="127.0.0.1",
    )
    parser.add_argument(
        "--cert", dest="certificate", help="the ssl certificate pem file",
    )
    parser.add_argument(
        "--private-key", dest="private_key", help="the ssl private key pem file",
    )
    parser.add_argument(
        "--port", dest="port", help="the port to listen on", type=int,
    )

    return parser.parse_args(args)


def _prepare_event(config=None):
    with SqliteServerAdapter(config) as adapter:
        repositories = adapter.list_repositories()

        data = {"repositories_count": len(repositories), "commits_count": 0}

        for repository_id in repositories:
            commits = adapter.commits_count(repository_id)
            data["commits_count"] += commits

    return data


def send_telemetry_event(config: dict = None):
    config = config or ccguard.configuration()

    data = _prepare_event(config)

    if config.get("telemetry.disable", False):
        logging.debug("telemetry: disabled")
        record_telemetry_event(data, "127.0.0.1", config=config)
    else:
        logging.debug("telemetry: enabled")
        x = threading.Thread(
            target=requests.post,
            args=("https://ccguard.nilleb.com/api/v1/telemetry",),
            kwargs={"data": data},
        )
        x.start()

    return data


def load_app(token):
    send_telemetry_event()
    app.config["TOKEN"] = token
    return app


def main(args=None, app=app):
    send_telemetry_event()
    logging.basicConfig(level=logging.DEBUG)
    args = parse_args(args)
    app.config["TOKEN"] = args.token
    ssl_context = (
        (args.certificate, args.private_key)
        if args.certificate and args.private_key
        else None
    )
    app.run(host=args.host, port=args.port, ssl_context=ssl_context)


if __name__ == "__main__":
    main()
