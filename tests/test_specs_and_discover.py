import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from hwprice.client import PricingError, ProductNotFound
from hwprice.discover import (
    REFERENCE_REGION,
    count_without_codes,
    discover,
    extract_specs,
    parse_menu,
    verify_mode,
    verify_type,
)
from hwprice.specs import AmbiguousSpec, find_spec, item_for, resource_type_codes, type_key

TODAY = date(2026, 1, 2)

PRODUCT_INFO = {"product": {"nat_natgateway": [
    {"resourceType": "hws.resource.type.natgateway", "cloudServiceType": "hws.service.type.natgateway",
     "resourceSpecCode": "natgateway_small", "productSpecSysDesc": "type:small",
     "planList": [
         {"billingMode": "MONTHLY", "periodNum": 1, "amount": 57.3},
         {"billingMode": "YEARLY", "periodNum": 1, "amount": 573.0},
         {"billingMode": "YEARLY", "periodNum": 2, "amount": 1146.0},
         {"billingMode": "ONDEMAND", "usageFactor": "duration", "usageMeasureId": 0, "measureUnit": 4, "amount": 8.1},
         {"billingMode": "RI"},
     ]},
]}}

MENU = {"menuInfos": [{"parentCategoryName": "Networking", "subCategoryLists": [
    {"categoryName": "NAT Gateway", "urlPath": "nat", "hasCalculator": True,
     "categoryInfos": [{"cloudServiceType": "hws.service.type.natgateway",
                        "resourceType": "hws.resource.type.natgateway"}]},
    {"categoryName": "No Calculator Thing", "urlPath": "nope", "hasCalculator": False, "categoryInfos": []},
]}]}


def spec(code="s1", billing=("monthly", "yearly", "ondemand"), usage=None, listing=None, rtype="rt"):
    record = {"cloudServiceType": "svc", "resourceType": rtype, "spec": code,
              "description": "", "billing": list(billing)}
    record["usage"] = usage if usage is not None else [{"factor": "duration", "unit": 4, "measure": 6}]
    if listing:
        record["list"] = listing
    return record


class ParsingTest(unittest.TestCase):
    def test_extract_specs_reads_billing_modes_usage_and_list_prices(self):
        record = extract_specs(PRODUCT_INFO)[0]
        self.assertEqual(record["spec"], "natgateway_small")
        self.assertEqual(record["billing"], ["monthly", "yearly", "ondemand"])
        self.assertEqual(record["usage"], [{"factor": "duration", "unit": 4, "measure": 0}])
        self.assertEqual(record["list"], {"monthly": 57.3, "yearly": 573.0})

    def test_a_spec_listed_once_per_usage_factor_becomes_one_record(self):
        info = {"product": {"smn_smn": [
            {"resourceType": "rt", "cloudServiceType": "svc", "resourceSpecCode": "smn",
             "planList": [{"billingMode": "ONDEMAND", "usageFactor": "email", "usageMeasureId": 30, "measureUnit": None}]},
            {"resourceType": "rt", "cloudServiceType": "svc", "resourceSpecCode": "smn",
             "productSpecSysDesc": "messages",
             "planList": [{"billingMode": "ONDEMAND", "usageFactor": "sms", "usageMeasureId": 30, "measureUnit": None},
                          {"billingMode": "MONTHLY", "periodNum": 1, "amount": 2.0}]},
            {"resourceType": "rt", "cloudServiceType": "svc", "resourceSpecCode": "other", "planList": []},
        ]}}
        records = extract_specs(info)
        self.assertEqual([r["spec"] for r in records], ["smn", "other"])
        smn = records[0]
        self.assertEqual([u["factor"] for u in smn["usage"]], ["email", "sms"])
        self.assertEqual((smn["billing"], smn["description"], smn["list"]), (["ondemand", "monthly"], "messages", {"monthly": 2.0}))

    def test_the_same_code_in_two_resource_types_stays_two_records(self):
        entry = lambda rt: {"resourceType": rt, "cloudServiceType": "svc", "resourceSpecCode": "x", "planList": []}
        self.assertEqual(len(extract_specs({"product": {"a": [entry("r1"), entry("r2")]}})), 2)

    def test_reserved_instance_plans_are_not_a_billing_mode(self):
        self.assertNotIn("ri", extract_specs(PRODUCT_INFO)[0]["billing"])

    def test_parse_menu_keeps_services_without_calculator(self):
        services = parse_menu(MENU)
        self.assertEqual([s["urlPath"] for s in services], ["nat", "nope"])
        self.assertFalse(services[1]["hasCalculator"])
        self.assertEqual(services[0]["resourceTypes"][0]["resourceType"], "hws.resource.type.natgateway")


