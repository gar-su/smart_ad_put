from pydantic import BaseModel, computed_field
from typing import Optional


class QualifiedMaterial(BaseModel):
    """达标素材"""
    filename: str  # 素材名称
    video_name: str  # 短剧名称
    language_name: str  # 语言名称 (如 "韩语")
    material_emp_id: str  # 素材EMP ID (createdBy)
    video_id: str  # 短剧ID (shortPlayLibraryId)
    comprehensive_meet_standard_rate: float  # 综合达标率
    cost: float  # 消耗金额
    cost_yesterday: Optional[float] = None  # 昨日消耗(趋势判断用)

    @computed_field
    @property
    def language_code(self) -> str:
        from ..constants import LANGUAGE_MAP
        return LANGUAGE_MAP.get(self.language_name, "en_US")


class MaterialQueryResult(BaseModel):
    """Step1 查询结果"""
    total: int
    rows: list[dict]
