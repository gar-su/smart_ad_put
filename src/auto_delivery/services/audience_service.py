from src.auto_delivery.api.audience import AudienceApi
from src.auto_delivery.constants import LANGUAGE_COUNTRY_MAP, COUNTRY_NAME_MAP


class AudienceService:
    """定向包服务"""

    def __init__(self, api: AudienceApi | None = None):
        self.api = api or AudienceApi()

    def get_or_create_audience(self, language_code: str) -> int:
        """
        根据语言代码获取或创建定向包，返回 audienceId
        """
        country_code = LANGUAGE_COUNTRY_MAP.get(language_code)
        if not country_code:
            raise ValueError(f"未知的语言代码: {language_code}")

        country_name = COUNTRY_NAME_MAP.get(country_code, country_code)
        package_name = f"{language_code}_{country_code}"

        # 查找是否已存在
        existing = self.api.get_by_name(package_name)
        if existing:
            return existing["id"]

        # 创建新的定向包
        resp = self.api.create(
            name=package_name,
            country_code=country_code,
            country_name=country_name,
            age_min=18,
            age_max=None,
        )

        if resp.get("code") == 200:
            # 从列表中获取刚创建的
            created = self.api.get_by_name(package_name)
            if created:
                return created["id"]

        raise RuntimeError(f"创建定向包失败: {resp}")

    def list_all(self) -> list[dict]:
        """列出所有定向包"""
        resp = self.api.list(page=1, page_size=100)
        return resp.get("data", {}).get("list", [])