class FindSpecTest(unittest.TestCase):
    SPECS = [spec("s6.large.4.linux"), spec("s6.large.4.windows"), spec("natgateway_small", rtype="other")]

    def test_an_exact_code_wins(self):
        self.assertEqual(find_spec(self.SPECS, "s6.large.4.linux")["spec"], "s6.large.4.linux")

    def test_a_shorter_code_that_matches_two_is_ambiguous(self):
        with self.assertRaises(AmbiguousSpec) as raised:
            find_spec(self.SPECS, "s6.large.4")
        self.assertEqual(raised.exception.candidates, ["s6.large.4.linux", "s6.large.4.windows"])

    def test_a_shorter_code_that_matches_one_is_accepted(self):
        self.assertEqual(find_spec([spec("a.b.linux")], "a.b")["spec"], "a.b.linux")

    def test_an_unknown_code_is_a_key_error(self):
        with self.assertRaises(KeyError):
            find_spec(self.SPECS, "nope")

    def test_the_resource_type_narrows_the_search(self):
        self.assertEqual(find_spec(self.SPECS, "natgateway_small", "other")["resourceType"], "other")


class ResourceTypeCodesTest(unittest.TestCase):
    SERVICE = {"urlPath": "rds", "resourceTypes": [
        {"cloudServiceType": "hws.service.type.rds", "resourceType": "hws.resource.type.rds.vm"}]}

    def test_the_short_name_is_enough(self):
        self.assertEqual(resource_type_codes(self.SERVICE, "rds.vm")["cloudServiceType"], "hws.service.type.rds")

    def test_the_full_name_works_too(self):
        self.assertEqual(resource_type_codes(self.SERVICE, "hws.resource.type.rds.vm")["resourceType"],
                         "hws.resource.type.rds.vm")

    def test_an_unknown_type_names_the_ones_the_service_has(self):
        with self.assertRaises(KeyError) as raised:
            resource_type_codes(self.SERVICE, "nope")
        self.assertIn("rds.vm", str(raised.exception))


class ItemForTest(unittest.TestCase):
    def test_a_sized_product_needs_a_size(self):
        with self.assertRaises(ValueError):
            item_for(spec(), "monthly", mode_info={"sized": True})

    def test_a_size_uses_the_unit_verification_found(self):
        item = item_for(spec(), "monthly", size=40, mode_info={"sized": True, "sizeMeasureId": 17})
        self.assertEqual((item.size, item.size_measure_id), (40, 17))

    def test_on_demand_reads_the_usage_from_the_spec(self):
        item = item_for(spec(usage=[{"factor": "traffic", "unit": 10, "measure": 13}]), "ondemand")
        self.assertEqual((item.usage_factor, item.usage_measure_id, item.usage_value), ("traffic", 10, 1))

    def test_on_demand_hours_default_to_a_month(self):
        self.assertEqual(item_for(spec(), "ondemand").usage_value, 730)

    def test_on_demand_prefers_the_unit_verification_learned(self):
        info = {"usageFactor": "duration", "usageMeasureId": 4}
        item = item_for(spec(usage=[{"factor": "duration", "unit": 9, "measure": 9}]), "ondemand", mode_info=info)
        self.assertEqual((item.usage_factor, item.usage_measure_id), ("duration", 4))

    def test_a_spec_billed_by_several_factors_can_be_priced_by_each(self):
        two = spec(usage=[{"factor": "email", "unit": None, "measure": 30},
                          {"factor": "sms", "unit": None, "measure": 31}])
        info = {"usageFactor": "email", "usageMeasureId": 30,
                "factors": {"sms": {"ok": True, "usageFactor": "sms", "usageMeasureId": 77}}}
        self.assertEqual(item_for(two, "ondemand", mode_info=info).usage_factor, "email")
        by_sms = item_for(two, "ondemand", mode_info=info, usage_factor="sms")
        self.assertEqual((by_sms.usage_factor, by_sms.usage_measure_id), ("sms", 77))

    def test_a_factor_the_spec_is_not_billed_by_is_refused_and_the_real_ones_are_named(self):
        with self.assertRaises(ValueError) as raised:
            item_for(spec(), "ondemand", usage_factor="nope")
        self.assertIn("duration", str(raised.exception))

    def test_a_spec_without_a_pay_per_use_plan_cannot_be_priced_that_way(self):
        with self.assertRaises(ValueError):
            item_for(spec(usage=[]), "ondemand")


