# ccguard CHANGELOG

## 0.5

- chore: use a template and use bootstrap
  - better keep separated python and html
- feature: status badge
  - provide a status badge for every project hosted by the ccguard server
- feature: telemetry
  - at boot, ccguard_server sends a payload to ccguard.nilleb.com, signalling the total number of hosted repositories and commits.
  - your IP address is being scrambled at reception on ccguard.nilleb.com
  - the data is kept only to measure how much ccguard is useful
  - you can opt out setting `"telemetry.disable": True` in your .ccguard.config.json
- feature: expose gross indicators at the table level
  - now, we exctract the line rate, the total number of lines and the covered lines when uploading a report
  - this feature requires a migration
- feature: a bash uploader
  - you can not upload the report and check if the coverage has improved using ccguard.sh

## When upgrading from version 0.4 to 0.5

run the migration script `migrate_sqlite_database.py` supplying as a single argument the path to the database to be migrated.
