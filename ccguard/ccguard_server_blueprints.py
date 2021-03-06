#! /usr/bin/env python3

import datetime
import hashlib
import io
import re
import logging
import socket
import sqlite3
import uuid
from typing import Optional, Tuple

import lxml
from colour import Color
from flask import (
    Blueprint,
    abort,
    current_app,
    g,
    jsonify,
    render_template,
    request,
    Response,
)
from pycobertura import Cobertura, CoberturaDiff
from pycobertura.reporters import HtmlReporter, HtmlReporterDelta

import ccguard

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")
api_v2 = Blueprint("api_v2", __name__, url_prefix="/api/v2")
api_home = Blueprint("api_home", __name__, url_prefix="/")
web = Blueprint("web_reports", __name__, url_prefix="/web")


ADMIN = "admin@local"


def authenticated(func):
    def inner(*args, **kwargs):
        halt = check_auth(request.headers, current_app.config, g)
        if halt:
            abort(*halt)
        return func(*args, **kwargs)

    # Renaming the function name:
    inner.__name__ = func.__name__
    return inner


def admin_required(func):
    def inner(*args, **kwargs):
        success = _is_admin(current_app.config, g)
        if not success:
            abort(403)
        return func(*args, **kwargs)

    # Renaming the function name:
    inner.__name__ = func.__name__
    return inner


class PersonalAccessToken(object):
    def __init__(self, user_id, name, value=None, revoked=False):
        super().__init__()
        self.user_id = user_id
        self.name = name
        self.value = value
        self.revoked = revoked

    @staticmethod
    def get_by_value(value: str, config=None):
        return PersonalAccessToken._get_by_value(value, config)

    def commit(self, config=None) -> None:
        if not self.value:
            raise ValueError("Unwilling to persist invalid token.")

        with PersonalAccessToken._get_connection(config) as conn:
            self._create_table(conn)
            self._persist(conn)

    @staticmethod
    def generate_value(config=None):
        possible = str(uuid.uuid4())
        # there might be a collision between two token values
        while PersonalAccessToken.get_by_value(possible, config):
            possible = str(uuid.uuid4())
        return possible

    @staticmethod
    def list_by_user_id(user_id, config=None):
        with PersonalAccessToken._get_connection(config) as conn:
            query = (
                "SELECT user_id, name, revoked "
                "FROM ccguard_server_tokens "
                "WHERE user_id = ?"
            )

            try:
                rows = conn.execute(query, (user_id,)).fetchall()
            except sqlite3.OperationalError:
                rows = []

            items = [
                PersonalAccessToken(
                    user_id=row[0], name=row[1], value="omitted", revoked=row[2]
                )
                for row in rows
            ]
            logging.debug("Returning %d tokens for %s", len(items), user_id)
            return items

    @staticmethod
    def delete(user_id, name, config=None):
        with PersonalAccessToken._get_connection(config) as conn:

            query = (
                "DELETE " "FROM ccguard_server_tokens " "WHERE user_id = ? and name = ?"
            )

            data_tuple = (
                user_id,
                name,
            )
            try:
                conn.execute(query, data_tuple)
            except sqlite3.OperationalError:
                logging.exception("Unable to delete the token %s, %s", user_id, name)

    @staticmethod
    def _get_connection(config=None) -> sqlite3.Connection:
        config = config or ccguard.configuration()
        dbpath = str(config.get("sqlite.dbpath"))
        logging.debug("PersonalAccessToken: dbpath %s", dbpath)
        return sqlite3.connect(dbpath)

    @staticmethod
    def _get_by_value(value: str, config=None):
        with PersonalAccessToken._get_connection(config) as conn:
            query = (
                "SELECT user_id, name, revoked "
                "FROM ccguard_server_tokens "
                "WHERE value = ?"
            )

            try:
                row = conn.execute(query, (value,)).fetchone()
            except sqlite3.OperationalError:
                row = None

            if row:
                return PersonalAccessToken(
                    user_id=row[0], name=row[1], value=value, revoked=row[2]
                )

            return None

    def _persist(self, conn: sqlite3.Connection) -> None:
        statement = (
            "INSERT INTO ccguard_server_tokens "
            "(user_id, name, value, revoked) VALUES (?, ?, ?, ?)"
        )
        data_tuple = (self.user_id, self.name, self.value, int(self.revoked))
        try:
            conn.execute(statement, data_tuple)
            conn.commit()
        except sqlite3.IntegrityError:
            logging.exception(
                "Token already present in base: %s (%s - %s)",
                self.value,
                self.user_id,
                self.name,
            )
            raise ValueError

    @staticmethod
    def _create_table(conn):
        statement = (
            "CREATE TABLE IF NOT EXISTS `ccguard_server_tokens` ("
            "`user_id` varchar(255) NOT NULL, "
            "`name` varchar(255) NOT NULL, "
            "`value` varchar(255) NOT NULL, "
            "`revoked` INT DEFAULT 0, "
            "PRIMARY KEY  (`user_id`, `name`) );"
        )
        conn.execute(statement)


