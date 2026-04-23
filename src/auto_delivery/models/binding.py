from pydantic import BaseModel
from typing import Optional


class BindingSearchResult(BaseModel):
    """2.1 搜索素材结果"""
    id: int  # 绑定用素材ID
    video_id: str  # 当前已绑定短剧ID


class VideoQueryResult(BaseModel):
    """2.2 查询视频结果"""
    short_play_id: str  # 绑定用短剧ID
    short_play_library_id: str  # 与报表videoId一致


class BindingResult(BaseModel):
    """Step2 绑定结果"""
    material_id: int
    video_id: str
    success: bool
    error_message: Optional[str] = None
