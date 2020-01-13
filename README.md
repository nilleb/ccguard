# ccguard

you can only improve! :-)

ccguard compares the current code coverage to past code coverage. ccguard fails unless your new code coverage is equal or better than your past code coverage!

## requires

- python
- git

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

## credits

- [Alexandre Conrad](https://pypi.org/user/aconrad/) for his wonderful pycobertura