class VerifyTest(unittest.TestCase):
    def test_the_first_answer_is_recorded_with_its_region(self):
        outcome = verify_mode([spec()], "monthly", lambda _: {"amount": 10.0}, today=TODAY)
        self.assertEqual((outcome["ok"], outcome["region"], outcome["amount"]), (True, REFERENCE_REGION, 10.0))
        self.assertEqual(outcome["verified_on"], "2026-01-02")

    def test_a_product_that_needs_a_size_is_retried_with_one(self):
        def transport(payload):
            if "resourceSize" not in payload["productInfos"][0]:
                raise PricingError("CBC.6050: resourceSpecSize is null or empty")
            return {"amount": 6.84}

        outcome = verify_mode([spec()], "monthly", transport, today=TODAY)
        self.assertTrue(outcome["ok"])
        self.assertEqual((outcome["sized"], outcome["sizeMeasureId"]), (True, 17))

    def test_the_unit_the_endpoint_asks_for_is_tried(self):
        def transport(payload):
            line = payload["productInfos"][0]
            if "resourceSize" not in line:
                raise PricingError("HTTP 500: CBC.6050: resourceSpecSize is null or empty")
            if line["resouceSizeMeasureId"] != 15:
                raise PricingError(
                    "HTTP 500: CBC.6050:Convert from resource spec size measure(17) "
                    "to resource spec size measure(15) error")
            return {"amount": 9.0}

        outcome = verify_mode([spec()], "monthly", transport, today=TODAY)
        self.assertTrue(outcome["ok"])
        self.assertEqual(outcome["sizeMeasureId"], 15)

    def test_a_hint_that_leads_nowhere_ends_without_looping(self):
        calls = []

        def transport(payload):
            calls.append(1)
            raise PricingError("HTTP 500: CBC.6050:Convert from measure(17) to measure(17) error")

        outcome = verify_mode([spec()], "monthly", transport, today=TODAY)
        self.assertFalse(outcome["ok"])
        self.assertLess(len(calls), 40)

    def test_a_region_that_does_not_sell_it_moves_on_to_the_next(self):
        def transport(payload):
            if payload["regionId"] == REFERENCE_REGION:
                raise ProductNotFound("CBC.6006")
            return {"amount": 5.0}

        outcome = verify_mode([spec()], "monthly", transport, today=TODAY)
        self.assertEqual(outcome["region"], "la-south-2")

    def test_a_wrong_usage_unit_is_replaced_by_one_that_works(self):
        def transport(payload):
            if payload["productInfos"][0]["usageMeasureId"] != 10:
                raise PricingError("CBC.6050: bad measure")
            return {"amount": 8.1}

        usage = [{"factor": "traffic", "unit": 99, "measure": 10}]
        outcome = verify_mode([spec(usage=usage)], "ondemand", transport, today=TODAY)
        self.assertTrue(outcome["ok"])
        self.assertEqual((outcome["usageFactor"], outcome["usageMeasureId"]), ("traffic", 10))

    def test_a_price_equal_to_the_catalog_list_price_is_confirmed(self):
        item = spec(listing={"monthly": 54.5})
        outcome = verify_mode([item], "monthly", lambda _: {"amount": 54.5}, today=TODAY)
        self.assertEqual((outcome["listPrice"], outcome["matchesList"]), (54.5, True))

    def test_a_price_different_from_the_list_price_is_not_called_verified(self):
        item = spec(listing={"monthly": 54.5})
        outcome = verify_mode([item], "monthly", lambda _: {"amount": 40.0}, today=TODAY)
        self.assertFalse(outcome["ok"])
        self.assertIn("catalog lists 54.5", outcome["reason"])

    def test_a_sized_product_is_confirmed_by_the_price_of_one_unit(self):
        def transport(payload):
            if "resourceSize" not in payload["productInfos"][0]:
                raise PricingError("CBC.6001: Required param resourceSpecSize is null or empty")
            return {"amount": round(0.0684 * payload["productInfos"][0]["resourceSize"], 2)}

        outcome = verify_mode([spec(listing={"monthly": 0.0684})], "monthly", transport, today=TODAY)
        self.assertEqual((outcome["ok"], outcome["sized"], outcome["matchesList"]), (True, True, True))

    def test_a_sized_product_in_the_wrong_unit_is_not_called_verified(self):
        def transport(payload):
            if "resourceSize" not in payload["productInfos"][0]:
                raise PricingError("CBC.6001: Required param resourceSpecSize is null or empty")
            return {"amount": 999.0}

        outcome = verify_mode([spec(listing={"monthly": 0.0684})], "monthly", transport, today=TODAY)
        self.assertFalse(outcome["ok"])
        self.assertIn("per unit", outcome["reason"])

    def test_a_second_spec_that_matches_the_list_price_is_accepted(self):
        bad, good = spec("bad", listing={"monthly": 10.0}), spec("good", listing={"monthly": 20.0})

        def transport(payload):
            return {"amount": 20.0}

        outcome = verify_mode([bad, good], "monthly", transport, today=TODAY)
        self.assertEqual((outcome["ok"], outcome["spec"], outcome["matchesList"]), (True, "good", True))

    def test_everything_failing_is_reported_with_the_reason(self):
        def transport(_):
            raise ProductNotFound("CBC.6006:Can not find product s1")

        outcome = verify_mode([spec()], "monthly", transport, today=TODAY)
        self.assertEqual(outcome["ok"], False)
        self.assertIn("CBC.6006", outcome["reason"])

    def test_every_usage_factor_is_verified_on_its_own(self):
        usage = [{"factor": "email", "unit": 4, "measure": 4}, {"factor": "sms", "unit": 4, "measure": 4}]

        def transport(payload):
            if payload["productInfos"][0]["usageFactor"] == "sms":
                raise PricingError("CBC.6050: sms is not priced")
            return {"amount": 1.0}

        outcome = verify_mode([spec(usage=usage)], "ondemand", transport, today=TODAY)
        self.assertTrue(outcome["ok"])
        self.assertEqual(outcome["usageFactor"], "email")
        self.assertEqual({f: i["ok"] for f, i in outcome["factors"].items()}, {"email": True, "sms": False})

    def test_a_mode_with_no_plan_is_not_tried(self):
        called = []
        outcome = verify_mode([spec(billing=("monthly",))], "yearly", lambda p: called.append(p) or {"amount": 1},
                              today=TODAY)
        self.assertEqual(outcome, {"ok": False, "reason": "no plan"})
        self.assertEqual(called, [])

    def test_verify_type_is_partial_when_only_some_modes_work(self):
        def transport(payload):
            if payload["chargingMode"] == 1:
                raise PricingError("CBC.6050: nope")
            return {"amount": 3.0}

        outcome = verify_type([spec()], transport, today=TODAY)
        self.assertEqual(outcome["status"], "partial")
        self.assertEqual(sorted(outcome["modes"]), ["monthly", "ondemand", "yearly"])

    def test_verify_type_is_unverified_when_nothing_works(self):
        def transport(_):
            raise ProductNotFound("CBC.6006")

        self.assertEqual(verify_type([spec()], transport, today=TODAY)["status"], "unverified")


