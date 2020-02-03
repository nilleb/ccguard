# documentation: how to setup ccguard for CI

## launch the server

the aim of the server is to centralize the code coverage data for the whole team, and to ensure that it has not regressed.

on a machine accessible via internet

```sh
pip install ccguard
# for more safety, change the port anc the token
ccguard_server --port 17132 --token EyNHvrWsP6BiiS3QrmzoY3NQNmHLMeYD7SVfAVYK
```

## circleci

expose environment variables

```sh
CCGUARD_SERVER_ADDRESS=http://ccguard_server:17132
CCGUARD_TOKEN=EyNHvrWsP6BiiS3QrmzoY3NQNmHLMeYD7SVfAVYK
```

add to your circleci.yaml

```sh
ccguard --adapter web coverage.xml
```

## on every team member host

you can retrieve the data collected by ccguard, periodically, with the command

```sh
CCGUARD_SERVER_ADDRESS=http://ccguard_server:17132
# no token required to retrieve the coverage data
# retrieve the data (requires ccguard 0.4)
ccguard_sync web sqlite
# inspect the log (directly in the repository you want to check)
ccguard_log
```
