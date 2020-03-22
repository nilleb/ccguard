# telemetry test plan

## steps

- [x] Test that the version in `ccguard/__init__.py` is upgraded when it changes in `setup.py`.
- [x] Test the `GET /api/v1/repositories/debug`
- [x] Test the `GET /api/v2/repositories/debug`
- [x] Test the `GET /api/v1/telemetry`
- [x] Test the `POST /api/v1/telemetry`
- [x] Test the server startup when the telemetry is disabled
- [x] Test the server startup when the telemetry is active
- [x] Play the client scenario

## conclusion

- three major bugs found
- all blocking bugs have been fixed
- we send twice the telemetry event at startup, considered not blocking
