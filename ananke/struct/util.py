import requests
import logging

logger = logging.getLogger(__name__)


class MegaportAuth:
    def __init__(self, client_id: str, client_secret: str, staging: bool = True):
        self.client_id = client_id
        self.client_secret = client_secret
        self.staging = staging
        self.token = self.get_token()

    def get_token(self) -> str:
        session = requests.Session()
        if self.staging:
            url = "https://oauth-m2m-staging.auth.ap-southeast-2.amazoncognito.com/oauth2/token"
        else:
            url = "https://auth-m2m.megaport.com/oauth2/token"
        session.auth = (self.client_id, self.client_secret)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        body = {"grant_type": "client_credentials"}
        response = session.post(url=url, headers=headers, data=body)
        logger.debug(response.json())
        return response.json()["access_token"]
