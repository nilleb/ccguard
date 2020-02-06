# the ccguard.config.json file

this file may be found in

- the repository folder
- your home folder

it's name shall be .ccguard.config.json


It will be used hyerarchically: we'll consider first the default parameters, then we'll update these values with the ones from the file in your home folder, last we'll update these values with the ones from the file in the current repository.

## known keys

the redis configuration

```json
    "redis.host": "localhost",
    "redis.port": 6379,
    "redis.db": 0,
    "redis.password": None,
```

the ccguard web server address (used by the web adapter)

```json
    "ccguard.server.address": "http://127.0.0.1:5000",
```

the sensitivity (or tolerance) of ccguard

```json
    "threshold.tolerance": 0, (no tolerance)
    "threshold.hard-minimum": -1, (no threshold - otherwise an integer between 0 and 100)
```

the path to the local sqlite database (the default adapter)

```json
    "sqlite.dbpath": "/tmp/ccguard.db"
```

the adapter to use

```json
    "adapter.class": "web" or "redis" or "sqlite"
```
