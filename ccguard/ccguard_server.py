import argparse
import datetime
import hashlib
import io
import json
import logging
import socket
import sqlite3
import threading

import flask
import lxml
import requests
from flask import abort, jsonify, request, render_template
from pycobertura import Cobertura, CoberturaDiff
from pycobertura.reporters import HtmlReporter, HtmlReporterDelta
from colour import Color

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
    return render_template("index.html", version=ccguard.__version__)


class SqliteServerAdapter(object):
    def __init__(self, config):
        config = config or ccguard.configuration()
        dbpath = str(config.get("sqlite.dbpath"))
        logging.debug("SqliteServerAdapter: dbpath %s", dbpath)
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
            "`version` varchar(40) NOT NULL, "
            "PRIMARY KEY  (`ip`) );"
        )
        self.conn.execute(statement)

    def record(self, data: dict):
        if not data or not isinstance(data, dict) or "ip" not in data:
            raise ValueError("Unwilling to persist invalid data.")

        statement = (
            "INSERT INTO ccguard_server_stats "
            "(ip, repositories_count, commits_count, version) VALUES (?, ?, ?, ?)"
        )
        data_tuple = (
            data["ip"],
            data.get("repositories_count", 0),
            data.get("commits_count", 0),
            data.get("version", "unknown"),
        )
        try:
            self.conn.execute(statement, data_tuple)
            self.conn.commit()
        except sqlite3.IntegrityError:
            logging.info("This IP seems to have already been recorded.")
            statement = (
                "UPDATE ccguard_server_stats "
                f'SET repositories_count = {data["repositories_count"]}, '
                f'commits_count = {data["commits_count"]}, '
                f'last_updated = "{datetime.datetime.now()}", '
                f'version = "{data["version"]}" '
                f'WHERE ip = "{data["ip"]}"'
            )
            logging.debug(statement)
            self.conn.execute(statement)
            self.conn.commit()

    def totals(self) -> dict:
        query = (
            "SELECT count(*), sum(repositories_count), sum(commits_count), version "
            "FROM ccguard_server_stats "
            "GROUP BY version"
        )
        rows = self.conn.execute(query).fetchall()

        data = {}
        for row in rows:
            version = {
                "servers": row[0],
                "served_repositories": row[1] or 0,
                "recorded_commits": row[2] or 0,
            }
            data[row[3]] = version

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
    try:
        ip_bytes = socket.inet_aton(remote_addr)
    except OSError:
        logging.exception("Unexpected exception on remote_addr: %s", remote_addr)
        ip_bytes = b"0.0.0.0"

    data["ip"] = hashlib.sha224(ip_bytes).hexdigest()
    with SqliteServerAdapter(config) as adapter:
        adapter.record(data)


def remote_address():
    fwd_for = request.headers.get("X-Forwarded-For")
    if fwd_for is not None:
        parts = fwd_for.split(", ")
        return parts[0]
    real_ip = request.headers.get("X-Real-Ip")
    if real_ip:
        return real_ip
    if request.remote_addr:
        return request.remote_addr
    return "0.0.0.0"


@app.route("/api/v1/telemetry", methods=["POST"])
def api_telemetry_collect():
    data = request.get_json()

    if not data:
        return "OK, Thanks all the same!"

    record_telemetry_event(data, remote_addr=remote_address())
    return "OK, Thanks!"


@app.route("/api/v1/telemetry", methods=["GET"])
def api_telemetry_get():
    config = ccguard.configuration()
    with SqliteServerAdapter(config) as server_adapter:
        data = server_adapter.totals()
    return jsonify(data)


def api_repositories_debug_common():
    config = ccguard.configuration()
    with SqliteServerAdapter(config) as adapter:
        return adapter.list_repositories()


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


def iter_callable(refs):
    def call():
        local = refs if isinstance(refs, str) else refs.decode("utf-8")
        yield [ref for ref in local.split("\n")]

    return call


@app.route("/api/v1/references/<string:repository_id>/choose", methods=["POST"])
def api_references_choose_v1(repository_id):
    commits = request.data
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        references = adapter.get_cc_commits()
        parent = ccguard.determine_parent_commit(references, iter_callable(commits))
        if not parent:
            abort(404)
        else:
            return parent


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


