# How to integrate ccguard in your CircleCI job

## Limitations

At the moment, [CircleCI does not expose the base branch of the PR being processed](https://ideas.circleci.com/ideas/CCI-I-894).
ccguard assumes then that the base branch is `origin/master`, and determines which reference to use on the base of the common history between `HEAD` and `origin/master`.
As pointed out by a comment on the Idea, a transitory solution would be to use [this orb](https://github.com/NarrativeScience/circleci-orb-ghpr), specifying `--target-branch ${GITHUB_PR_BASE_BRANCH:-origin/master}`. The two sample workflows include it.
Otherwise, you could adopt a more aggressive behavior `--target-branch HEAD` that compares the current CC to the previous commit.

## Common

Set two environment variables

```sh
# the public address of your ccguard server
ccguard_server_address=https://ccguard.your.domain
# you should have setup this same token when preparing ccguard_server
ccguard_token=azoudcodbqzypfuazêofvpzkecnaio
```

## Go workflow

Disclaimer: requires python. You could instead use the "_I don't want install python3_ workflow".

```yaml
  prepare_tests:
    description: "Prepare unit tests environment"
    steps:
      - run:
          name: Prepare unit tests environment
          command: |
            sudo apt-get update
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
            source /tmp/workspace/env/bin/activate
            ccguard_convert coverage.txt -if go -of xml -o coverage.xml
            ccguard --adapter web coverage.xml --target-branch ${GITHUB_PR_BASE_BRANCH:-origin/master} --branch ${CIRCLE_BRANCH}

      - store_artifacts:
          path: cc.html
          destination: cc.html

      - store_artifacts:
          path: diff.html
          destination: diff.html
```

## python 3 workflow

```yaml
      - run:
          name: run build workflow
          command: |
            python3 -m venv venv
            . venv/bin/activate
            pip install black flake8 pytest pytest-cov ccguard
            black --check ccguard/*.py
            flake8 ccguard/*.py
            pytest --cov-report xml --cov src
            ccguard --html coverage.xml --adapter web --target-branch ${GITHUB_PR_BASE_BRANCH:-origin/master}

      - store_artifacts:
          path: cc.html
          destination: cc.html

      - store_artifacts:
          path: diff.html
          destination: diff.html
```

## _I don't want install python3_ workflow

```yaml
      - run:
          name: run build workflow
          command: |
            # compute code coverage.xml somehow here
            curl https://raw.githubusercontent.com/nilleb/ccguard/master/ccguard/ccguard.sh -o ccguard.sh
            bash ccguard.sh coverage.xml
```
