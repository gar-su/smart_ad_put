import json
from ..api.client import ApiClient


class AudienceApi:
    """定向包 API"""

    INSERT_API = "/prod-api/batchput/meta/autoTaskAudience/insertOrUpdate"
    LIST_API = "/prod-api/batchput/meta/autoTaskAudience/selectMetaAutoTaskAudienceList"

    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient()

    def create(
        self,
        name: str,
        country_code: str,
        country_name: str,
        age_min: int = 18,
        age_max: int | None = None,
    ) -> dict:
        """创建定向包"""
        params = {
            "name": name,
            "geoLocations": json.dumps({
                "countries": [{"key": country_code, "name": country_name}],
                "regions": [],
                "cities": [],
            }),
            "excludedGeoLocations": json.dumps({
                "countries": [],
                "regions": [],
                "cities": [],
            }),
            "ageMin": age_min,
            "ageMax": age_max,
            "facebookPositions": json.dumps([
                "feed", "profile_feed", "marketplace", "video_feeds",
                "biz_disco_feed", "story", "facebook_reels",
                "instream_video", "facebook_reels_overlay", "search",
            ]),
            "instagramPositions": json.dumps([
                "stream", "profile_feed", "explore", "explore_home",
                "story", "reels", "profile_reels", "reels_overlay", "ig_search",
            ]),
            "messengerPositions": json.dumps(["messenger_home", "story"]),
            "audienceNetworkPositions": json.dumps(["classic", "rewarded_video"]),
            "userDeviceType": 3,  # 全部设备
        }
        return self.client.post(self.INSERT_API, json=params)

    def list(self, page: int = 1, page_size: int = 50) -> dict:
        """查询定向包列表"""
        params = {"page": page, "pageSize": page_size}
        return self.client.get(self.LIST_API, params=params)

    def get_by_name(self, name: str) -> dict | None:
        """根据名称查找定向包"""
        resp = self.list(page=1, page_size=100)
        rows = resp.get("data", {}).get("list", [])
        for row in rows:
            if row.get("name") == name:
                return row
        return None
