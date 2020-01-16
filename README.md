# ccguard

you can only improve! :-)

ccguard compares the current code coverage to past code coverage. ccguard fails unless your new code coverage is equal or better than your past code coverage!

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
# install a venv so to keep your system interpreter clean
python3 -m venv env
source env/bin/activate

pip install -r dev-requirements.txt
pip install --upgrade pip
cp pre-commit .git/hooks/pre-commit
```

please execute flake8, black, pytest and ccguard against all of your changes.
(a pre-commit hook will ensure that everythng is fine before letting you commit)

```sh
pytest -v --cov-report xml --cov ccguard
flake8 ccguard/ccguard.py
black ccguard/ccguard.py
python ccguard/ccguard.py --html coverage.xml --repository ccguard
```

## execute this tool

```sh
# produce coverage data executing your unit tests and covert them to cobertura, then
python ccguard.py coverage.xml
```

## documentation: how to produce coverage data

### golang

```sh
# install cobertura converter (only once)
go get github.com/t-yuki/gocover-cobertura
# compute the code coverage and convert it to cobertura
go test -coverprofile=coverage.txt -covermode count github.com/gorilla/mux
gocover-cobertura < coverage.txt > coverage.xml
```

## python

```sh
# install cobertura converter (only once)
pip install pytest-cov
# compute the code coverage and convert it to cobertura
pytest -v --cov-report xml --cov my_project
```

## javascript

add to your `package.json` the required `cobertura` settings

```json
{
  "name": "continuous-test-code-coverage-guide",
  "scripts": {
    "start": "webpack",
    "test": "jest --coverage --coverageDirectory=output/coverage/jest"
  },
  ...
  "jest": {
    "coverageReporters": [
      "text",
      "cobertura"
    ]
    ...
  }
}
```

pass to ccguard the path to the coverage directory

## credits

- [Alexandre Conrad](https://pypi.org/user/aconrad/) for his wonderful pycobertura