def _is_admin(app_config, flask_global):
    token = app_config.get("TOKEN", None)
    logging.info("token %s, accessing as %s", token, flask_global.user)
    return not token or (token and flask_global.user == ADMIN)


def check_auth(headers, app_config, flask_global) -> Optional[Tuple[int, str]]:
    auth = headers.get("authorization", None)

    flask_global.user = None

    token = app_config.get("TOKEN", None)
    if token:
        if not auth:
            return (401, "Authentication required")

    if auth:
        if auth == token:
            logging.info("Successfully authenticated admin")
            flask_global.user = ADMIN
            return None

        pat = PersonalAccessToken.get_by_value(auth)

        if not pat or pat.revoked:
            logging.debug("%s, %s", pat, pat.revoked if pat else "N/A")
            return (403, "Forbidden")
        else:
            logging.info("Successfully authenticated User %s", pat.user_id)
            flask_global.user = pat.user_id
            return None

    return None


@api_home.route("/", methods=["GET"])
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
                "SET repositories_count = ?, "
                "commits_count = ?, "
                "last_updated = ?, "
                "version = ? "
                "WHERE ip = ?"
            )
            data_tuple = (
                data["repositories_count"],
                data["commits_count"],
                datetime.datetime.now(),
                data["version"],
                data["ip"],
            )
            self.conn.execute(statement, data_tuple)
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
        query = 'SELECT name FROM sqlite_master WHERE type = "table" AND name LIKE ?'

        data_tuple = (
            ccguard.SqliteAdapter._table_name_pattern.format(
                metric="%", repository_id="%"
            ),
        )
        tuples = self.conn.execute(query, data_tuple).fetchall()

        repositories_pattern = ccguard.SqliteAdapter._table_name_pattern.format(
            metric="(?P<metric>.[a-zA-Z0-9]+)",
            repository_id="(?P<repository_id>.[a-zA-Z0-9_]+)",
        )

        def extract_repository_id(table_name):
            return re.match(repositories_pattern, table_name).group("repository_id")

        return frozenset({extract_repository_id(row[0]) for row in tuples})

    def commits_count(self, repository_id) -> frozenset:
        table_name = ccguard.SqliteAdapter._table_name_pattern.format(
            metric="coverage", repository_id=repository_id
        )
        query = f"SELECT count(*) FROM {table_name}"
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


@api_v1.route("/personal_access_token/<string:user_id>", methods=["PUT"])
@authenticated
@admin_required
def api_personal_access_token_generate(user_id):
    if user_id == ADMIN:
        abort(403)

    data = request.get_json()
    if not data or not data.get("name"):
        abort(400)

    pats = PersonalAccessToken.list_by_user_id(user_id)
    if len(pats) > 4:
        logging.error("Too many PATs for user %s", user_id)
        abort(400)

    value = PersonalAccessToken.generate_value()
    pat = PersonalAccessToken(user_id, data.get("name"), value)

    try:
        pat.commit()
    except ValueError:
        abort(409)

    return jsonify({"value": pat.value, "user_id": pat.user_id, "name": pat.name})


@api_v1.route("/personal_access_token/<string:user_id>", methods=["DELETE"])
@authenticated
def api_personal_access_token_delete(user_id):
    if not (g.user == ADMIN or g.user == user_id):
        abort(403)

    data = request.get_json()
    name = data.get("name", None)

    if not name:
        abort(400)

    try:
        PersonalAccessToken.delete(user_id, name)
    except ValueError:
        abort(400)

    return {"status": "success"}


@api_v1.route("/personal_access_tokens/<string:user_id>", methods=["GET"])
@authenticated
def api_personal_access_tokens_list(user_id):
    if not (g.user == ADMIN or g.user == user_id):
        abort(403)

    pats = PersonalAccessToken.list_by_user_id(user_id)
    logging.debug("obtained %d items for %s", len(pats), user_id)
    return jsonify({"items": [{"name": pat.name} for pat in pats]})


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


