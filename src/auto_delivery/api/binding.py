from ..api.client import ApiClient


class BindingApi:
    SEARCH_API_PATH = "/prod-api/batchput/material/search"
    VIDEO_QUERY_API_PATH = "/prod-api/video/shortPlay/pageList"
    BIND_API_PATH = "/prod-api/batchput/material/updateBatchVideoId"

    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient()

    def search_material(self, filename: str) -> dict:
        """2.1 搜索素材获取绑定用ID"""
        params = {
            "searchType": 1,
            "search": filename,
            "tagIds": [],
        }
        return self.client.post(self.SEARCH_API_PATH, json=params)

    def query_video(self, short_play_library_name: str, language: str) -> dict:
        """2.2 查询视频获取绑定用shortPlayId"""
        params = {
            "pageNum": 1,
            "pageSize": 10,
            "isCheck": 0,
            "shortPlayLibraryName": short_play_library_name,
            "languages": [language],
        }
        return self.client.get(f"{self.VIDEO_QUERY_API_PATH}", params=params)

    def bind_material(self, material_id: int, short_play_id: str) -> dict:
        """2.3 绑定素材到短剧"""
        params = {
            "materialIds": f"[{material_id}]",
            "videoId": short_play_id,
        }
        return self.client.post(self.BIND_API_PATH, json=params)
