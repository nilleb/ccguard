# to open ipython on ccguard, with autoreload on
ipython -i interpreter.py

# to execute unit tests on ccguard
pytest -v --cov-report xml --cov ccguard

# to execute the linter
flake8 ccguard/ccguard.py

# to upload the package
python3 -m twine upload dist/*

# start a virtual environment
python3 -m venv env
source env/bin/activate

# to build the package in a venv
pip install wheel

# to prepare this package
python3 setup.py bdist_wheel

# to install this package locally
python3 -m pip install dist/*.whl
