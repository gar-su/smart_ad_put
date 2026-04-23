import pytest
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


def test_qualified_material_korean():
    m = QualifiedMaterial(
        filename="test_material",
        video_name="Test Drama",
        language_name="韩语",
        material_emp_id="123",
        video_id="456",
        comprehensive_meet_standard_rate=120.5,
        cost=100.0,
    )
    assert m.language_code == "ko_KR"


def test_binding_result_tracks_success():
    r = BindingResult(material_id=123, video_id="456", success=True)
    assert r.success is True
    assert r.error_message is None


def test_binding_result_tracks_failure():
    r = BindingResult(material_id=123, video_id="456", success=False, error_message="Not found")
    assert r.success is False
    assert r.error_message == "Not found"


def test_delivery_task_result_tracks_success():
    r = DeliveryTaskResult(task_name="test_task", short_play_id="123", success=True)
    assert r.success is True


def test_delivery_task_result_tracks_failure():
    r = DeliveryTaskResult(task_name="test_task", short_play_id="123", success=False, error_message="Confirm failed")
    assert r.success is False
    assert r.error_message == "Confirm failed"
