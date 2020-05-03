DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
${DIR}/../common-distrib.sh

python3 -m venv /tmp/venv
source /tmp/venv/bin/activate
cd /tmp/
python3 -m pip install ${OLDPWD}/dist/*.whl
