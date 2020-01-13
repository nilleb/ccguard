# to open ipython on ccguard, with autoreload on
ipython -i interpreter.py

# to execute unit tests on ccguard
pytest -v --cov-report xml --cov ccguard

# to execute the linter
flake8 ccguard/ccguard.py

# to prepare this package
python setup.py bdist_wheel

# to install this package locally
python -m pip install dist/

# to upload the package
python -m twine upload dist/*
