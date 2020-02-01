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

## rust - grcov

so you have a rav1e developer among your oldest and best friends... :-)

```sh
# everything starts with..
rustup update
cargo install grcov

# in order to have -Zprofile support, you need to switch to the nighlty toolchain
rustup install nightly
rustup default nightly

# build your software and collect data
export YOUR_PROJECT_NAME=rav1e
export CARGO_INCREMENTAL=0
export RUSTFLAGS="-Zprofile -Ccodegen-units=1 -Cinline-threshold=0 -Clink-dead-code -Coverflow-checks=off -Zno-landing-pads"
# go and get a coffee after having launched the following commands. unless it's 11.40PM
cargo build --verbose $CARGO_OPTIONS
cargo test --verbose $CARGO_OPTIONS

# gather gc files
zip -0 ccov.zip `find . \( -name "${YOUR_PROJECT_NAME}*.gc*" \) -print`;
./grcov ccov.zip -s . -t lcov --llvm --branch --ignore-not-existing --ignore "/*" -o lcov.info;

# now use https://github.com/eriwen/lcov-to-cobertura-xml to convert it to cobertura
python3 -m venv env
source env/bin/activate
pip install lcov_cobertura
python env/lib/python3.7/site-packages/lcov_cobertura.py lcov.info -o coverage.xml
```
