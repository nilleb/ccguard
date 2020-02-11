# FAQ

## What does CCGuard collect, and where

CCGuard stores Code Coverage reports.
It sends the report, and the associated git commit ID, to the configured adapter.

No source code is being collected, at any time.
No commit message or metadata is being collected.

According to the configured adapter settings:

- SQLiteAdapter writes the reports to a local sqlite database (by default, $HOME/.ccguard.db)
- RedisAdapter sends the reports to the configured Redis Server listening on http://localhost:6379
- WebAdapter sends the reports to a ccguard server listening on http://localhost:5000
