# FAQ

## What does CCGuard collect, and where

CCGuard stores Code Coverage reports.

It sends the report, the git repository ID and the git commit ID associated to the report, to the configured adapter.

- No source code is being collected.
- No commit message or git metadata other than commit IDs are being collected.

According to the configured adapter settings:

- SQLiteAdapter (the default adapter) writes the reports to a local sqlite database (by default, $HOME/.ccguard.db)
- RedisAdapter sends the reports to the configured Redis Server (by default, http://localhost:6379)
- WebAdapter sends the reports to a ccguard server (by default, http://localhost:5000)

The `ccguard_server` POSTs a request to https://ccguard.nilleb.com/api/v1/telemetry, at startup, containing

- The number of repositories
- The cumulated number of collected references

You can turn off this data submission by setting the `telemetry.disable` flag to false in the `.ccguard.config.json` file used by the ccguard_server (by default, it is located in the `$HOME`).

## Hey, I have merged my two branches, where ccguard was successful, to master; and it now detects a regression

Yeah, this is possible if both the branches had the same base and you merged them without rebasing.
I would suggest you to force the rebase of your pull request before merging.
