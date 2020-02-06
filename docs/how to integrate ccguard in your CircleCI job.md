# How to integrate ccguard in your CircleCI job

## Common

Set two environment variables

```sh
# the public address of your ccguard server
CCGUARD_SERVER_ADDRESS=https://ccguard.your.domain
# you should have setup this same token when preparing ccguard_server
CCGUARD_TOKEN=azoudcodbqzypfuazêofvpzkecnaio
```

## Go workflow

```yaml
  prepare_tests:
    description: "Prepare unit tests environment"
    steps:
      - run:
          name: Prepare unit tests environment
          command: |
            go get github.com/t-yuki/gocover-cobertura
            sudo apt install python3-pip python3-venv python3-wheel
            python3 -m venv /tmp/workspace/env --system-site-packages
            /tmp/workspace/env/bin/pip install ccguard
      - persist_to_workspace:
          root: /tmp/workspace
          paths:
              - env
  run_tests:
    description: "Run unit tests and compute code coverage"
    steps:
      - attach_workspace:
          at: /tmp/workspace
      - run:
          name: Run unit tests
          command: |
            GO111MODULE=on go test -coverprofile coverage.txt -covermode=count -coverpkg=github.com/nilleb/fsevents/... ./...
            gocover-cobertura < coverage.txt > coverage.xml
            source /tmp/workspace/env/bin/activate
            ccguard --adapter web coverage.xml
```

## python workflow

```yaml
      - run:
          name: run build workflow
          command: |
            . venv/bin/activate
            venv/bin/black --check ccguard/*.py
            venv/bin/flake8 ccguard/*.py
            venv/bin/pytest --cov-report xml --cov ccguard
            venv/bin/python ccguard/ccguard.py --html coverage.xml --adapter web
```