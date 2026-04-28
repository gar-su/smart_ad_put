from datetime import date, timedelta
from typing import Iterator
from ..api.client import ApiClient


class MaterialReportApi:
    API_PATH = "/prod-api/put/material/list"

    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient()

    def query_day(self, query_date: date, page: int = 1) -> dict:
        """查询某一天的素材报表"""
        params = {
            "startDate": query_date.isoformat(),
            "endDate": query_date.isoformat(),
            "pageNum": page,
            "pageSize": 100,
            "type": 1,
        }
        return self.client.post(self.API_PATH, json=params)

    def query_days(self, days: int = 5) -> Iterator[dict]:
        """查询最近N天的素材报表"""
        today = date.today()
        for i in range(days):
            query_date = today - timedelta(days=i)
            resp = self.query_day(query_date)
            yield resp
