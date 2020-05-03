# Before you release
# - install twine: pip install twine
# - configure your .pypirc as described here https://pypi.org/help/#apitoken
#   - the section shall be named ccguard
# - bump package version in setup.py

. ./update-version.sh

git add ccguard/__init__.py
git commit -m "chore: bump version"

git tag -am "release v${PKG_VERSION}" v${PKG_VERSION}
git push --tags
./common-distrib.sh
twine upload --repository ccguard dist/${PKG_NAME}-${PKG_VERSION}-py3-none-any.whl
