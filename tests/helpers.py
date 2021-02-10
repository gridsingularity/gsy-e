from deepdiff import DeepDiff


def compare_dicts(dict1, dict2):
    return len(DeepDiff(dict1, dict2, ignore_order=True)) == 0


def compare_lists_contain_same_elements(list1, list2):
    return set(list1) == set(list2)
