# documentation: how to produce coverage data

## golang

```sh
# install cobertura converter (only once)
go get github.com/t-yuki/gocover-cobertura
# compute the code coverage and convert it to cobertura
go test -coverprofile=coverage.txt -covermode count github.com/gorilla/mux
gocover-cobertura < coverage.txt > coverage.xml
# pass to ccguard the path of the coverage.xml file
```

## python

```sh
# install cobertura converter (only once)
pip install pytest-cov
# compute the code coverage and convert it to cobertura
pytest -v --cov-report xml --cov my_project
# pass to ccguard the path of the coverage.xml file
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

pass to ccguard the path of the coverage directory
