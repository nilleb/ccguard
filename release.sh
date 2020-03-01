# Before you release
# - install pandoc on your system: apt-get install pandoc
# - install pypandoc: pip install pypandoc
# - install twine: pip install twine
# - bump package version in setup.py
# - update the package version in the CHANGES file

PKG_NAME=$(python setup.py --name)
PKG_VERSION=$(python setup.py --version)

sed -i "" "s/\(__version__ = \"\).*\(\"\)/\1${PKG_VERSION}\2/g" ccguard/__init__.py

git tag -am "release v${PKG_VERSION}" v${PKG_VERSION}
git push --tags
python setup.py bdist_wheel
twine upload dist/${PKG_NAME}-${PKG_VERSION}-py3-none-any.whl
