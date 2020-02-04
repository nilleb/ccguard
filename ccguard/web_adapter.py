import os
import requests
import ccguard


class WebAdapter(ccguard.ReferenceAdapter):
    def __init__(self, repository_id, config={}):
        conf_key = "ccguard.server.address"
        token_key = "ccguard.token"
        env_server = os.environ.get(conf_key.replace(".", "_"), None)
        self.server = env_server if env_server else config.get(conf_key)
        token = os.environ.get(token_key.replace(".", "_"), None)
        self.token = token if token else config.get(conf_key, None)
        super().__init__(repository_id, config)

    def get_cc_commits(self) -> frozenset:
        r = requests.get(
            "{p.server}/api/v1/references/{p.repository_id}/all".format(p=self)
        )
        return frozenset(r.json())

    def retrieve_cc_data(self, commit_id: str) -> bytes:
        r = requests.get(
            "{p.server}/api/v1/references/{p.repository_id}/{commit_id}/data".format(
                p=self, commit_id=commit_id
            )
        )
        return r.content.decode("utf-8")

    def persist(self, commit_id: str, data: bytes):
        headers = {}
        if self.token:
            headers["Authorization"] = self.token

        requests.put(
            "{p.server}/api/v1/references/{p.repository_id}/{commit_id}/data".format(
                p=self, commit_id=commit_id
            ),
            headers=headers,
        )

    def dump(self):
        print(requests.get)
        r = requests.get(
            "{p.server}/api/v1/references/{p.repository_id}/data".format(p=self)
        )
        return r.json
