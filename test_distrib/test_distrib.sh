rm dist/*.whl
rm -rf /tmp/venv

PKG_NAME=$(python setup.py --name)
PKG_VERSION=$(python setup.py --version)
sed -i "" "s/\(__version__ = \"\).*\(\"\)/\1${PKG_VERSION}\2/g" ccguard/__init__.py

pip install wheel
python3 setup.py bdist_wheel
python3 -m venv /tmp/venv
source /tmp/venv/bin/activate
cd /tmp/
python3 -m pip install ${OLDPWD}/dist/*.whl
