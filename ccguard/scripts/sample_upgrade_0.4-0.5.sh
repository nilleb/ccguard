[[ -f ~/.ccguard.db-202004141500-0.4.0.backup ]] || cp ~/.ccguard.db .ccguard.db.202004141500-0.4.0.backup
[[ -d env-0.4-backup ]] || cp -dpR env env-0.4-backup
. env/bin/activate
pip install --upgrade ccguard
python env/lib/python3.6/site-packages/ccguard/scripts/migrate_sqlite_database.py ~/.ccguard.db
sudo systemctl restart ccguard
