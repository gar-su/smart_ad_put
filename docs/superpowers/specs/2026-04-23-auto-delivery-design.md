# 自动化投放流程设计

## 概述

基于后台接口的本地自动化投放流程，手动触发执行，将达标素材批量绑定短剧并创建广告投放任务。

## 流程概览

```
手动触发执行
    │
    ▼
Step 1: 查询素材报表（最近5天，综合达标率>100，消耗提升明显）
    │
    ▼
Step 2: 绑定素材与短剧
    ├── 2.1 搜索素材获取绑定用ID (id)
    ├── 2.2 查询视频获取绑定用shortPlayId
    └── 2.3 调用绑定接口
    │
    ▼
Step 3: 创建广告投放任务
    ├── 3.1 确认接口 selectVideoCount
    └── 3.2 创建任务 insertOrUpdate
    │
    ▼
汇总报告
```

## 设计决策

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 触发方式 | 手动触发 | 调用一次执行一次 |
| 处理粒度 | 批量 | Step1收集→批量绑定→批量投放 |
| 错误处理 | 全流程完成后汇总报告 | 各步骤失败不中断，用户手动处理 |
| 中间数据 | 持久化 | 每步骤结果落地，便于排查 |
| 认证信息 | 外部配置 | 存配置文件，过期后手动更新 |

## 接口详情

### Step 1: 查询素材报表

**接口**: `POST https://admin.netshort.com/prod-api/put/material/list`

**请求示例**:
```json
{
  "startDate": "2026-04-18",
  "endDate": "2026-04-22",
  "type": 1,
  "pageNum": 1,
  "pageSize": 100
}
```

**筛选条件**:
- `comprehensiveMeetStandardRate` > 100（字符串，如 "126.77%" 需解析为 126.77）
- 消耗提升明显（趋势对比：当日消耗 > 前日消耗）

**输出字段**:
| 字段 | 说明 |
|------|------|
| `materialEmpId` | 素材创建者ID（用于搜索素材） |
| `filename` | 素材名称（用于搜索素材） |
| `videoId` | 短剧Library ID（用于查询视频） |
| `videoName` | 短剧名称（用于查询视频） |
| `languageName` | 素材语言（需映射） |
| `comprehensiveMeetStandardRate` | 综合达标率 |
| `cost` | 消耗金额 |

**分页**: total=67354, pageSize=100，需遍历所有页

---

### Step 2: 绑定素材与短剧

#### 2.1 搜索素材获取绑定用ID

**接口**: `POST https://admin.netshort.com/prod-api/batchput/material/search`

**请求示例**:
```json
{
  "searchType": 1,
  "search": "905_tantanhui_QT_KR_LM009_260414_FF_AISC",
  "tagIds": []
}
```

**输出字段**:
| 字段 | 说明 |
|------|------|
| `id` | 绑定用素材ID |
| `videoId` | 当前已绑定的短剧ID（不是目标的） |

#### 2.2 查询视频获取绑定用shortPlayId

**接口**: `GET https://admin.netshort.com/prod-api/video/shortPlay/pageList`

**请求参数**:
- `shortPlayLibraryName`: 短剧名称（来自Step1的videoName）
- `languages[]`: 语言代码（需映射）

**输出字段**:
| 字段 | 说明 |
|------|------|
| `shortPlayId` | 绑定用短剧ID |
| `shortPlayLibraryId` | 与素材报表的videoId一致 |

#### 2.3 绑定接口

**接口**: `POST https://admin.netshort.com/prod-api/batchput/material/updateBatchVideoId`

**请求示例**:
```json
{
  "materialIds": "[922860]",
  "videoId": "2041826934278586370"
}
```

**说明**:
- `materialIds`: JSON数组序列化后的字符串
- 同 `shortPlayId` 的素材可批量一次请求

---

### Step 3: 创建广告投放任务

#### 3.1 确认接口

**接口**: `POST https://admin.netshort.com/prod-api/batchput/meta/autoTask/selectVideoCount`

**请求示例**:
```json
[{
  "conditionType": 7,
  "conditionRule": 1,
  "conditionValue": "[{\"label\":\"短剧名\",\"value\":\"shortPlayId\"}]"
}]
```

**响应**: `{"code":200,"message":"success","data": 1}` — data为符合条仱的视频数量

**逻辑**: 返回数量 > 0 则继续创建任务

