from src.auto_delivery.constants import LANGUAGE_MAP, DEFAULT_MATERIAL_QUERY_PARAMS, FIXED_DELIVERY_TASK_PARAMS


def test_language_map_has_korean():
    assert LANGUAGE_MAP["韩语"] == "ko_KR"


def test_language_map_has_english():
    assert LANGUAGE_MAP["英语"] == "en_US"


def test_default_params_has_type():
    assert DEFAULT_MATERIAL_QUERY_PARAMS["type"] == 1


def test_fixed_params_has_status():
    assert FIXED_DELIVERY_TASK_PARAMS["status"] == "ON"


def test_fixed_params_has_channel_package_id():
    assert FIXED_DELIVERY_TASK_PARAMS["channelPackageId"] == 6
