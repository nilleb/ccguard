python3 -m venv env
source env/bin/activate
# install python packaging tools
pip install wheel
# build this package
python3 setup.py bdist_wheel
# install it
python3 -m pip install dist/*.whl
