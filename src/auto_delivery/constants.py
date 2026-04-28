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

# 语言代码到国家代码的映射（用于按语言分流到不同账户包）
LANGUAGE_COUNTRY_MAP: dict[str, str] = {
    "ko_KR": "KR",  # 韩语→韩国
    "en_US": "US",  # 英语→美国
    "ja_JP": "JP",  # 日语→日本
    "th_TH": "TH",  # 泰语→泰国
    "vi_VN": "VN",  # 越南语→越南
    "ar_AE": "AE",  # 阿拉伯语→阿联酋
    "de_DE": "DE",  # 德语→德国
    "es_ES": "ES",  # 西班牙语→西班牙
    "fr_FR": "FR",  # 法语→法国
    "hi_IN": "IN",  # 印地语→印度
    "id_ID": "ID",  # 印尼语→印尼
    "it_IT": "IT",  # 意大利语→意大利
    "ms_MY": "MY",  # 马来语→马来西亚
    "pt_PT": "PT",  # 葡萄牙语→葡萄牙
    "tr_TR": "TR",  # 土耳其语→土耳其
    "zh_CN": "CN",  # 简体中文→中国
    "zh_TW": "TW",  # 繁体中文→台湾
}

# 国家代码到国家名称的映射
COUNTRY_NAME_MAP: dict[str, str] = {
    "KR": "韩国",
    "US": "美国",
    "JP": "日本",
    "TH": "泰国",
    "VN": "越南",
    "AE": "阿联酋",
    "DE": "德国",
    "ES": "西班牙",
    "FR": "法国",
    "IN": "印度",
    "ID": "印度尼西亚",
    "IT": "意大利",
    "MY": "马来西亚",
    "PT": "葡萄牙",
    "TR": "土耳其",
    "CN": "中国",
    "TW": "台湾",
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
        "adMaterialNum": 3,
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
    # channelPackageId is now set dynamically based on language
    "dailyBudget": "30.00",
    "appStore": "1",
}
