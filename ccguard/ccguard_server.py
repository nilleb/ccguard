import io
import logging
import argparse
import flask
import lxml
from flask import request, jsonify, abort
from pycobertura import Cobertura
from pycobertura.reporters import HtmlReporter, HtmlReporterDelta
import ccguard

app = flask.Flask(__name__)
app.config["DEBUG"] = True


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
        '<p>A <a href="https://github.com/nilleb/ccguard">CCGuard</a> '
        "prototype API for mananing code coverage reports.</p>"
    )


@app.route("/api/v1/repositories/debug", methods=["GET"])
def api_repositories_debug():
    halt = check_auth()
    if halt:
        abort(*halt)

    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    repositories = adapter_class.list_repositories(config)

    return jsonify(list(repositories))


@app.route("/api/v1/references/<string:repository_id>/all", methods=["GET"])
def api_references_all(repository_id):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    commits = []
    with adapter_class(repository_id, config) as adapter:
        commits = adapter.get_cc_commits()

    return jsonify(list(commits))


def dump_data(repository_id):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        return adapter.dump()


@app.route("/api/v1/references/<string:repository_id>/debug", methods=["GET"])
def api_references_debug(repository_id):
    halt = check_auth()
    if halt:
        abort(*halt)

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


@app.route("/api/v1/references/<string:repository_id>/data", methods=["GET"])
def api_references_dump(repository_id):
    data = dump_data(repository_id)

    return jsonify(list(data))


@app.route(
    "/api/v1/references/<string:repository_id>/<string:commit_id>/data",
    methods=["GET"],
)
def api_references_download_data(repository_id, commit_id):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        return adapter.retrieve_cc_data(commit_id)


@app.route(
    "/api/v1/references/<string:repository_id>/<string:commit_id>/data", methods=["PUT"]
)
def api_upload_reference(repository_id, commit_id):
    halt = check_auth()
    if halt:
        abort(*halt)

    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        data = request.get_data(as_text=True)
        adapter.persist(commit_id, data)
        return "{} bytes ({}) received".format(len(data), type(data).__name__)


@app.route("/web/report/<string:repository_id>/<string:commit_id>", methods=["GET"])
def api_generate_report(repository_id, commit_id):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        reference = retrieve(adapter, commit_id)
        if not reference:
            return "<h1>Huh-oh</h1><p>Sorry, no data found.</p>"
        report = HtmlReporter(reference)
        return report.generate()


@app.route(
    "/api/v1/references/<string:repository_id>/<string:commit_id>/debug",
    methods=["GET"],
)
def api_generate_report_debug(repository_id, commit_id):
    halt = check_auth()
    if halt:
        abort(*halt)

    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        cc_reference_data = adapter.retrieve_cc_data(commit_id)
        return {
            "commit_id": commit_id,
            "data_len": len(cc_reference_data) if cc_reference_data else None,
            "data_type": type(cc_reference_data).__name__,
        }


def retrieve(adapter, commit_id, source="ccguard"):
    cc_reference_data = adapter.retrieve_cc_data(commit_id)
    reference_fd = io.StringIO(cc_reference_data)

    try:
        return Cobertura(reference_fd, source=source)
    except lxml.etree.XMLSyntaxError:
        return


@app.route(
    "/web/diff/<string:repository_id>/<string:commit_id1>..<string:commit_id2>",
    methods=["GET"],
)
def api_generate_diff(repository_id, commit_id1, commit_id2):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        reference = retrieve(adapter, commit_id1)
        challenger = retrieve(adapter, commit_id2)
        if not reference or not challenger:
            return "<h1>Huh-oh</h1><p>Sorry, no data found.</p>"
        delta = HtmlReporterDelta(reference, challenger)
        return delta.generate()


def parse_args(args=None):
    parser = argparse.ArgumentParser(description="ccguard web server")

    parser.add_argument(
        "--adapter-class",
        help="Choose the adapter to use (choices: sqlite or redis)",
        dest="adapter",
    )
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


def load_app(token):
    app.config["TOKEN"] = token
    return app


def main(args=None, app=app):
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
