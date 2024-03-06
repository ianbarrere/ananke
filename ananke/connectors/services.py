import requests
import re

# import google.auth.transport.requests
import logging
from time import sleep
from typing import List, Any, Dict, Optional, Literal

# from google.oauth2 import service_account
from ananke.struct.config import ConfigPack
from ananke.connectors.shared import Connector
from ananke.struct.util import MegaportAuth

logger = logging.getLogger(__name__)


# class Gcp:
#     def __init__(
#         self,
#         target_id: str,
#         settings: Any,
#         variables: Any,
#         username: str,
#         password: str,
#     ):
#         self.target_id = target_id
#         self.settings = settings
#         self.variables = variables
#         self.credentials = self.authenticate()
#         assert (
#             self.variables["service-id"] == "gcp"
#         ), f"Device {self.target_id} does not appear to be a GCP service"

#     # def refresh_token(self, decorated: Any):
#     #     def wrapper(*args):
#     #         if self.credentials.expired:
#     #             request = google.auth.transport.requests.Request()
#     #             self.credentials.refresh(request)
#     #         return decorated(*args)

#     #     return wrapper

#     def authenticate(self):
#         request = google.auth.transport.requests.Request()
#         scopes = ["https://www.googleapis.com/auth/compute.readonly"]
#         credentials = service_account.Credentials.from_service_account_file(
#             self.settings["gcp"]["service-account-file"], scopes=scopes
#         )
#         credentials.refresh(request)
#         return credentials

#     def _set_config(self, config_pack):
#         response = requests.get(
#             url=config_pack.path,
#             headers={"Authorization": f"Bearer {self.credentials.token}"},
#         )
#         print(response.json())

#     # @refresh_token
#     def deploy(self, method: str, config: List[ConfigPack], dry_run: bool) -> Any:
#         return shared_deploy(
#             target=self.target_id,
#             variables=self.variables,
#             config=config,
#             write_method=method,
#             dry_run=dry_run,
#             set_func=self._set_config,
#             transform_func=None,
#         )


class AnankeRestResource(Connector):
    def __init__(self, target_id: str, settings: Any, variables: Any):
        self.target_id = target_id
        super().__init__(target=target_id, settings=settings, variables=variables)

    @staticmethod
    def trim_url(url: str, elements: int) -> str:
        """
        Helper function to trim n elements off a URL
        """
        for _ in range(elements):
            url = url[: url.rfind("/")]
        return url

    def _set_config(self, config_pack: ConfigPack) -> Any:
        """
        Underlying config set function. Does basic coordination of service type and
        returns the requests JSON body.
        """
        if self.headers == {}:
            self._populate_headers()
        # trim off false key from path
        config_pack.path = self.trim_url(url=config_pack.path, elements=1)
        if config_pack.path == "https://api.packetfabric.com/v2/services":
            response = self._process_service_match(
                config_pack,
                requests.get(url=config_pack.path, headers=self.headers).json(),
            )
        elif config_pack.path == "https://api-staging.megaport.com/v3/product/vxc":
            products = requests.get(
                url="https://api-staging.megaport.com/v2/products",
                headers=self.headers,
            ).json()["data"]
            service_list = []
            for product in products:
                if "associatedVxcs" in product:
                    service_list.extend(product["associatedVxcs"])
            response = self._process_service_match(config_pack, service_list)
        response.raise_for_status()
        return response.json()


