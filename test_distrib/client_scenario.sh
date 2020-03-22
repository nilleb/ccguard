# change to a folder containing a .git repository and a coverage.xml
repository=${repository:-~/dev/rav1e}

set -eu

if [[ ! -f ${repository}/coverage.xml ]]; then
    echo "fatal: need a coverage.xml report in ${repository}"
    exit 255
fi

source /tmp/venv/bin/activate
export ccguard_server_address=http://localhost:8888
export ccguard_token=aaaa
cd $repository
ccguard --adapter web coverage.xml $*
ccguard_log --adapter web $*
ccguard_sync web default $*
ccguard_log $*
echo "OK, test passed"
