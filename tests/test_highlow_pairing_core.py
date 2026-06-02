# -*- coding: utf-8 -*-
"""Pure-Python tests for highlow_pairing_core (no bpy)."""

import unittest

from core.highlow_pairing_core import plan_high_low_pairs, complexity_of


def _lh(pair):
    """(low_name, high_name) tuple from a pair dict, ignoring poly/ambiguous."""
    return (pair["low"], pair["high"])


class _FakeData:
    def __init__(self, polys=0, verts=0):
        self.polygons = [0] * polys
        self.vertices = [0] * verts


class _FakeObj:
    def __init__(self, name, polys=0, verts=0):
        self.name = name
        self.data = _FakeData(polys, verts)


class ComplexityTests(unittest.TestCase):
    def test_prefers_polygon_count(self):
        self.assertEqual(complexity_of(_FakeObj("a", polys=12, verts=99)), 12)

    def test_falls_back_to_vertices(self):
        self.assertEqual(complexity_of(_FakeObj("a", polys=0, verts=7)), 7)

    def test_no_data(self):
        obj = _FakeObj("a")
        obj.data = None
        self.assertEqual(complexity_of(obj), 0)


class PlanHighLowPairsTests(unittest.TestCase):
    def test_even_count_all_paired(self):
        plan = plan_high_low_pairs([("low1", 10), ("high1", 100),
                                    ("low2", 20), ("high2", 200)])
        self.assertTrue(plan.ok)
        self.assertEqual(len(plan.pairs), 2)
        self.assertEqual(plan.leftovers, [])
        # ordered by complexity: low1(10), low2(20), high1(100), high2(200)
        # lows=[low1,low2], highs=[high1,high2] -> low1-high1, low2-high2
        self.assertEqual(_lh(plan.pairs[0]), ("low1", "high1"))
        self.assertEqual(_lh(plan.pairs[1]), ("low2", "high2"))
        # poly counts are carried through and nothing is ambiguous here
        self.assertEqual(plan.pairs[0]["low_polys"], 10)
        self.assertEqual(plan.pairs[0]["high_polys"], 100)
        self.assertFalse(plan.pairs[0]["ambiguous"])
        self.assertEqual(plan.ambiguous_pairs, [])

    def test_odd_count_leaves_leftover_and_not_ok(self):
        plan = plan_high_low_pairs([("a", 1), ("b", 2), ("c", 3)])
        self.assertFalse(plan.ok)
        self.assertEqual(plan.error_kind, "unpaired_objects")
        self.assertEqual(plan.leftovers, ["c"])
        # a draft pairing is still computed for the caller's reference
        self.assertEqual(len(plan.pairs), 1)

    def test_fewer_than_two_objects(self):
        plan = plan_high_low_pairs([("only", 5)])
        self.assertFalse(plan.ok)
        self.assertEqual(plan.error_kind, "not_enough_objects")
        self.assertEqual(plan.leftovers, ["only"])
        self.assertEqual(plan.pairs, [])

    def test_empty(self):
        plan = plan_high_low_pairs([])
        self.assertFalse(plan.ok)
        self.assertEqual(plan.error_kind, "not_enough_objects")
        self.assertEqual(plan.leftovers, [])

    def test_none_input(self):
        plan = plan_high_low_pairs(None)
        self.assertFalse(plan.ok)
        self.assertEqual(plan.error_kind, "not_enough_objects")

    def test_matches_legacy_slicing_on_odd_five(self):
        # 5 objects sorted [a,b,c,d,e], pair_count=2:
        # lows=[a,b], highs=sorted([c,d,e])=[c,d,e], pair a-c, b-d, leftover e.
        plan = plan_high_low_pairs([("a", 1), ("b", 2), ("c", 3), ("d", 4), ("e", 5)])
        self.assertEqual(_lh(plan.pairs[0]), ("a", "c"))
        self.assertEqual(_lh(plan.pairs[1]), ("b", "d"))
        self.assertEqual(plan.leftovers, ["e"])

    def test_unsorted_input_is_ordered_by_complexity(self):
        plan = plan_high_low_pairs([("big", 500), ("small", 5),
                                    ("mid2", 60), ("mid1", 50)])
        self.assertTrue(plan.ok)
        # ordered: small(5), mid1(50), mid2(60), big(500)
        # lows=[small,mid1], highs=[mid2,big] -> small-mid2, mid1-big
        self.assertEqual(_lh(plan.pairs[0]), ("small", "mid2"))
        self.assertEqual(_lh(plan.pairs[1]), ("mid1", "big"))


class AmbiguityTests(unittest.TestCase):
    def test_equal_polys_in_a_pair_is_ambiguous_and_not_ok(self):
        # two identical-complexity objects: cannot tell high from low
        plan = plan_high_low_pairs([("x", 100), ("y", 100)])
        self.assertFalse(plan.ok)
        self.assertEqual(plan.error_kind, "ambiguous_pairs")
        self.assertEqual(len(plan.ambiguous_pairs), 1)
        self.assertEqual(plan.ambiguous_pairs[0]["polys"], 100)
        self.assertTrue(plan.pairs[0]["ambiguous"])

    def test_clear_pair_is_not_ambiguous(self):
        plan = plan_high_low_pairs([("lo", 10), ("hi", 999)])
        self.assertTrue(plan.ok)
        self.assertEqual(plan.ambiguous_pairs, [])
        self.assertFalse(plan.pairs[0]["ambiguous"])

    def test_mixed_one_clear_one_ambiguous_blocks_commit(self):
        # ordered: a(10), b(10), c(50), d(99)
        # lows=[a,b], highs=[c,d] -> a-c (clear), b-d (clear)... both clear here.
        # Force an ambiguous pair: equal counts must land in the SAME pair.
        # ordered: a(10), b(10), c(10), d(99) -> lows=[a,b] highs=[c,d]
        # pair0 a-c equal(10,10) ambiguous; pair1 b-d (10,99) clear.
        plan = plan_high_low_pairs([("a", 10), ("b", 10), ("c", 10), ("d", 99)])
        self.assertFalse(plan.ok)
        self.assertEqual(plan.error_kind, "ambiguous_pairs")
        self.assertEqual(len(plan.ambiguous_pairs), 1)
        self.assertEqual(len(plan.pairs), 2)

    def test_leftover_takes_priority_over_ambiguity(self):
        # odd count with an equal-poly pair: leftover error reported first
        plan = plan_high_low_pairs([("a", 5), ("b", 5), ("c", 7)])
        self.assertFalse(plan.ok)
        self.assertEqual(plan.error_kind, "unpaired_objects")
        self.assertEqual(plan.leftovers, ["c"])
        # ambiguous_pairs is still populated for the agent's reference
        self.assertEqual(len(plan.ambiguous_pairs), 1)


if __name__ == "__main__":
    unittest.main()