@api_v1.route("/telemetry", methods=["POST"])
def api_telemetry_collect():
    data = request.get_json()

    if not data:
        return "OK, Thanks all the same!"

    record_telemetry_event(data, remote_addr=remote_address())
    return "OK, Thanks!"


@api_v1.route("/telemetry", methods=["GET"])
def api_telemetry_get():
    config = ccguard.configuration()
    with SqliteServerAdapter(config) as server_adapter:
        data = server_adapter.totals()
    return jsonify(data)


def api_repositories_debug_common():
    config = ccguard.configuration()
    with SqliteServerAdapter(config) as adapter:
        return adapter.list_repositories()


@api_v1.route("/repositories/debug", methods=["GET"])
@authenticated
@admin_required
def api_repositories_debug_v1():
    response = api_repositories_debug_common()
    return jsonify(list(response))


@api_v2.route("/repositories/debug", methods=["GET"])
@authenticated
@admin_required
def api_repositories_debug_v2():
    response = api_repositories_debug_common()
    return jsonify({"repositories": list(response)})


def api_references_all_common(repository_id, subtype):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        return adapter.get_cc_commits(subtype=subtype)


@api_v1.route("/references/<string:repository_id>/all", methods=["GET"])
def api_references_all_v1(repository_id):
    subtype = request.args.get("subtype")
    commits = api_references_all_common(repository_id, subtype)
    return jsonify(list(commits))


@api_v2.route("/references/<string:repository_id>/all", methods=["GET"])
def api_references_all_v2(repository_id):
    subtype = request.args.get("subtype")
    commits = api_references_all_common(repository_id, subtype)
    return jsonify({"references": list(commits)})


def iter_callable(refs):
    def call():
        local = refs if isinstance(refs, str) else refs.decode("utf-8")
        yield [ref for ref in local.split("\n")]

    return call


@api_v1.route("/references/<string:repository_id>/choose", methods=["POST"])
def api_references_choose_v1(repository_id):
    subtype = request.args.get("subtype")
    commits = request.data
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        references = adapter.get_cc_commits(subtype=subtype)
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


@api_v1.route("/references/<string:repository_id>/debug", methods=["GET"])
@authenticated
@admin_required
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


BADGE_FORMAT = """<svg xmlns="http://www.w3.org/2000/svg" width="96" height="20">
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

BADGE_UNKNOWN = """<svg xmlns="http://www.w3.org/2000/svg" width="121" height="20">
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


def get_last_commit(adapter, branch=None, subtype=None):
    commit_id = adapter.get_cc_commits(branch=branch, count=1, subtype=subtype)

    if not commit_id:
        return None

    (commit_id,) = commit_id
    return commit_id


@api_v1.route("/repositories/<string:repository_id>/status_badge.svg", methods=["GET"])
def api_status_badge(repository_id):
    logging.warning(request.headers.get("Referer", None))
    branch = request.args.get("branch") or "master"
    red = request.args.get("red") or "red"
    green = request.args.get("green") or "green"
    subtype = request.args.get("subtype")
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        commit_id = get_last_commit(adapter, branch, subtype)
        if not commit_id:
            return Response(minimize_xml(BADGE_UNKNOWN), mimetype="image/svg+xml")

        rate, *_ = adapter.get_commit_info(commit_id, subtype=subtype)
        rate = int(rate) if rate > 1 else int(rate * 100)
        rate = 100 if rate > 100 else rate

        red, green = Color(red), Color(green)
        colors = list(red.range_to(green, 100))

        response = minimize_xml(
            BADGE_FORMAT.format(color=colors[rate], pct="{:d}%".format(rate))
        )
        return Response(response, mimetype="image/svg+xml")


