"""Checks on the generated data. They read data/ and need no network."""

import unittest

from hwprice.snapshot import SAMPLES_PATH, load_samples
from hwprice.specs import (
    SPECS_DIR,
    find_spec,
    load_services,
    load_specs,
    load_verification,
    type_key,
)

BILLING = {"monthly", "yearly", "ondemand"}


class GeneratedDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.services = load_services()
        cls.verification = load_verification()["resource_types"]

    def test_every_service_with_a_path_has_a_specs_file(self):
        missing = [s["urlPath"] for s in self.services
                   if s["urlPath"] and not (SPECS_DIR / f"{s['urlPath']}.json").exists()]
        self.assertEqual(missing, [])

    def test_every_spec_names_its_codes_and_billing_modes(self):
        for service in self.services:
            if not service["urlPath"]:
                continue
            for spec in load_specs(service["urlPath"]):
                self.assertTrue(spec["spec"], f"{service['urlPath']}: a spec has no code")
                self.assertTrue(set(spec["billing"]) <= BILLING, f"{spec['spec']}: {spec['billing']}")

    def test_no_spec_code_is_listed_twice_in_a_resource_type(self):
        for service in self.services:
            if not service["urlPath"]:
                continue
            seen = set()
            for spec in load_specs(service["urlPath"]):
                key = (spec["resourceType"], spec["spec"])
                self.assertNotIn(key, seen, f"{service['urlPath']}: {key} is listed twice")
                seen.add(key)

    def test_every_verified_answer_names_a_spec_that_exists(self):
        for key, outcome in self.verification.items():
            path, resource_type = key.split("|", 1)
            specs = load_specs(path)
            for mode, info in outcome["modes"].items():
                if info["ok"]:
                    find_spec(specs, info["spec"], resource_type)

    def test_a_status_agrees_with_its_modes(self):
        for key, outcome in self.verification.items():
            oks = [m["ok"] for m in outcome["modes"].values()]
            expected = {"no-plans": not oks, "verified": all(oks) and bool(oks),
                        "partial": any(oks) and not all(oks), "unverified": not any(oks)}
            self.assertTrue(expected[outcome["status"]], f"{key}: {outcome['status']} vs {oks}")


class SamplesTest(unittest.TestCase):
    def test_every_sample_is_a_real_spec_that_was_verified_in_each_of_its_modes(self):
        if not SAMPLES_PATH.exists():
            self.skipTest("no samples yet")
        verification = load_verification()["resource_types"]
        for sample in load_samples():
            record = find_spec(load_specs(sample["service"]), sample["spec"], sample.get("resourceType"))
            outcome = verification[type_key(sample["service"], record["resourceType"])]
            for mode in sample["billing"]:
                self.assertIn(mode, record["billing"], f"{sample['id']}: no {mode} plan")
                self.assertTrue(outcome["modes"][mode]["ok"], f"{sample['id']}: {mode} was not verified")


if __name__ == "__main__":
    unittest.main()
