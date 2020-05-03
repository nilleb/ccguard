PKG_NAME=$(python setup.py --name)
PKG_VERSION=$(python setup.py --version)
sed -i "" "s/\(__version__ = \"\).*\(\"\)/\1${PKG_VERSION}\2/g" ccguard/__init__.py
