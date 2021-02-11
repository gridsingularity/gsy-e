from deepdiff import DeepDiff


def assert_dicts_identical(dict1, dict2):
    assert len(DeepDiff(dict1, dict2, ignore_order=True)) == 0


def assert_lists_contain_same_elements(list1, list2):
    assert set(list1) == set(list2)
