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
