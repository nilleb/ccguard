import io
import logging
import argparse
import flask
from flask import request, jsonify, abort
from pycobertura import Cobertura
from pycobertura.reporters import HtmlReporter, HtmlReporterDelta
import ccguard

app = flask.Flask(__name__)
app.config["DEBUG"] = True


@app.route("/", methods=["GET"])
def home():
    return (
        "<h1>CCGuard Server</h1>"
        "<p>A CCGuard prototype API for uploading reports, "
        "listing references and displaying reports.</p>"
    )


@app.route("/api/v1/references/<string:repository_id>/all", methods=["GET"])
def api_references_all(repository_id):
    config = ccguard.configuration(repository_id)
    adapter_class = ccguard.adapter_factory(None, config)
    commits = []
    with adapter_class(repository_id, config) as adapter:
        commits = adapter.get_cc_commits()

    return jsonify(list(commits))


@app.route(
    "/api/v1/references/<string:repository_id>/<string:commit_id>/data",
    methods=["GET"],
)
def api_references_download_data(repository_id, commit_id):
    config = ccguard.configuration(repository_id)
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        return adapter.retrieve_cc_data(commit_id)


def check_auth():
    token = app.config.get("TOKEN", None)
    print(token)
    if token:
        auth = request.headers.get("authorization", None)
        if not auth:
            return (401, "Authentication required")
        if auth != token:
            return (403, "Forbidden")


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
        adapter.persist(commit_id, request.data)
        return "OK"


@app.route("/web/report/<string:repository_id>/<string:commit_id>", methods=["GET"])
def api_generate_report(repository_id, commit_id):
    config = ccguard.configuration()
    adapter_class = ccguard.adapter_factory(None, config)
    with adapter_class(repository_id, config) as adapter:
        reference = retrieve(adapter, commit_id)
        report = HtmlReporter(reference)
        return report.generate()


def retrieve(adapter, commit_id, source="ccguard"):
    cc_reference_data = adapter.retrieve_cc_data(commit_id)
    logging.debug("Reference data (%s): %r", commit_id, cc_reference_data)
    reference_fd = io.StringIO(cc_reference_data)
    return Cobertura(reference_fd, source=source)


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
        "--port", dest="port", help="the port to listen on", type=int,
    )

    return parser.parse_args(args)


def main(args=None):
    args = parse_args(args)
    app.config["TOKEN"] = args.token
    app.run(port=args.port)


if __name__ == "__main__":
    main()