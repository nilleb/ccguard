# ccguard

you can only improve! :-)

ccguard compares the current code coverage to past code coverage. ccguard fails unless your new code coverage is equal or better than your past code coverage!

![alt text](static/success.png "ccguard.py in action")
![alt text](static/failure.png "so bad, a regression")

## requires

- python
- git

## welcome beta testers: setup and execution

```sh
# install a venv so to keep your system interpreter clean
python3 -m venv env
source env/bin/activate
# install python packaging tools
pip install wheel
# build this package
python3 setup.py bdist_wheel
# install it
python3 -m pip install dist/*.whl
# use it!
cd your-favorite-source-folder
# execute unit tests, collecting code coverage here
ccguard coverage.xml
# change your code somehow, commit
# execute unit tests, collecting code coverage here
ccguard coverage.xml
```

(should also work on python2)

## if you want to contribute

```sh
./bootstraph.sh
```

please execute flake8, black, pytest and ccguard against all of your changes.
(a pre-commit hook will ensure that everythng is fine before letting you commit)

```sh
./pre-commit
```

## execute this tool

```sh
# produce coverage data executing your unit tests and covert them to cobertura, then
python ccguard.py coverage.xml
```

please see [how to produce code coverage data](docs/how to produce code coverage data.md) to know how to produce code coverage data in your favourite language.

## credits

- [Alexandre Conrad](https://pypi.org/user/aconrad/) for his wonderful pycobertura
- all the beta testers for the precious feedback
