from datetime import datetime
from src.auto_delivery.services.delivery_service import DeliveryService


def test_build_task_name():
    service = DeliveryService()
    name = service.build_task_name("Test Drama", 5)
    assert "Test Drama" in name
    assert "5" in name
    assert datetime.now().strftime("%Y%m%d") in name
