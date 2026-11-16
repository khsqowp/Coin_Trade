from scripts.research.crypto_exhaustive_consensus import (
    RULES, combine_at_bar, enumerate_subsets,
)


def test_subset_enumeration_covers_every_nonempty_combination_once():
    subsets = enumerate_subsets()
    assert len(RULES) == 4
    assert len(subsets) == 15
    assert len(set(subsets)) == 15
    assert [sum(len(s) == k for s in subsets) for k in range(1, 5)] == [4, 6, 4, 1]


def test_strict_majority_requires_more_than_half_of_all_members():
    votes = {RULES[0]: {4: ("long", 90)}, RULES[1]: {4: ("long", 92)},
             RULES[2]: {4: ("short", 110)}, RULES[3]: {}}
    assert combine_at_bar(votes, RULES[:2], 4) == ("long", 91.0)
    split_votes = {RULES[0]: {4: ("long", 90)}, RULES[1]: {4: ("short", 110)},
                   RULES[2]: {}, RULES[3]: {}}
    assert combine_at_bar(split_votes, RULES[:3], 4) is None
    assert combine_at_bar(votes, RULES, 4) is None


def test_majority_tie_is_abstention():
    votes = {RULES[0]: {7: ("long", 90)}, RULES[1]: {7: ("short", 110)}}
    assert combine_at_bar(votes, RULES[:2], 7) is None