class PacketFabric(AnankeRestResource):
    def __init__(
        self,
        target_id: str,
        settings: Any,
        variables: Any,
        username: str,
        password: str,
    ):
        self.target_id = target_id
        self.settings = settings
        self.variables = variables
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.variables['ANANKE_PACKETFABRIC_API_KEY']}",
        }
        assert (
            self.variables["service-id"] == "packetfabric"
        ), f"Service {self.target_id} does not appear to be a PacketFabric service"
        super().__init__(target_id=target_id, settings=settings, variables=variables)

    def _populate_headers(self):
        raise NotImplementedError("Headers are pre-populated for PacketFabric")

    def _process_service_match(
        self, config_pack: ConfigPack, service_list: List[Any]
    ) -> requests.Response:
        """
        Attempts to find an existing service matching the configured attributes. If an
        existing service is already configured between the port pairs using the same
        VLANs and bandwidth then an update is made to that service, otherwise a new
        service is created.
        """
        content = config_pack.content
        configured_ports = set(
            [
                (port["port_circuit_id"], port["vlan"] if port.get("vlan") else None)
                for port in content["interfaces"]
            ]
        )
        configured_bandwidth = content["bandwidth"].get("speed")
        for service in service_list:
            service_ports = set(
                [
                    (
                        port["port_circuit_id"],
                        port["vlan"] if port.get("vlan") else None,
                    )
                    for port in service["interfaces"]
                ]
            )
            if configured_ports == service_ports:
                if configured_bandwidth != service["bandwidth"].get("speed"):
                    to_delete = f"{config_pack.path}/{service['vc_circuit_id']}"
                    response = requests.delete(
                        url=to_delete,
                        headers=self.headers,
                    )
                    retry = 10
                    success = False
                    while not success and retry > 1:
                        response = requests.get(url=to_delete, headers=self.headers)
                        print(response.json())
                        retry -= 1
                        sleep(1)
                        if (
                            "message" in response.json()
                            and "Virtual circuit not found"
                            in response.json()["message"]
                        ):
                            success = True
                    break
        return requests.post(
            url=f"{config_pack.path}/backbone",
            headers=self.headers,
            json=config_pack.content,
        )


class Megaport(AnankeRestResource):
    def __init__(
        self,
        target_id: str,
        settings: Any,
        variables: Any,
        username: str,
        password: str,
        staging: bool = True,
    ):
        self.target_id = target_id
        self.settings = settings
        self.variables = variables
        self.staging = staging
        self.headers = {}
        super().__init__(target_id=target_id, settings=settings, variables=variables)
        assert (
            self.variables["service-id"] == "megaport"
        ), f"Service {self.target_id} does not appear to be a Megaport service"

    def _populate_headers(self) -> str:
        mp_auth = MegaportAuth(
            self.variables["ANANKE_MEGAPORT_CLIENT_ID"],
            self.variables["ANANKE_MEGAPORT_CLIENT_SECRET"],
        )
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {mp_auth.token}",
        }

    def _process_service_match(
        self, config_pack: ConfigPack, service_list: List[Any]
    ) -> requests.Response:
        """
        Attempts to find an existing service matching the configured attributes. If an
        existing service is already configured between the port pairs using the same
        VLANs and bandwidth then an update is made to that service, otherwise a new
        service is created.
        """
        configured_ports = set(
            [
                (
                    config_pack.original_content["aEndProductUid"],
                    config_pack.original_content["aEndVlan"],
                ),
                (
                    config_pack.original_content["bEndProductUid"],
                    config_pack.original_content["bEndVlan"],
                ),
            ]
        )
        for service in service_list:
            service_ports = set(
                [
                    (service["aEnd"]["productUid"], service["aEnd"]["vlan"]),
                    (service["bEnd"]["productUid"], service["bEnd"]["vlan"]),
                ]
            )
            if configured_ports == service_ports:
                return requests.put(
                    url=f"{config_pack.path}/{service['productUid']}",
                    headers=self.headers,
                    json=config_pack.content,
                )
        # need to reformat our stored body since the networkdesign/buy endpoint requires
        # a different format
        purchase_body = [
            {
                "productUid": config_pack.content["aEndProductUid"],
                "associatedVxcs": [
                    {
                        "productName": config_pack.content["name"],
                        "rateLimit": config_pack.content["rateLimit"],
                        "aEnd": {"vlan": config_pack.content["aEndVlan"]},
                        "bEnd": {
                            "productUid": config_pack.content["bEndProductUid"],
                            "vlan": config_pack.original_content["bEndVlan"],
                        },
                    }
                ],
            }
        ]
        if "pairingKey" in config_pack.content:
            purchase_body[0]["associatedVxcs"][0]["bEnd"].update(
                {
                    "partnerConfig": {
                        "connectType": "GOOGLE",
                        "pairingKey": config_pack.content["pairingKey"],
                    }
                }
            )
        url_prefix = self.trim_url(url=config_pack.path, elements=2)
        response = requests.post(
            url=f"{url_prefix}/networkdesign/buy",
            headers=self.headers,
            json=purchase_body,
        )
        return response
