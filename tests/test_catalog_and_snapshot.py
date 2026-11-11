import unittest
from datetime import date

from hwprice.catalog import load_catalog, problems, resolve, sample_id
from hwprice.client import ProductNotFound
from hwprice.snapshot import diff, take_snapshot


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()

    def test_the_shipped_catalog_is_valid(self):
        self.assertEqual(problems(self.catalog), [])

    def test_ecs_gets_the_linux_suffix_once(self):
        self.assertEqual(resolve(self.catalog, "ecs", "s6.large.4").spec, "s6.large.4.linux")
        self.assertEqual(resolve(self.catalog, "ecs", "s6.large.4.linux").spec, "s6.large.4.linux")

    def test_a_volume_needs_a_size(self):
        with self.assertRaises(ValueError):
            resolve(self.catalog, "evs", "SSD")
        self.assertEqual(resolve(self.catalog, "evs", "SSD", size_gb=100).size_gb, 100)

    def test_an_unknown_product_names_the_known_ones(self):
        with self.assertRaises(KeyError) as raised:
            resolve(self.catalog, "nope", "x")
        self.assertIn("ecs", str(raised.exception))

    def test_problems_finds_a_sample_with_no_product(self):
        broken = {"products": {}, "samples": [{"product": "ghost", "spec": "x"}]}
        self.assertEqual(len(problems(broken)), 1)

    def test_sample_ids_are_stable(self):
        self.assertEqual(sample_id({"product": "evs", "spec": "SSD", "size_gb": 100}), "evs:SSD:100gb")
        self.assertEqual(sample_id({"product": "ecs", "spec": "s6.large.4"}), "ecs:s6.large.4")


class SnapshotTest(unittest.TestCase):
    CATALOG = {
        "products": {"ecs": {"description": "d", "cloudServiceType": "s", "resourceType": "r",
                             "specSuffix": ".linux"}},
        "samples": [{"product": "ecs", "spec": "a"}, {"product": "ecs", "spec": "b"}],
    }

    def test_a_product_that_is_not_offered_becomes_null(self):
        def transport(payload):
            if payload["productInfos"][0]["resourceSpecCode"] == "b.linux":
                raise ProductNotFound("CBC.6006")
            return {"amount": 10.0, "currency": "USD"}

        snapshot = take_snapshot(self.CATALOG, ["r1"], transport, today=date(2026, 1, 2))
        self.assertEqual(snapshot["date"], "2026-01-02")
        self.assertEqual(snapshot["regions"]["r1"]["ecs:a"], {"monthly": 10.0, "ondemand": 10.0})
        self.assertEqual(snapshot["regions"]["r1"]["ecs:b"], {"monthly": None, "ondemand": None})

    def test_diff_lists_only_what_changed(self):
        old = {"regions": {"r1": {"ecs:a": {"monthly": 10.0, "ondemand": 12.0}}}}
        new = {"regions": {"r1": {"ecs:a": {"monthly": 11.0, "ondemand": 12.0}}}}
        self.assertEqual(diff(old, new), [
            {"region": "r1", "sample": "ecs:a", "billing": "monthly", "before": 10.0, "after": 11.0}])

    def test_diff_reports_a_new_region_as_a_change_from_nothing(self):
        new = {"regions": {"r2": {"ecs:a": {"monthly": 5.0}}}}
        self.assertEqual(diff({"regions": {}}, new)[0]["before"], None)

    def test_identical_snapshots_have_no_diff(self):
        snap = {"regions": {"r1": {"ecs:a": {"monthly": 10.0}}}}
        self.assertEqual(diff(snap, snap), [])


if __name__ == "__main__":
    unittest.main()
