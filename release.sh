# Before you release
# - install twine: pip install twine
# - configure your .pypirc as described here https://pypi.org/help/#apitoken
#   - the section shall be named ccguard
# - bump package version in setup.py

PKG_NAME=$(python setup.py --name)
PKG_VERSION=$(python setup.py --version)

sed -i "" "s/\(__version__ = \"\).*\(\"\)/\1${PKG_VERSION}\2/g" ccguard/__init__.py

git add ccguard/__init__.py
git commit -m "chore: bump version"

git tag -am "release v${PKG_VERSION}" v${PKG_VERSION}
git push --tags
python setup.py bdist_wheel
twine upload --repository ccguard dist/${PKG_NAME}-${PKG_VERSION}-py3-none-any.whl
