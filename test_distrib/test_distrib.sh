rm dist/*.whl
rm -rf /tmp/venv

pip install wheel
python3 setup.py bdist_wheel
python3 -m venv /tmp/venv
source /tmp/venv/bin/activate
cd /tmp/
python3 -m pip install ${OLDPWD}/dist/*.whl
