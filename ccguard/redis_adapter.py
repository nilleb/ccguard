import redis

import ccguard
from datetime import datetime


class RedisAdapter(ccguard.ReferenceAdapter):
    def __init__(self, repository_id, config={}):
        self.repository_id = repository_id
        host = config.get("redis.host")
        port = config.get("redis.port")
        db = config.get("redis.db")
        password = config.get("redis.password")
        self.redis = redis.Redis(host=host, port=port, db=db, password=password)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.redis.close()

    def get_cc_commits(self):
        return frozenset(self.redis.hkeys(self.repository_id))

    def retrieve_cc_data(self, commit_id):
        return self.redis.hget(self.repository_id, commit_id)

    def persist(self, commit_id, data):
        self.redis.hset(self.repository_id, commit_id, data)
        self.redis.hset(
            "{}:time".format(self.repository_id), commit_id, str(datetime.now())
        )

    def dump(self):
        return self.redis.hgetall(self.repository_id)
