rm dist/*.whl

PKG_NAME=$(python setup.py --name)
PKG_VERSION=$(python setup.py --version)
sed -i "" "s/\(__version__ = \"\).*\(\"\)/\1${PKG_VERSION}\2/g" ccguard/__init__.py

python3 -m venv env
source env/bin/activate
# install python packaging tools
pip install wheel
# build this package
python3 setup.py bdist_wheel
# install it
python3 -m pip install -U dist/*.whl
