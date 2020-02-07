# documentation: how to setup ccguard for CI

## launch the server

the aim of the server is to centralize the code coverage data for the whole team, and to ensure that it has not regressed.

on a machine accessible via internet

```sh
pip install ccguard
# for more safety, change the port anc the token
ccguard_server --port 17132 --token EyNHvrWsP6BiiS3QrmzoY3NQNmHLMeYD7SVfAVYK
```

(you also have a server configuration script/sample in the folder docs/server-setup)

## circleci workflows

see [how to integrate ccguard in your CircleCI job](how%20to%20integrate%20ccguard%20in%20your%20CircleCI%20job.md) for more detailed examples.

## on every team member host

you can retrieve the data collected by ccguard, periodically, with the command

```sh
# set the ccguard server address
# via the environment variable
export CCGUARD_SERVER_ADDRESS=http://ccguard_server:17132
# or using the .ccguard.config.json
echo '{"ccguard.server.address":"https://ccguard.domain.com"}' > ~/.ccguard.config.json
# no token required to retrieve the coverage data
# retrieve the data (requires at least ccguard 0.4)
ccguard_sync web sqlite
# inspect the log (directly in the repository you want to check)
ccguard_log --adapter web
```
