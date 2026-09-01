# Auto Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a local CLI tool that automates the ad delivery workflow: query qualified materials, bind them to short dramas, and create ad delivery tasks.

**Architecture:** Python CLI application using httpx for HTTP calls, Pydantic for models, JSON files for persistence. API clients wrap HTTP calls, services contain business logic, and a runner orchestrates the flow.

**Tech Stack:** Python 3.13+, httpx, pydantic, pyyaml, pathlib

---

## File Structure

```
config/
  credentials.json          # Auth tokens (user-managed)
  credentials.example.json  # Template

src/
  auto_delivery/
    __init__.py
    api/
      __init__.py
      client.py            # Base HTTP client
      material.py          # Step1 material report API
      binding.py           # Step2 binding APIs (search, video query, bind)
      delivery.py          # Step3 delivery task APIs
    models/
      __init__.py
      material.py          # QualifiedMaterial model
      binding.py          # BindingResult model
      delivery.py          # TaskResult model
    services/
      __init__.py
      material_service.py   # Step1: query and filter materials
      binding_service.py   # Step2: bind materials to dramas
      delivery_service.py  # Step3: create ad tasks
    runner.py              # Main entry point
    constants.py            # Language map, fixed config values

tests/
  auto_delivery/
    __init__.py
    test_material_service.py
    test_binding_service.py
    test_delivery_service.py
```

---

## Task 1: Project Setup - Credentials Config

**Files:**
- Create: `config/credentials.example.json`
- Create: `config/credentials.json` (user creates from example)

- [ ] **Step 1: Create credentials template**

```json
{
  "base_url": "https://admin.netshort.com",
  "authorization": "Bearer YOUR_TOKEN_HERE",
  "cookies": "_bl_uid=xxx; sensorsdata2015jssdkcross=xxx; ..."
}
```

- [ ] **Step 2: Commit**

```bash
git add config/credentials.example.json
git commit -m "feat(auto-delivery): add credentials template"
```

---

## Task 2: Base API Client

**Files:**
- Create: `src/auto_delivery/__init__.py`
- Create: `src/auto_delivery/api/__init__.py`
- Create: `src/auto_delivery/api/client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/auto_delivery/__init__.py
# tests/auto_delivery/test_client.py
import pytest
from src.auto_delivery.api.client import ApiClient

def test_client_loads_credentials():
    client = ApiClient()
    assert client.base_url == "https://admin.netshort.com"
    assert client.authorization.startswith("Bearer ")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/auto_delivery/test_client.py::test_client_loads_credentials -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: Write minimal implementation**

```python
# src/auto_delivery/__init__.py
```

```python
# src/auto_delivery/api/__init__.py
```

```python
# src/auto_delivery/api/client.py
import json
from pathlib import Path
import httpx
from config.settings import settings

class ApiClient:
    def __init__(self, credentials_path: Path | None = None):
        cred_path = credentials_path or settings.BASE_DIR / "config" / "credentials.json"
        with open(cred_path) as f:
            creds = json.load(f)
        self.base_url = creds["base_url"]
        self.authorization = creds["authorization"]
        self.cookies = creds.get("cookies", "")

    def _build_headers(self) -> dict:
        return {
            "Authorization": self.authorization,
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Content-Language": "zh_CN",
            "Cookie": self.cookies,
        }

    def post(self, path: str, json: dict) -> dict:
        url = f"{self.base_url}{path}"
        with httpx.Client() as client:
            resp = client.post(url, json=json, headers=self._build_headers())
            resp.raise_for_status()
            return resp.json()

    def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        with httpx.Client() as client:
            resp = client.get(url, params=params, headers=self._build_headers())
            resp.raise_for_status()
            return resp.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/auto_delivery/test_client.py::test_client_loads_credentials -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_delivery/
git commit -m "feat(auto-delivery): add base API client"
```

---

## Task 3: Constants Module

**Files:**
- Create: `src/auto_delivery/constants.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/auto_delivery/test_constants.py
from src.auto_delivery.constants import LANGUAGE_MAP, DEFAULT_MATERIAL_QUERY_PARAMS

