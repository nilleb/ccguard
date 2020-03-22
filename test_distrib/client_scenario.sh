# change to a folder containing a .git repository and a coverage.xml
set -eu
repository=~/dev/rav1e
source /tmp/venv/bin/activate
export ccguard_server_address=http://localhost:8888
export ccguard_token=aaaa
cd $repository
ccguard --adapter web coverage.xml $*
ccguard_log --adapter web $*
ccguard_sync web default $*
ccguard_log $*
echo "OK, test passed"
