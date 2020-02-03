rm dist/*.whl
rm -rf /tmp/venv
python3 setup.py bdist_wheel
python3 -m venv /tmp/venv
source /tmp/venv/bin/activate
cd /tmp/
python3 -m pip install /Users/ivo/dev/ccguard/dist/*.whl

#git clone https://github.com/nilleb/fsevents-watcher
#cd fsevents-watcher
exit

# the test scenario follows
source /tmp/venv/bin/activate
ccguard_server --token aaaa --port 8888

source /tmp/venv/bin/activate
export ccguard_server_address=http://localhost:8888
export ccguard_token=aaaa
cd ~/dev/rav1e
ccguard --adapter web coverage.xml
ccguard_log
ccguard_sync