class DiscoverTest(unittest.TestCase):
    def test_entries_without_codes_are_not_specs_and_are_counted(self):
        info = {"product": {"x": [
            {"resourceType": None, "cloudServiceType": None, "resourceSpecCode": None, "name": "an OS image"},
            {"resourceType": "rt", "cloudServiceType": "svc", "resourceSpecCode": "fine",
             "planList": [{"billingMode": "MONTHLY", "periodNum": 1, "amount": 1.0}]},
        ]}}
        self.assertEqual([s["spec"] for s in extract_specs(info)], ["fine"])
        self.assertEqual(count_without_codes(info), 1)

        def get_json(url, params):
            return MENU if url.endswith("menuInfo") else info

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = discover(get_json, lambda _: {"amount": 1.0}, only=["nat"], today=TODAY,
                              log=lambda _: None, specs_dir=root / "s", services_path=root / "v.json",
                              verification_path=root / "ver.json")
            saved = json.loads((root / "s" / "nat.json").read_text())
        self.assertEqual(saved["skipped_without_codes"], 1)
        self.assertEqual(list(result["resource_types"]), [type_key("nat", "rt")])

    def test_a_service_that_is_discovered_again_drops_its_old_resource_types(self):
        def get_json(url, params):
            return MENU if url.endswith("menuInfo") else PRODUCT_INFO

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ver.json").write_text(json.dumps({"resource_types": {
                "nat|gone": {"status": "verified", "specs": 1, "modes": {}},
                "other|kept": {"status": "verified", "specs": 1, "modes": {}}}}))
            result = discover(get_json, lambda p: {"amount": 573.0 if p["periodType"] == 3 else 57.3},
                              only=["nat"], today=TODAY, log=lambda _: None, specs_dir=root / "s",
                              services_path=root / "v.json", verification_path=root / "ver.json")
        self.assertNotIn("nat|gone", result["resource_types"])
        self.assertIn("other|kept", result["resource_types"])

    def test_progress_is_saved_after_every_service_and_resume_skips_done_ones(self):
        calls = []

        def get_json(url, params):
            if url.endswith("productInfo"):
                calls.append(params["urlPath"])
                return PRODUCT_INFO
            return MENU

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kwargs = dict(today=TODAY, log=lambda _: None, specs_dir=root / "s",
                          services_path=root / "v.json", verification_path=root / "ver.json")
            discover(get_json, lambda _: {"amount": 1.0}, only=["nat"], **kwargs)
            self.assertTrue((root / "ver.json").exists())
            discover(get_json, lambda _: {"amount": 1.0}, only=["nat"], resume=True, **kwargs)
        self.assertEqual(calls, ["nat"])

    def test_discover_writes_services_specs_and_verification(self):
        def get_json(url, params):
            return MENU if url.endswith("menuInfo") else PRODUCT_INFO

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = discover(
                get_json, lambda p: {"amount": 573.0 if p["periodType"] == 3 else 57.3},
                only=["nat"], today=TODAY, log=lambda _: None,
                specs_dir=root / "specs", services_path=root / "services.json",
                verification_path=root / "verification.json",
            )
            key = type_key("nat", "hws.resource.type.natgateway")
            self.assertEqual(result["resource_types"][key]["status"], "verified")
            saved = json.loads((root / "specs" / "nat.json").read_text())
            self.assertEqual(saved["specs"][0]["spec"], "natgateway_small")
            self.assertEqual(len(json.loads((root / "services.json").read_text())["services"]), 2)
            self.assertFalse((root / "specs" / "nope.json").exists())


if __name__ == "__main__":
    unittest.main()
