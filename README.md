# ccguard

<div align="center">

[![CircleCI](https://circleci.com/gh/nilleb/ccguard.svg?style=svg)](https://circleci.com/gh/nilleb/ccguard) [![PyPI version](https://badge.fury.io/py/ccguard.svg)](https://badge.fury.io/py/ccguard) [![CodeCoverage](https://ccguard.nilleb.com/api/v1/repositories/a8858db8a0d483f8f6c8e74a5dc03b84bc9674f8/status_badge.svg)](https://ccguard.nilleb.com/web/main/a8858db8a0d483f8f6c8e74a5dc03b84bc9674f8)[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

</div>

you can only improve! :-)

ccguard compares the current code coverage to past code coverage. ccguard fails unless your new code coverage is equal or better than your past code coverage!

![ccguard.py in action](https://github.com/nilleb/ccguard/blob/master/static/success.png?raw=true "ccguard.py in action")
![so bad, a regression](https://github.com/nilleb/ccguard/blob/master/static/failure.png?raw=true "so bad, a regression")

<img src="https://github.com/nilleb/ccguard/raw/master/static/log.png" alt="trends" title="cc is increasing!" style="max-width: 60%;"><img src="https://github.com/nilleb/ccguard/raw/master/static/all_badges.png" alt="all the status badges" title="expose your code coverage pride ;-)" style="max-width: 40%;/* top: 0; */vertical-align: top;">

## requires

- python3 (on the server)
- git

## how should you use this software

- [setup the server](https://github.com/nilleb/ccguard/blob/master/docs/server-setup/server-setup-ubuntu.sh)
- define your code coverage exclusions and inclusions (in your test runner, not in ccguard)
- setup the CI workflow so that ccguard can ([here]((https://github.com/nilleb/ccguard/blob/master/docs/how%20to%20integrate%20ccguard%20in%20your%20CircleCI%20job.md)) for CircleCI)
  - ingest the code coverage report
  - send it to the server
  - ensure that the coverage improves
- (optional, but required for the following steps) download reports on your computer using [ccguard_sync](https://github.com/nilleb/ccguard#synchronize-repositories)
- (recommended) inspect the git/reference log with [ccguard_log](https://github.com/nilleb/ccguard#display-code-coverage-trends)
- (optional) display the code coverage for a specific commit with [ccguard_show](https://github.com/nilleb/ccguard#display-code-coverage-report)
- (optional) display the code coverage diff between two references with [ccguard_diff](https://github.com/nilleb/ccguard#display-code-coverage-diff)

## welcome beta testers: setup

```sh
# prepare the package and install it
./distrib.sh
```

## contribute

```sh
./bootstrap.sh
```

please execute flake8, black, pytest and ccguard against all of your changes.
(a pre-commit hook will ensure that everythng is fine before letting you commit)

```sh
./pre-commit
```

## ccguard - the code coverage guard

```sh
cd your-favorite-source-folder
# execute unit tests, collecting code coverage here
ccguard coverage.xml
# change your code somehow
# execute unit tests, collecting code coverage
# then verify that your code coverage has not decreased
ccguard --consider-uncommitted-changes coverage.xml
# if you are rather a visual person, check cc.html and diff.html
ccguard --html --consider-uncommitted-changes coverage.xml
# if needed to display the line coverage for each file in the HTML report,
# fine tune the source files path with the --repository argument
ccguard--html --consider-uncommitted-changes coverage.xml --repository src/
# allow regressions up to 3%
ccguard coverage.xml --tolerance 3
# allow regressions up to 10%, but never descend below 70%
ccguard coverage.xml --tolerance 10 --hard-minimum 70
# use the web adapter (ie. send the data to ccguard_server).
# requires a ccguard.server.address setting in the config.
ccguard coverage.xml --adapter web
```

please see [how to produce code coverage data](https://github.com/nilleb/ccguard/blob/master/docs/how%20to%20produce%20code%20coverage%20data.md) in your favourite language.

## display code coverage trends

What a better feedback loop than measuring the work you have accomplished?

```sh
ccguard_log
```

## display code coverage report

You could be curious about how the code coverage looked like a few commits ago..

```sh
ccguard_show 7b43f26
```

## display code coverage diff

And, you could be curious about how the code coverage has evolved between two commits.

```sh
ccguard_diff 3413af3 7b43f26
```

## synchronize repositories

The use case being: you wish to use ccguard as pre-commit. Your team already has some references.
Then you could be interested in sharing them.

```sh
# upload the report to a distant redis repository
ccguard_sync sqlite redis
# download the report from a distant redis repository
ccguard_sync redis sqlite
# limit to a single repository
ccguard_sync redis sqlite --repository_id abcd
# limit to a single repository and a single commit
ccguard_sync redis sqlite --repository_id abcd --commit_id ef12
# retrieve data from a specific web server, and display whats going on behind the scenes
ccguard_server_address=https://ccguard.nilleb.com ccguard_sync web sqlite --debug
```

## launch a local server

ccguard_server allows you to centralize the reports and the regression checks (useful for CI workflows)
also serves coverage and diff reports.

```sh
ccguard_server
```

You could be interested to know how to [setup the server](https://github.com/nilleb/ccguard/blob/master/docs/server-setup/server-setup-ubuntu.sh).

## convert a report

Sometimes you need to convert a report from a format to another. ccguard_convert is here to help!

```sh
# convert the report from golang textual format to cobertura.xml
ccguard_convert golang-coverage-report.txt -if go -of xml -o output.xml

# convert the report from cobertura xml format to html (pycobertura)
ccguard_convert cobertura.xml -if xml -of html -o output.html

# convert the report from golang textual format to html (pycobertura)
ccguard_convert golang-coverage-report.txt -if go -of html -o output.html

# you can add a .ccguard.config.json in the same directory of the report or to your home directory to fine tune the exclusions
echo '{"convert.exclusions.go": ["**/config/default.go"]}' > .ccguard.config.json
# the report will not contain the files matching the glob expression
ccguard_convert golang-coverage-report.txt -if go -of xml -o output.xml
```

To know more about glob expressions, see `man 3 fnmatch`.

## expose a status badge

Add the following Markdown to your README.md

```md
[![CodeCoverage](https://ccguard.nilleb.com/api/v1/repositories/a8858db8a0d483f8f6c8e74a5dc03b84bc9674f8/status_badge.svg?branch=master)](https://ccguard.nilleb.com/web/main/a8858db8a0d483f8f6c8e74a5dc03b84bc9674f8)
```

(make sure that you change your repository_id to match the one printed by a `ccguard --debug`)

## alternatives to this software

- [opencov](https://github.com/danhper/opencov)
- [diff-cover](https://github.com/Bachmann1234/diff_cover)
- [codecov.io](https://codecov.io/)
- [coveralls.io](https://coveralls.io/)
- [sonarqube](https://www.sonarqube.org/)

## credits

- [Alexandre Conrad](https://pypi.org/user/aconrad/) for his wonderful pycobertura
- all the beta testers for their precious feedback
