# ccguard

## requires

- python
- git

## golang

### how to install this tool

```sh
go get github.com/t-yuki/gocover-cobertura
```

## how to use this tool

```sh
go test -coverprofile=coverage.txt -covermode count github.com/gorilla/mux
gocover-cobertura < coverage.txt > coverage.xml
```

## python

### how to install this tool

```sh
pip install pytest-cov
```

## how to use this tool

```sh
pytest -v --cov-report xml --cov my_project
```

## credits

- [Alexandre Conrad](https://pypi.org/user/aconrad/) for his wonderful pycobertura
