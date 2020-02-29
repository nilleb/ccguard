[[ -d env-0.3-backup ]] || cp -dpR env env-0.3-backup
[[ -f ~/.ccguard.db.0.3.8.backup ]] || cp ~/.ccguard.db ~/.ccguard.db.0.3.8.backup
source env/bin/activate
pip install --upgrade ccguard
python env/lib/python3.7/site-packages/ccguard/scripts/migrate_sqlite_database.py ~/.ccguard.db
sudo systemctl restart ccguard
