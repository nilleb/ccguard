# ccguard

[![CircleCI](https://circleci.com/gh/nilleb/ccguard.svg?style=svg)](https://circleci.com/gh/nilleb/ccguard)

you can only improve! :-)

ccguard compares the current code coverage to past code coverage. ccguard fails unless your new code coverage is equal or better than your past code coverage!

![ccguard.py in action](https://github.com/nilleb/ccguard/blob/master/static/success.png?raw=true "ccguard.py in action")
![so bad, a regression](https://github.com/nilleb/ccguard/blob/master/static/failure.png?raw=true "so bad, a regression")
![trends](https://github.com/nilleb/ccguard/blob/master/static/log.png "cc is increasing!")

## requires

- python
- git

Should work on both python2 and python3. python2 is not anymore supported.

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

## execute this tool

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
```

## launch a local server

ccguard server allows you to centralize the reports and the regression checks (useful for CI workflows)
also serves coverage and diff reports.

```sh
ccguard_server
```

## credits

- [Alexandre Conrad](https://pypi.org/user/aconrad/) for his wonderful pycobertura
- all the beta testers for their precious feedback
