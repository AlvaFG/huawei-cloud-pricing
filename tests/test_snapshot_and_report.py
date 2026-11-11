import unittest
from datetime import date

from hwprice.client import Item, ProductNotFound
from hwprice.report import coverage, render_services_page
from hwprice.snapshot import diff, take_snapshot

SAMPLES = [
    {"id": "ecs:a", "service": "ecs", "spec": "a", "billing": ["monthly", "ondemand"]},
    {"id": "ecs:b", "service": "ecs", "spec": "b", "billing": ["monthly"]},
]


def resolve(sample, billing):
    return Item("s", "r", sample["spec"])


class SnapshotTest(unittest.TestCase):
    def test_a_product_that_is_not_offered_becomes_null(self):
        def transport(payload):
            if payload["productInfos"][0]["resourceSpecCode"] == "b":
                raise ProductNotFound("CBC.6006")
            return {"amount": 10.0, "currency": "USD"}

        snapshot = take_snapshot(SAMPLES, ["r1"], resolve, transport, today=date(2026, 1, 2))
        self.assertEqual(snapshot["date"], "2026-01-02")
        self.assertEqual(snapshot["regions"]["r1"]["ecs:a"], {"monthly": 10.0, "ondemand": 10.0})
        self.assertEqual(snapshot["regions"]["r1"]["ecs:b"], {"monthly": None})

    def test_only_the_billing_modes_of_a_sample_are_quoted(self):
        modes = []

        def transport(payload):
            modes.append(payload["chargingMode"])
            return {"amount": 1.0}

        take_snapshot(SAMPLES[1:], ["r1"], resolve, transport)
        self.assertEqual(modes, [0])

    def test_the_snapshot_describes_its_samples(self):
        snapshot = take_snapshot(SAMPLES[:1], ["r1"], resolve, lambda _: {"amount": 1.0})
        self.assertEqual(snapshot["samples"]["ecs:a"]["spec"], "a")
        self.assertNotIn("id", snapshot["samples"]["ecs:a"])

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


SERVICES = [
    {"category": "Networking", "service": "NAT Gateway", "urlPath": "nat", "hasCalculator": True,
     "resourceTypes": [{"cloudServiceType": "s", "resourceType": "r"}]},
    {"category": "Misc", "service": "Odd", "urlPath": "odd", "hasCalculator": False, "resourceTypes": []},
]
VERIFICATION = {
    "generated": "2026-01-02",
    "resource_types": {
        "nat|r": {"status": "partial", "specs": 4, "modes": {
            "monthly": {"ok": True, "spec": "x", "amount": 5.0, "listPrice": 6.0, "matchesList": False},
            "ondemand": {"ok": False, "reason": "CBC.6050: bad | unit"},
        }},
    },
}


class ReportTest(unittest.TestCase):
    def test_coverage_counts_what_was_verified(self):
        stats = coverage(SERVICES, VERIFICATION)
        self.assertEqual((stats["services"], stats["with_calculator"], stats["specs"]), (2, 1, 4))
        self.assertEqual(stats["statuses"], {"partial": 1})
        self.assertEqual(stats["list_price_mismatches"], 1)

    def test_the_page_shows_what_failed_and_does_not_hide_it(self):
        page = render_services_page(SERVICES, VERIFICATION)
        self.assertIn("| Networking | NAT Gateway | `nat` | 1 | 4 | 1/1 | - | 0/1 |", page)
        self.assertIn("| `nat` | `r` | ondemand | CBC.6050: bad / unit |", page)
        self.assertIn("## Differences from the catalog list price", page)
        self.assertIn("`odd` | 0 | 0 | - | - | -", page)


if __name__ == "__main__":
    unittest.main()
