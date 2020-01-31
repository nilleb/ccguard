import requests
from ccguard import ReferenceAdapter


class WebAdapter(ReferenceAdapter):
    def __init__(self, repository_id, config={}):
        self.server = config.get("ccguard.server.address")
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
        r = requests.put(
            "{server}/api/v1/references/{repository_id}/{commit_id}/data".format(
                self, commit_id=commit_id
            )
        )

    # does not support `dump` yet
