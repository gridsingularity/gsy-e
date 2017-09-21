from d3a.models.area import Area
from d3a.area_serializer import area_to_string, area_from_string


def test_area_with_children():
    child1 = Area("child1")
    child2 = Area("child2")
    parent = Area("parent", [child1, child2])
    string = area_to_string(parent)
    recovered = area_from_string(string)
    assert recovered.name == "parent"
    assert recovered.children[0].name == "child1"
    assert recovered.children[1].name == "child2"
