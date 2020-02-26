[[ -d env-0.3-backup ]] || cp -dpR env env-0.3-backup
source env/bin/activate
pip install --upgrade ccguard
python env/lib/python3.7/site-packages/ccguard/scripts/migrate_sqlite_database.py ~/.ccguard.db
