import argparse
import logging
import threading

import json
import flask
import requests

import ccguard

from .ccguard_server_blueprints import (
    _prepare_event,
    api_home,
    api_v1,
    api_v2,
    record_telemetry_event,
    web,
)

app = flask.Flask(__name__)
app.config["DEBUG"] = True


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


def _register_blueprints(host_app):
    host_app.register_blueprint(api_home)
    host_app.register_blueprint(api_v1)
    host_app.register_blueprint(api_v2)
    host_app.register_blueprint(web)


_register_blueprints(app)


def load_app(token, config=None):
    send_telemetry_event(config)
    app.config["TOKEN"] = token
    return app


def main(args=None, app=app, config=None):
    logging.basicConfig(level=logging.DEBUG)
    args = parse_args(args)
    load_app(args.token, config)
    ssl_context = (
        (args.certificate, args.private_key)
        if args.certificate and args.private_key
        else None
    )
    app.run(host=args.host, port=args.port, ssl_context=ssl_context)


if __name__ == "__main__":
    main()