BADGE_FORMAT = """<svg xmlns="http://www.w3.org/2000/svg" width="112" height="20">
    <linearGradient id="b" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
        <stop offset="1" stop-opacity=".1"/>
    </linearGradient>
    <mask id="a">
        <rect width="96" height="20" rx="3" fill="#fff"/>
    </mask>
    <g mask="url(#a)">
        <path fill="#555" d="M0 0h60v20H0z"/>
        <path fill="{color}" d="M60 0h36v20H60z"/>
        <path fill="url(#b)" d="M0 0h96v20H0z"/>
    </g>
    <g fill="#fff" text-anchor="middle"
       font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="30" y="15" fill="#010101" fill-opacity=".3">coverage</text>
        <text x="30" y="14">coverage</text>
        <text x="80" y="15" fill="#010101" fill-opacity=".3">{pct}</text>
        <text x="80" y="14">{pct}</text>
    </g>
</svg>
"""

BADGE_UNKNOWN = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
    <linearGradient id="b" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
        <stop offset="1" stop-opacity=".1"/>
    </linearGradient>
    <mask id="a">
        <rect width="121" height="20" rx="3" fill="#fff"/>
    </mask>
    <g mask="url(#a)">
        <path fill="#555" d="M0 0h60v20H0z"/>
        <path fill="#9f9f9f" d="M60 0h61v20H60z"/>
        <path fill="url(#b)" d="M0 0h121v20H0z"/>
    </g>
    <g fill="#fff" text-anchor="middle"
       font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="30" y="15" fill="#010101" fill-opacity=".3">coverage</text>
        <text x="30" y="14">coverage</text>
        <text x="89.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
        <text x="89.5" y="14">unknown</text>
    </g>
</svg>
"""


def minimize_xml(xml):
    parser = lxml.etree.XMLParser(remove_blank_text=True)
    elem = lxml.etree.XML(xml, parser=parser)
    return lxml.etree.tostring(elem)


@app.route("/api/v1/repositories/<string:repository_id>/status_badge", methods=["GET"])
def api_status_badge(repository_id):
    branch = request.args.get("branch") or "master"
    red = request.args.get("red") or "red"
    green = request.args.get("green") or "green"
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        commit_id = adapter.get_cc_commits(branch=branch, count=1)
        if not commit_id:
            return minimize_xml(BADGE_UNKNOWN)
        (commit_id,) = commit_id

        rate, *_ = adapter.get_commit_info(commit_id)
        rate = int(rate) if rate > 1 else int(rate * 100)
        rate = 100 if rate > 100 else rate

        red, green = Color(red), Color(green)
        colors = list(red.range_to(green, 100))

        return minimize_xml(
            BADGE_FORMAT.format(color=colors[rate], pct="{:d}%".format(rate))
        )


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
            logging.exception("Unexpected exception on persist.")
            abort(400, "Invalid request.")
        return "{} bytes ({}) received".format(len(data), type(data).__name__)


@app.route(
    "/api/v1/references/<string:repository_id>/"
    "<string:commit_id1>..<string:commit_id2>/comparison",
    methods=["GET"],
)
def api_compare(repository_id, commit_id1, commit_id2):
    tolerance = int(request.args.get("tolerance") or 0)
    hard_minimum = int(request.args.get("hard_minimum") or 0)
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        reference = retrieve(adapter, commit_id1)
        challenger = retrieve(adapter, commit_id2)
        if not reference or not challenger:
            abort(404, b"<html><h1>Huh-oh</h1><p>Sorry, no data found.</p></html>")
        diff = CoberturaDiff(reference, challenger)
        has_coverage_improved = ccguard.has_better_coverage(
            diff, tolerance=tolerance, hard_minimum=hard_minimum
        )
        return str(255 if not has_coverage_improved else 0)


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

        data = {
            "repositories_count": len(repositories),
            "commits_count": 0,
            "version": ccguard.__version__,
        }

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
            kwargs={
                "data": json.dumps(data),
                "headers": {"content-type": "application/json"},
            },
        )
        x.start()

    return data


def load_app(token, config=None):
    send_telemetry_event(config)
    app.config["TOKEN"] = token
    return app


def main(args=None, app=app, config=None):
    send_telemetry_event(config)
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