def test_language_map_has_korean():
    assert LANGUAGE_MAP["韩语"] == "ko_KR"

def test_default_params_has_type():
    assert DEFAULT_MATERIAL_QUERY_PARAMS["type"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/auto_delivery/test_constants.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/auto_delivery/constants.py

LANGUAGE_MAP: dict[str, str] = {
    "韩语": "ko_KR",
    "英语": "en_US",
    "日语": "ja_JP",
    "泰语": "th_TH",
    "越南语": "vi_VN",
    "阿拉伯语": "ar_AE",
    "德语": "de_DE",
    "西班牙语": "es_ES",
    "法语": "fr_FR",
    "印地语": "hi_IN",
    "印度尼西亚语": "id_ID",
    "意大利语": "it_IT",
    "马来西亚语": "ms_MY",
    "葡萄牙语": "pt_PT",
    "土耳其语": "tr_TR",
    "简体中文": "zh_CN",
    "繁体中文": "zh_TW",
}

DEFAULT_MATERIAL_QUERY_PARAMS: dict = {
    "type": 1,
    "pageSize": 100,
    "deptOrUser": "",
    "createBy": "",
    "deptIds": [],
    "videoIds": [],
    "linkIds": [],
    "weatherNewShortPlay": None,
    "today": "",
    "materialAccount": "",
    "channelNoFilterType": 1,
    "channelNos": [],
}

FIXED_DELIVERY_TASK_PARAMS: dict = {
    "status": "ON",
    "validTimeList": [{"startTime": "00:00:00", "endTime": "23:59:59"}],
    "runInterval": 60,
    "stopConditionList": [
        {"conditionType": 2, "conditionValue": 10},
        {"conditionType": 3, "conditionValue": 10},
    ],
    "materialRule": {
        "materialRuleType": 2,
        "sortType": "2",
        "materialDeliveryTimeType": 3,
        "materialCreateOrDeliveryDays": 3,
        "materialCountType": 1,
        "materialRepeatType": 2,
        "materialRepeatNum": 1,
        "adSetNum": 1,
        "adMaterialNum": 30,
        "materialCostType": 1,
        "rangeType": 2,
        "rangeSymbol": 1,
    },
    "objective": "OUTCOME_SALES",
    "budgetStrategy": 1,
    "budgetType": 1,
    "buyingType": "AUCTION",
    "bidStrategy": "LOWEST_COST_WITHOUT_CAP",
    "spendCapType": 1,
    "applicationId": "",
    "objectStoreUrl": "http://play.google.com/store/apps/details?id=com.netshort.abroad",
    "optimizationGoal": "VALUE",
    "attributionSpec": "[{\"event_type\":\"CLICK_THROUGH\",\"window_days\":7}]",
    "attributionSpecValue": "1",
    "customEventType": "PURCHASE",
    "bidAmount": None,
    "billingEvent": "IMPRESSIONS",
    "enrollStatus": "OPT_IN",
    "callToActionTypes": "WATCH_MORE",
    "deeplinkUrl": "",
    "creativeFeaturesSpec": "[\"inline_comment\",\"image_templates\",\"image_touchups\",\"video_auto_crop\",\"image_brightness_and_contrast\",\"enhance_cta\",\"text_optimizations\",\"audios\"]",
    "channelPackageId": 6,
    "dailyBudget": "30.00",
    "appStore": "1",
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/auto_delivery/test_constants.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_delivery/constants.py
git commit -m "feat(auto-delivery): add constants (language map, fixed params)"
```

---

## Task 4: Domain Models

**Files:**
- Create: `src/auto_delivery/models/__init__.py`
- Create: `src/auto_delivery/models/material.py`
- Create: `src/auto_delivery/models/binding.py`
- Create: `src/auto_delivery/models/delivery.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/auto_delivery/test_models.py
from src.auto_delivery.models.material import QualifiedMaterial
from src.auto_delivery.models.binding import BindingResult
from src.auto_delivery.models.delivery import DeliveryTaskResult

def test_qualified_material_has_required_fields():
    m = QualifiedMaterial(
        filename="test_material",
        video_name="Test Drama",
        language_name="英语",
        material_emp_id="123",
        video_id="456",
        comprehensive_meet_standard_rate=120.5,
        cost=100.0,
    )
    assert m.filename == "test_material"
    assert m.language_code == "en_US"

def test_binding_result_tracks_success():
    r = BindingResult(material_id=123, video_id="456", success=True)
    assert r.success is True

def test_delivery_task_result_tracks_success():
    r = DeliveryTaskResult(task_name="test_task", short_play_id="123", success=True)
    assert r.success is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/auto_delivery/test_models.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/auto_delivery/models/__init__.py
from .material import QualifiedMaterial, MaterialQueryResult
from .binding import BindingResult, BindingSearchResult, VideoQueryResult
from .delivery import DeliveryTaskResult, DeliveryConfirmResult
```

```python
# src/auto_delivery/models/material.py
from pydantic import BaseModel
from typing import Optional

class QualifiedMaterial(BaseModel):
    """达标素材"""
    filename: str                      # 素材名称
    video_name: str                    # 短剧名称
    language_name: str                # 语言名称 (如 "韩语")
    material_emp_id: str              # 素材EMP ID (createdBy)
    video_id: str                     # 短剧ID (shortPlayLibraryId)
    comprehensive_meet_standard_rate: float  # 综合达标率
    cost: float                       # 消耗金额
    cost_yesterday: Optional[float] = None  # 昨日消耗(趋势判断用)

    @property
    def language_code(self) -> str:
        from ..constants import LANGUAGE_MAP
        return LANGUAGE_MAP.get(self.language_name, "en_US")

class MaterialQueryResult(BaseModel):
    """Step1 查询结果"""
    total: int
    rows: list[dict]
```

```python
# src/auto_delivery/models/binding.py
from pydantic import BaseModel
from typing import Optional

class BindingSearchResult(BaseModel):
    """2.1 搜索素材结果"""
    id: int                    # 绑定用素材ID
    video_id: str              # 当前已绑定短剧ID

class VideoQueryResult(BaseModel):
    """2.2 查询视频结果"""
    short_play_id: str          # 绑定用短剧ID
    short_play_library_id: str # 与报表videoId一致

class BindingResult(BaseModel):
    """Step2 绑定结果"""
    material_id: int
    video_id: str
    success: bool
    error_message: Optional[str] = None
```

```python
# src/auto_delivery/models/delivery.py
from pydantic import BaseModel
from typing import Optional

class DeliveryConfirmResult(BaseModel):
    """Step3.1 确认结果"""
    count: int
    can_proceed: bool

class DeliveryTaskResult(BaseModel):
    """Step3 创建任务结果"""
    task_name: str
    short_play_id: str
    success: bool
    error_message: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/auto_delivery/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_delivery/models/
git commit -m "feat(auto-delivery): add domain models"
```

---

## Task 5: Material Report API (Step1)

**Files:**
- Create: `src/auto_delivery/api/material.py`

- [ ] **Step 1: Write failing test**

```python
# tests/auto_delivery/test_material_api.py
from src.auto_delivery.api.material import MaterialReportApi

def test_material_api_query_returns_data():
    api = MaterialReportApi()
    # Will need to mock httpx - use respx or patch
```

- [ ] **Step 2: Write implementation (no test yet - will add integration test later)**

```python
# src/auto_delivery/api/material.py
from ..api.client import ApiClient
from datetime import date, timedelta
from typing import Iterator

class MaterialReportApi:
    API_PATH = "/prod-api/put/material/list"

    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient()

    def query_day(self, query_date: date) -> dict:
        """查询某一天的素材报表"""
        params = {
            "startDate": query_date.isoformat(),
            "endDate": query_date.isoformat(),
            "pageNum": 1,
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
```

- [ ] **Step 3: Commit**

```bash
git add src/auto_delivery/api/material.py
git commit -m "feat(auto-delivery): add material report API (Step1)"
```

---

## Task 6: Binding APIs (Step2)

**Files:**
- Create: `src/auto_delivery/api/binding.py`

- [ ] **Step 1: Write implementation**

```python
# src/auto_delivery/api/binding.py
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
```

- [ ] **Step 2: Commit**

```bash
git add src/auto_delivery/api/binding.py
git commit -m "feat(auto-delivery): add binding APIs (Step2)"
```

---

## Task 7: Delivery Task APIs (Step3)

**Files:**
- Create: `src/auto_delivery/api/delivery.py`

- [ ] **Step 1: Write implementation**

```python
# src/auto_delivery/api/delivery.py
import json
from datetime import datetime
from ..api.client import ApiClient

class DeliveryApi:
    CONFIRM_API_PATH = "/prod-api/batchput/meta/autoTask/selectVideoCount"
    CREATE_API_PATH = "/prod-api/batchput/meta/autoTask/insertOrUpdate"

    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient()

    def confirm(self, short_play_name: str, short_play_id: str) -> dict:
        """3.1 确认接口"""
        condition_value = json.dumps([{"label": short_play_name, "value": short_play_id}])
        params = [{
            "conditionType": 7,
            "conditionRule": 1,
            "conditionValue": condition_value,
        }]
        return self.client.post(self.CONFIRM_API_PATH, json=params)

    def create_task(
        self,
        task_name: str,
        short_play_name: str,
        short_play_id: str,
        created_by: str,
    ) -> dict:
        """3.2 创建投放任务"""
        from ..constants import FIXED_DELIVERY_TASK_PARAMS

        condition_value = json.dumps([{"label": short_play_name, "value": short_play_id}])
        valid_time = json.dumps([{"endTime": "23:59:59", "startTime": "00:00:00"}])
        run_condition = json.dumps([{
            "conditionRule": 1,
            "conditionType": 7,
            "conditionValue": condition_value,
        }])
        stop_condition = json.dumps([
            {"conditionType": 2, "conditionValue": 10},
            {"conditionType": 3, "conditionValue": 10},
        ])

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        params = {
            **FIXED_DELIVERY_TASK_PARAMS,
            "taskName": task_name,
            "runConditionList": [{
                "conditionType": 7,
                "conditionRule": 1,
                "conditionValue": condition_value,
            }],
            "validTime": valid_time,
            "runCondition": run_condition,
            "stopCondition": stop_condition,
            "lastFinishTime": now,
            "createdBy": created_by,
            "updatedBy": created_by,
        }
        return self.client.post(self.CREATE_API_PATH, json=params)
```

- [ ] **Step 2: Commit**

```bash
git add src/auto_delivery/api/delivery.py
git commit -m "feat(auto-delivery): add delivery task APIs (Step3)"
```

---

## Task 8: Material Service (Step1 Logic)

**Files:**
- Create: `src/auto_delivery/services/__init__.py`
- Create: `src/auto_delivery/services/material_service.py`
- Create: `tests/auto_delivery/test_material_service.py`

- [ ] **Step 1: Write failing test**

```python
# tests/auto_delivery/test_material_service.py
import pytest
from datetime import date
from src.auto_delivery.services.material_service import MaterialService
from src.auto_delivery.models.material import QualifiedMaterial

def test_filter_comprehensive_rate_over_100():
    service = MaterialService()
    items = [
        {"filename": "m1", "comprehensiveMeetStandardRate": "150.5%", "cost": "100"},
        {"filename": "m2", "comprehensiveMeetStandardRate": "80.0%", "cost": "100"},
    ]
    # Test internal filter logic
    assert service._rate_over_100(items[0]) is True
    assert service._rate_over_100(items[1]) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/auto_delivery/test_material_service.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/auto_delivery/services/__init__.py
```

```python
# src/auto_delivery/services/material_service.py
import json
from datetime import date, timedelta
from pathlib import Path
from src.auto_delivery.api.material import MaterialReportApi
from src.auto_delivery.models.material import QualifiedMaterial, MaterialQueryResult

class MaterialService:
    def __init__(self, api: MaterialReportApi | None = None):
        self.api = api or MaterialReportApi()

    def _rate_over_100(self, item: dict) -> bool:
        """判断综合达标率是否大于100"""
        rate_str = item.get("comprehensiveMeetStandardRate", "0%")
        rate = float(rate_str.rstrip("%"))
        return rate > 100

    def _cost_increasing(self, item: dict, yesterday_cost: float | None) -> bool:
        """判断消耗是否提升"""
        if yesterday_cost is None:
            return False
        current_cost = float(item.get("cost", "0"))
        return current_cost > yesterday_cost

    def _parse_material(self, item: dict, yesterday_cost: float | None = None) -> QualifiedMaterial | None:
        """解析单条素材记录"""
        try:
            if not self._rate_over_100(item):
                return None
            return QualifiedMaterial(
                filename=item["filename"],
                video_name=item["videoName"],
                language_name=item["languageName"],
                material_emp_id=item["materialEmpId"],
                video_id=item["videoId"],
                comprehensive_meet_standard_rate=float(item["comprehensiveMeetStandardRate"].rstrip("%")),
                cost=float(item["cost"]),
                cost_yesterday=yesterday_cost,
            )
        except (KeyError, ValueError):
            return None

    def query_qualified_materials(self, days: int = 5) -> list[QualifiedMaterial]:
        """查询最近N天达标素材"""
        all_materials: list[QualifiedMaterial] = []
        today = date.today()

        for i in range(days):
            query_date = today - timedelta(days=i)
            resp = self.api.query_day(query_date)
            rows = resp.get("materialCostPage", {}).get("rows", [])

            yesterday_cost_map: dict[str, float] = {}
            if i > 0:
                yesterday_date = today - timedelta(days=i - 1)
                yesterday_resp = self.api.query_day(yesterday_date)
                yesterday_rows = yesterday_resp.get("materialCostPage", {}).get("rows", [])
                for row in yesterday_rows:
                    yesterday_cost_map[row["filename"]] = float(row.get("cost", "0"))

            for item in rows:
                material = self._parse_material(item, yesterday_cost_map.get(item["filename"]))
                if material and self._cost_increasing(item, yesterday_cost_map.get(item["filename"])):
                    all_materials.append(material)

        return all_materials

    def save_to_file(self, materials: list[QualifiedMaterial], output_path: Path) -> None:
        """保存达标素材到文件"""
        data = [m.model_dump() for m in materials]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self, input_path: Path) -> list[QualifiedMaterial]:
        """从文件加载达标素材"""
        with open(input_path, encoding="utf-8") as f:
            data = json.load(f)
        return [QualifiedMaterial(**item) for item in data]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/auto_delivery/test_material_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_delivery/services/material_service.py tests/auto_delivery/test_material_service.py
git commit -m "feat(auto-delivery): add material service (Step1 logic)"
```

---

## Task 9: Binding Service (Step2 Logic)

**Files:**
- Create: `src/auto_delivery/services/binding_service.py`
- Create: `tests/auto_delivery/test_binding_service.py`

- [ ] **Step 1: Write failing test**

```python
# tests/auto_delivery/test_binding_service.py
import pytest
from src.auto_delivery.services.binding_service import BindingService
from src.auto_delivery.models.material import QualifiedMaterial

def test_group_by_video():
    service = BindingService()
    materials = [
        QualifiedMaterial(filename="m1", video_name="drama1", language_name="韩语",
                         material_emp_id="1", video_id="v1", comprehensive_meet_standard_rate=120, cost=100),
        QualifiedMaterial(filename="m2", video_name="drama1", language_name="韩语",
                         material_emp_id="2", video_id="v1", comprehensive_meet_standard_rate=130, cost=110),
        QualifiedMaterial(filename="m3", video_name="drama2", language_name="英语",
                         material_emp_id="3", video_id="v2", comprehensive_meet_standard_rate=140, cost=120),
    ]
    grouped = service.group_by_video(materials)
    assert len(grouped) == 2
    assert len(grouped["v1"]) == 2
    assert len(grouped["v2"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/auto_delivery/test_binding_service.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/auto_delivery/services/binding_service.py
import json
from collections import defaultdict
from pathlib import Path
from src.auto_delivery.api.binding import BindingApi
from src.auto_delivery.models.material import QualifiedMaterial
from src.auto_delivery.models.binding import BindingResult

class BindingService:
    def __init__(self, api: BindingApi | None = None):
        self.api = api or BindingApi()

    def group_by_video(self, materials: list[QualifiedMaterial]) -> dict[str, list[QualifiedMaterial]]:
        """按videoId分组素材"""
        grouped = defaultdict(list)
        for m in materials:
            grouped[m.video_id].append(m)
        return dict(grouped)

    def get_bind_id(self, filename: str) -> int | None:
        """2.1 获取绑定用素材ID"""
        resp = self.api.search_material(filename)
        materials = resp.get("data", {}).get("materials", [])
        if materials:
            return materials[0]["id"]
        return None

    def get_short_play_id(self, video_name: str, language_code: str) -> str | None:
        """2.2 获取绑定用shortPlayId"""
        resp = self.api.query_video(video_name, language_code)
        rows = resp.get("rows", [])
        for row in rows:
            if row.get("shortPlayLibraryId"):
                return row["shortPlayId"]
        return None

    def bind_materials(self, materials: list[QualifiedMaterial]) -> list[BindingResult]:
        """批量绑定素材到短剧"""
        results = []
        for m in materials:
            bind_id = self.get_bind_id(m.filename)
            if not bind_id:
                results.append(BindingResult(
                    material_id=int(m.material_emp_id),
                    video_id=m.video_id,
                    success=False,
                    error_message=f"未找到素材绑定ID: {m.filename}",
                ))
                continue

            short_play_id = self.get_short_play_id(m.video_name, m.language_code)
            if not short_play_id:
                results.append(BindingResult(
                    material_id=bind_id,
                    video_id=m.video_id,
                    success=False,
                    error_message=f"未找到shortPlayId: {m.video_name}",
                ))
                continue

            resp = self.api.bind_material(bind_id, short_play_id)
            if resp.get("code") == 200:
                results.append(BindingResult(
                    material_id=bind_id,
                    video_id=short_play_id,
                    success=True,
                ))
            else:
                results.append(BindingResult(
                    material_id=bind_id,
                    video_id=short_play_id,
                    success=False,
                    error_message=resp.get("message", "绑定失败"),
                ))

        return results

    def save_results(self, results: list[BindingResult], output_path: Path) -> None:
        """保存绑定结果"""
        data = [r.model_dump() for r in results]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_results(self, input_path: Path) -> list[BindingResult]:
        """加载绑定结果"""
        with open(input_path, encoding="utf-8") as f:
            data = json.load(f)
        return [BindingResult(**item) for item in data]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/auto_delivery/test_binding_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_delivery/services/binding_service.py tests/auto_delivery/test_binding_service.py
git commit -m "feat(auto-delivery): add binding service (Step2 logic)"
```

---

## Task 10: Delivery Service (Step3 Logic)

**Files:**
- Create: `src/auto_delivery/services/delivery_service.py`
- Create: `tests/auto_delivery/test_delivery_service.py`

- [ ] **Step 1: Write failing test**

```python
# tests/auto_delivery/test_delivery_service.py
from datetime import datetime
from src.auto_delivery.services.delivery_service import DeliveryService

def test_build_task_name():
    service = DeliveryService()
    name = service.build_task_name("Test Drama", 5)
    assert "Test Drama" in name
    assert "5" in name
    assert datetime.now().strftime("%Y%m%d") in name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/auto_delivery/test_delivery_service.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/auto_delivery/services/delivery_service.py
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from src.auto_delivery.api.delivery import DeliveryApi
from src.auto_delivery.models.binding import BindingResult
from src.auto_delivery.models.delivery import DeliveryTaskResult

class DeliveryService:
    def __init__(self, api: DeliveryApi | None = None):
        self.api = api or DeliveryApi()

    def build_task_name(self, video_name: str, material_count: int) -> str:
        """构建任务名称: 执行日期_短剧名_素材数量"""
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{date_str}_{video_name}_{material_count}"

    def group_by_video(self, binding_results: list[BindingResult]) -> dict[str, list[BindingResult]]:
        """按shortPlayId分组成功的绑定结果"""
        grouped = defaultdict(list)
        for r in binding_results:
            if r.success:
                grouped[r.video_id].append(r)
        return dict(grouped)

    def confirm_and_create(
        self,
        video_name: str,
        video_id: str,
        material_ids: list[int],
        created_by: str,
    ) -> DeliveryTaskResult:
        """3.1 确认 + 3.2 创建任务"""
        confirm_resp = self.api.confirm(video_name, video_id)
        count = confirm_resp.get("data", 0)

        if count <= 0:
            return DeliveryTaskResult(
                task_name="",
                short_play_id=video_id,
                success=False,
                error_message=f"确认失败: 符合条件的视频数量为 {count}",
            )

        task_name = self.build_task_name(video_name, len(material_ids))
        create_resp = self.api.create_task(task_name, video_name, video_id, created_by)

        if create_resp.get("code") == 200:
            return DeliveryTaskResult(
                task_name=task_name,
                short_play_id=video_id,
                success=True,
            )
        else:
            return DeliveryTaskResult(
                task_name=task_name,
                short_play_id=video_id,
                success=False,
                error_message=create_resp.get("message", "创建任务失败"),
            )

    def create_tasks(
        self,
        binding_results: list[BindingResult],
        video_name_map: dict[str, str],
        created_by: str,
    ) -> list[DeliveryTaskResult]:
        """批量创建投放任务"""
        grouped = self.group_by_video(binding_results)
        task_results = []

        for video_id, results in grouped.items():
            material_ids = [r.material_id for r in results]
            video_name = video_name_map.get(video_id, video_id)

            result = self.confirm_and_create(video_name, video_id, material_ids, created_by)
            task_results.append(result)

        return task_results

    def save_results(self, results: list[DeliveryTaskResult], output_path: Path) -> None:
        """保存投放任务结果"""
        data = [r.model_dump() for r in results]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/auto_delivery/test_delivery_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_delivery/services/delivery_service.py tests/auto_delivery/test_delivery_service.py
git commit -m "feat(auto-delivery): add delivery service (Step3 logic)"
```

---

## Task 11: Main Runner

**Files:**
- Create: `src/auto_delivery/runner.py`
- Create: `tests/auto_delivery/test_runner_integration.py` (basic smoke test)

- [ ] **Step 1: Write runner implementation**

```python
# src/auto_delivery/runner.py
import json
from datetime import datetime
from pathlib import Path
from config.settings import settings
from src.auto_delivery.services.material_service import MaterialService
from src.auto_delivery.services.binding_service import BindingService
from src.auto_delivery.services.delivery_service import DeliveryService

class AutoDeliveryRunner:
    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or settings.BASE_DIR / "output" / "auto_delivery"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.material_service = MaterialService()
        self.binding_service = BindingService()
        self.delivery_service = DeliveryService()

    def _get_timestamp(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def run(self, days: int = 5, created_by: str = "2030896251477688321") -> dict:
        """执行完整流程"""
        results = {
            "step1_materials_found": 0,
            "step2_bind_success": 0,
            "step2_bind_failed": 0,
            "step3_create_success": 0,
            "step3_create_failed": 0,
            "errors": [],
        }

        # Step 1: 查询达标素材
        print("[Step1] 查询达标素材...")
        materials = self.material_service.query_qualified_materials(days=days)
        results["step1_materials_found"] = len(materials)

        materials_file = self.output_dir / f"step1_materials_{self._get_timestamp()}.json"
        self.material_service.save_to_file(materials, materials_file)
        print(f"[Step1] 找到 {len(materials)} 个达标素材，已保存到 {materials_file}")

        if not materials:
            results["errors"].append("Step1: 没有找到达标素材")
            return results

        # Step 2: 绑定素材
        print("[Step2] 绑定素材到短剧...")
        binding_results = self.binding_service.bind_materials(materials)
        success_bindings = [r for r in binding_results if r.success]
        failed_bindings = [r for r in binding_results if not r.success]
        results["step2_bind_success"] = len(success_bindings)
        results["step2_bind_failed"] = len(failed_bindings)

        bindings_file = self.output_dir / f"step2_bindings_{self._get_timestamp()}.json"
        self.binding_service.save_results(binding_results, bindings_file)
        print(f"[Step2] 绑定成功 {len(success_bindings)} 个，失败 {len(failed_bindings)} 个，已保存到 {bindings_file}")

        if not success_bindings:
            results["errors"].append("Step2: 没有成功绑定的素材")
            return results

        # Step 3: 创建投放任务
        print("[Step3] 创建广告投放任务...")
        video_name_map = {m.video_id: m.video_name for m in materials}
        task_results = self.delivery_service.create_tasks(binding_results, video_name_map, created_by)
        success_tasks = [r for r in task_results if r.success]
        failed_tasks = [r for r in task_results if not r.success]
        results["step3_create_success"] = len(success_tasks)
        results["step3_create_failed"] = len(failed_tasks)

        tasks_file = self.output_dir / f"step3_tasks_{self._get_timestamp()}.json"
        self.delivery_service.save_results(task_results, tasks_file)
        print(f"[Step3] 创建成功 {len(success_tasks)} 个任务，失败 {len(failed_tasks)} 个，已保存到 {tasks_file}")

        # 汇总
        print("\n=== 执行汇总 ===")
        print(f"Step1: 找到 {results['step1_materials_found']} 个达标素材")
        print(f"Step2: 绑定成功 {results['step2_bind_success']} 个，失败 {results['step2_bind_failed']} 个")
        print(f"Step3: 创建成功 {results['step3_create_success']} 个，失败 {results['step3_create_failed']} 个")
        if results["errors"]:
            print(f"错误: {results['errors']}")

        return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="自动化投放流程")
    parser.add_argument("--days", type=int, default=5, help="查询天数")
    parser.add_argument("--created-by", type=str, default="2030896251477688321", help="创建人ID")
    args = parser.parse_args()

    runner = AutoDeliveryRunner()
    runner.run(days=args.days, created_by=args.created_by)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add src/auto_delivery/runner.py
git commit -m "feat(auto-delivery): add main runner with CLI entry point"
```

---

## Task 12: Final Integration - Test Import

**Files:**
- Create: `tests/auto_delivery/test_integration_imports.py`

- [ ] **Step 1: Verify all imports work**

```bash
cd /Users/gar/projects/smart_ad_put
python -c "from src.auto_delivery.runner import AutoDeliveryRunner; print('OK')"
```

Expected: OK (if credentials.json exists and is valid)

- [ ] **Step 2: Commit if any changes needed**

```bash
git add -A
git commit -m "feat(auto-delivery): complete implementation"
```

---

## Self-Review Checklist

- [ ] Spec coverage: All 3 steps implemented
  - Step1: MaterialService ✓
  - Step2: BindingService ✓
  - Step3: DeliveryService ✓
- [ ] Placeholder scan: No TBD/TODO in code
- [ ] Type consistency: All model field names match API response fields
- [ ] File structure: Each module has single responsibility
- [ ] Tests: Unit tests for services

---

## Execution Options

**Plan complete and saved to `docs/superpowers/plans/2026-04-23-auto-delivery-implementation-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
