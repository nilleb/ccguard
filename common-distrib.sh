rm dist/*.whl

python3 -m venv env
source env/bin/activate
# install python packaging tools
pip install wheel

./update-version.sh

# build this package
python3 setup.py bdist_wheel