#### 3.2 创建任务接口

**接口**: `POST https://admin.netshort.com/prod-api/batchput/meta/autoTask/insertOrUpdate`

**可变字段**:
| 字段 | 说明 | 示例 |
|------|------|------|
| `taskName` | 任务名称 | `{执行时间}_{短剧名}_{素材数量}` |
| `runConditionList[].conditionValue` | 短剧条件 | `[{"label": videoName, "value": shortPlayId}]` |

**固定字段**:
```json
{
  "status": "ON",
  "validTimeList": [{"startTime": "00:00:00", "endTime": "23:59:59"}],
  "runInterval": 60,
  "stopConditionList": [
    {"conditionType": 2, "conditionValue": 10},
    {"conditionType": 3, "conditionValue": 10}
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
    "rangeSymbol": 1
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
  "bidAmount": null,
  "billingEvent": "IMPRESSIONS",
  "enrollStatus": "OPT_IN",
  "callToActionTypes": "WATCH_MORE",
  "deeplinkUrl": "",
  "creativeFeaturesSpec": "[\"inline_comment\",\"image_templates\",\"image_touchups\",\"video_auto_crop\",\"image_brightness_and_contrast\",\"enhance_cta\",\"text_optimizations\",\"audios\"]",
  "channelPackageId": 6,
  "dailyBudget": "30.00",
  "appStore": "1"
}
```

---

## 配置文件

### 认证信息配置

文件: `config/credentials.json`

```json
{
  "base_url": "https://admin.netshort.com",
  "authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "cookies": "_bl_uid=...; sensorsdata2015jssdkcross=..."
}
```

**说明**: Token和Cookie过期后，手动更新此文件。

### 语言映射配置

```python
LANGUAGE_MAP = {
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
```

---

## ID映射关系总结

| 数据来源 | 素材ID | 短剧ID |
|---------|--------|--------|
| 素材报表 | `materialEmpId` (createdBy) | `videoId` (实际是shortPlayLibraryId) |
| 搜索素材接口 | `id` (绑定用) | `videoId` (当前已绑定，非目标) |
| 查询视频接口 | - | `shortPlayId` (绑定用) |
| 绑定接口参数 | `materialIds` | `videoId` |

---

## 执行流程详解

### Step 1 伪代码
```
for each day in [今天-4, 今天]:
    for page in 1..max:
        resp = POST /put/material/list(startDate=day, endDate=day, pageNum=page)
        for each item in resp.rows:
            if comprehensiveMeetStandardRate > 100 AND 消耗提升明显:
                保存到 qualified_materials
保存 qualified_materials 到文件
```

### Step 2 伪代码
```
grouped = group_by(qualified_materials, videoId)

for each videoId, materials in grouped:
    # 2.1 搜索素材获取绑定用ID
    search_resp = POST /batchput/material/search(search=materials[0].filename)
    material_bind_id = search_resp.materials[0].id

    # 2.2 查询视频获取绑定用shortPlayId
    lang_code = LANGUAGE_MAP[materials[0].languageName]
    video_resp = GET /video/shortPlay/pageList(shortPlayLibraryName=materials[0].videoName, languages=[lang_code])
    short_play_id = video_resp.rows[0].shortPlayId

    # 2.3 绑定
    POST /batchput/material/updateBatchVideoId(
        materialIds=JSON.stringify([material_bind_id]),
        videoId=short_play_id
    )

保存绑定结果
```

### Step 3 伪代码
```
for each (videoId, materials) in grouped:
    short_play_id = ...

    # 3.1 确认
    count_resp = POST /batchput/meta/autoTask/selectVideoCount(runConditionList)
    if count_resp.data <= 0:
        记录失败，跳过

    # 3.2 创建
    task_name = f"{执行时间}_{materials[0].videoName}_{len(materials)}"
    condition_value = JSON.stringify([{"label": materials[0].videoName, "value": short_play_id}])

    POST /batchput/meta/autoTask/insertOrUpdate(
        taskName=task_name,
        runConditionList=[{conditionType:7, conditionRule:1, conditionValue:condition_value}],
        ...固定字段
    )

保存创建结果
```

---

## 错误处理

- 各步骤失败不中断流程
- 全部完成后汇总报告：Step1找到N个、Step2成功M个失败K个、Step3成功P个失败Q个
- 失败记录持久化供排查