@api_v1.route(
    "/references/<string:repository_id>/<string:commit_id>/data",
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


@api_v1.route(
    "/references/<string:repository_id>/<string:commit_id>/debug",
    methods=["GET"],
)
@authenticated
@admin_required
def api_reference_download_data_debug(repository_id, commit_id):
    subtype = request.args.get("subtype")
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        cc_reference_data = adapter.retrieve_cc_data(commit_id, subtype=subtype)
        return {
            "commit_id": commit_id,
            "data_len": len(cc_reference_data) if cc_reference_data else None,
            "data_type": type(cc_reference_data).__name__,
        }


@api_v1.route(
    "/references/<string:repository_id>/<string:commit_id>/data", methods=["PUT"]
)
@authenticated
def api_upload_reference(repository_id, commit_id):
    subtype = request.args.get("subtype")
    branch = request.args.get("branch")
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        data = request.get_data()
        try:
            adapter.persist(commit_id, data, branch=branch, subtype=subtype)
        except Exception:
            logging.exception("Unexpected exception on persist.")
            abort(400, "Invalid request.")
        return "{} bytes ({}) received".format(len(data), type(data).__name__)


@api_v1.route(
    "/references/<string:repository_id>/"
    "<string:commit_id1>..<string:commit_id2>/comparison",
    methods=["GET"],
)
def api_compare(repository_id, commit_id1, commit_id2):
    subtype = request.args.get("subtype")
    tolerance = int(request.args.get("tolerance") or 0)
    hard_minimum = int(request.args.get("hard_minimum") or 0)
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        reference = retrieve(adapter, commit_id1, subtype=subtype)
        challenger = retrieve(adapter, commit_id2, subtype=subtype)
        if not reference or not challenger:
            abort(404, b"<html><h1>Huh-oh</h1><p>Sorry, no data found.</p></html>")
        diff = CoberturaDiff(reference, challenger)
        has_coverage_improved = ccguard.has_better_coverage(
            diff, tolerance=tolerance, hard_minimum=hard_minimum
        )
        return str(255 if not has_coverage_improved else 0)


@web.route("/report/<string:repository_id>/<string:commit_id>", methods=["GET"])
def web_generate_report(repository_id, commit_id):
    subtype = request.args.get("subtype")
    return report(repository_id, commit_id=commit_id, subtype=subtype)


@web.route("/main/<string:repository_id>", methods=["GET"])
def web_main(repository_id):
    branch = request.args.get("branch") or "master"
    subtype = request.args.get("subtype")
    return report(repository_id, branch=branch, subtype=subtype)


SOURCES_MESSAGE = """
Since <a href="https://github.com/nilleb/ccguard/blob/master/docs/FAQ.md#what-does-ccguard-collect-and-where">
code is not available on the server</a>,
we are not displaying it inline. In order to obtain a report including sources,
please type, in the folder containing your source code:
<pre id="commandline">
ccguard_server_address="" ccguard_show --adapter web {commit_id}
</pre>
<script>
var serverAddress = window.location.protocol + "//" + window.location.hostname
if (window.location.port != "") 
   serverAddress += ":" + window.location.port 

var preElement = document.getElementById("commandline");
preElement.innerHTML = "ccguard_server_address=" + serverAddress + " ccguard_show --adapter web {commit_id}"
</script>
"""  # noqa


def report(repository_id, commit_id=None, branch=None, subtype=None):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        commit_id = commit_id or get_last_commit(adapter, branch, subtype)
        reference = retrieve(adapter, commit_id, subtype=subtype)
        if not reference:
            abort(404, b"<html><h1>Huh-oh</h1><p>Sorry, no data found.</p></html>")
        # sources_message = SOURCES_MESSAGE.format(commit_id=commit_id)
        report = HtmlReporter(
            reference,
            # title="Coverage report for commit {commit_id}".format(commit_id=commit_id),
            # render_file_sources=False,
            # no_file_sources_message=sources_message.format(commit_id),
        )
        return report.generate()


def retrieve(adapter, commit_id, source="ccguard", subtype=None):
    cc_reference_data = adapter.retrieve_cc_data(commit_id, subtype=subtype)
    reference_fd = io.BytesIO(cc_reference_data)

    try:
        return Cobertura(reference_fd, source=source)
    except lxml.etree.XMLSyntaxError:
        return


@web.route(
    "/diff/<string:repository_id>/<string:commit_id1>..<string:commit_id2>",
    methods=["GET"],
)
def web_generate_diff(repository_id, commit_id1, commit_id2):
    subtype = request.args.get("subtype")
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        reference = retrieve(adapter, commit_id1, subtype=subtype)
        challenger = retrieve(adapter, commit_id2, subtype=subtype)
        if not reference or not challenger:
            abort(404, b"<html><h1>Huh-oh</h1><p>Sorry, no data found.</p></html>")
        delta = HtmlReporterDelta(reference, challenger)
        return delta.generate()


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
