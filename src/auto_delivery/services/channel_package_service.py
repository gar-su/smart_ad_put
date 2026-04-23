from src.auto_delivery.api.channel_package import ChannelPackageApi
from src.auto_delivery.services.audience_service import AudienceService
from src.auto_delivery.constants import LANGUAGE_COUNTRY_MAP, COUNTRY_NAME_MAP


class ChannelPackageService:
    """账户包服务"""

    def __init__(
        self,
        api: ChannelPackageApi | None = None,
        audience_service: AudienceService | None = None,
    ):
        self.api = api or ChannelPackageApi()
        self.audience_service = audience_service or AudienceService()

    def get_or_create_by_language(self, language_code: str) -> int:
        """
        根据语言获取或创建账户包，返回 channelPackageId
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

        # 确保定向包存在
        audience_id = self.audience_service.get_or_create_audience(language_code)

        # 创建新的账户包
        resp = self.api.create(
            package_name=package_name,
            audience_id=audience_id,
        )

        if resp.get("code") == 200:
            # 从列表中获取刚创建的
            created = self.api.get_by_name(package_name)
            if created:
                return created["id"]

        raise RuntimeError(f"创建账户包失败: {resp}")

    def list_all(self) -> list[dict]:
        """列出所有账户包"""
        resp = self.api.list(page=1, page_size=100)
        return resp.get("data", {}).get("list", [])
