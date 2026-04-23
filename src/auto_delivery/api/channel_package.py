import json
from ..api.client import ApiClient


class ChannelPackageApi:
    """账户包 API"""

    INSERT_API = "/prod-api/batchput/meta/autoTaskChannelPackage/insertOrUpdate"
    LIST_API = "/prod-api/batchput/meta/autoTaskChannelPackage/selectMetaAutoTaskChannelPackageList"

    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient()

    def create(
        self,
        package_name: str,
        audience_id: int,
        channel_no: str = "1980550782209687554",
        channel_name: str = "ns投放FB通用默认渠道",
        pixel_id: str = "1048893256918258",
        pixel_name: str = "FB-M31-1204-TEST",
        call_to_action: str = "gogogo！",
    ) -> dict:
        """创建账户包"""
        params = {
            "packageName": package_name,
            "businessType": 1,
            "promotionChannel": 1,
            "channelNo": channel_no,
            "channelName": channel_name,
            "backTemplateName": "",
            "promotionType": 1,
            "pixelId": pixel_id,
            "pixelName": pixel_name,
            "audienceId": audience_id,
            "audienceName": package_name,
            "callToAction": call_to_action,
            "relationsList": [{
                "advertiserId": "1012041707796839",
                "advertiserName": "FB-MAD-NS-XH-UTC+8-穗禾-东八-大蚂蚁",
            }],
            "dsaBeneficiary": json.dumps([
                {"dsa_id": "725556908784280", "name": "netshort", "country": "TW"},
                {"dsa_id": "725556908784280", "name": "netshort", "country": "AU"},
                {"dsa_id": "725556908784280", "name": "netshort", "country": "SG"},
                {"dsa_id": "725556908784280", "name": "netshort", "country": "TH"},
                {"dsa_id": "725556908784280", "name": "netshort", "country": "EU"},
            ]),
            "dsaPayor": json.dumps([
                {"dsa_id": "725556908784280", "name": "netshort", "country": "TW"},
                {"dsa_id": "725556908784280", "name": "netshort", "country": "AU"},
                {"dsa_id": "725556908784280", "name": "netshort", "country": "SG"},
                {"dsa_id": "725556908784280", "name": "netshort", "country": "TH"},
                {"dsa_id": "725556908784280", "name": "netshort", "country": "EU"},
            ]),
        }
        return self.client.post(self.INSERT_API, json=params)

    def list(self, page: int = 1, page_size: int = 50) -> dict:
        """查询账户包列表"""
        params = {"page": page, "pageSize": page_size}
        return self.client.get(self.LIST_API, params=params)

    def get_by_name(self, name: str) -> dict | None:
        """根据名称查找账户包"""
        resp = self.list(page=1, page_size=100)
        rows = resp.get("data", {}).get("list", [])
        for row in rows:
            if row.get("packageName") == name:
                return row
        return None
