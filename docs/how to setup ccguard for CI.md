# documentation: how to setup ccguard for CI

## launch the server

the aim of the API server is to centralize the code coverage data for the whole team, and to ensure that the coverage rate has not regressed.

on a machine accessible via internet

```sh
pip install ccguard
# for more safety, change the port anc the token
# for even more safety, see the server setup script (docs/server-setup/server-setup-ubuntu.sh)
ccguard_server --port 17132 --token EyNHvrWsP6BiiS3QrmzoY3NQNmHLMeYD7SVfAVYK
```

## CircleCI workflows

see [how to integrate ccguard in your CircleCI job](how%20to%20integrate%20ccguard%20in%20your%20CircleCI%20job.md) for more detailed examples.

## GitHub Actions workflows

see [how to integrate ccguard in your GitHub Actions job](how%20to%20integrate%20ccguard%20in%20your%20GitHub%20Actions%20job.md) for more detailed examples.

## on every team member host

you can retrieve the data collected by ccguard, periodically, with the command

```sh
# set the ccguard server address
# via the environment variable
export ccguard_server_address=http://ccguard_server:17132
# OR using the .ccguard.config.json
echo '{"ccguard.server.address":"https://ccguard.domain.com"}' > ~/.ccguard.config.json
# execute the following steps in the repository where you have setup ccguard
# retrieve the data - no token required
ccguard_sync web sqlite
# inspect the log
ccguard_log
```
