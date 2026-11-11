import unittest

from hwprice.client import (
    GB_MEASURE_ID,
    Item,
    PricingError,
    ProductNotFound,
    build_payload,
    quote,
)

ECS = Item("hws.service.type.ec2", "hws.resource.type.vm", "c6.large.2.linux")
DISK = Item("hws.service.type.ebs", "hws.resource.type.volume", "GPSSD", size=40)


class BuildPayloadTest(unittest.TestCase):
    def test_monthly_matches_the_documented_request(self):
        payload = build_payload([ECS, DISK], "cn-north-4")
        self.assertEqual(payload["chargingMode"], 0)
        self.assertEqual(payload["periodType"], 2)
        self.assertEqual(payload["regionId"], "cn-north-4")
        self.assertEqual(payload["siteCode"], "HWC")
        self.assertEqual([p["id"] for p in payload["productInfos"]], ["1", "2"])
        self.assertEqual(payload["productInfos"][0]["resourceSpecCode"], "c6.large.2.linux")

    def test_yearly_is_a_subscription_of_one_year(self):
        payload = build_payload([ECS], "la-south-2", "yearly")
        self.assertEqual((payload["chargingMode"], payload["periodType"], payload["periodNum"]), (0, 3, 1))

    def test_a_sized_item_carries_the_size_and_the_misspelled_measure_key(self):
        disk = build_payload([DISK], "la-south-2")["productInfos"][0]
        self.assertEqual(disk["resourceSize"], 40)
        self.assertEqual(disk["resouceSizeMeasureId"], GB_MEASURE_ID)
        self.assertNotIn("resourceSizeMeasureId", disk)

    def test_a_size_can_use_another_unit(self):
        item = Item("s", "r", "x", size=2, size_measure_id=99)
        self.assertEqual(build_payload([item], "r1")["productInfos"][0]["resouceSizeMeasureId"], 99)

    def test_on_demand_defaults_to_hours_of_duration(self):
        payload = build_payload([ECS], "la-south-2", "ondemand", hours=100)
        line = payload["productInfos"][0]
        self.assertEqual(payload["chargingMode"], 1)
        self.assertEqual(payload["periodType"], 4)
        self.assertEqual((line["usageFactor"], line["usageMeasureId"], line["usageValue"]),
                         ("Duration", 4, 100))

    def test_on_demand_uses_the_usage_the_item_declares(self):
        item = Item("s", "r", "12_bgp", usage_factor="upflow", usage_measure_id=10, usage_value=250)
        line = build_payload([item], "la-south-2", "ondemand")["productInfos"][0]
        self.assertEqual((line["usageFactor"], line["usageMeasureId"], line["usageValue"]),
                         ("upflow", 10, 250))

    def test_monthly_lines_have_no_usage_fields(self):
        self.assertNotIn("usageFactor", build_payload([ECS], "la-south-2")["productInfos"][0])

    def test_rejects_an_unknown_billing_mode(self):
        with self.assertRaises(ValueError):
            build_payload([ECS], "la-south-2", "weekly")

    def test_rejects_an_empty_request(self):
        with self.assertRaises(ValueError):
            build_payload([], "la-south-2")


class QuoteTest(unittest.TestCase):
    def test_returns_the_total_and_each_line(self):
        def transport(_):
            return {"amount": 34.11, "currency": "USD",
                    "productRatingResult": [{"amount": 29.79}, {"amount": 4.32}]}

        result = quote([ECS, DISK], "cn-north-4", transport=transport)
        self.assertEqual((result.total, result.currency), (34.11, "USD"))
        self.assertEqual(list(result.lines), [29.79, 4.32])

    def test_a_response_without_amount_is_an_error(self):
        with self.assertRaises(PricingError):
            quote([ECS], "la-south-2", transport=lambda _: {"amount": None})

    def test_an_unknown_product_propagates(self):
        def transport(_):
            raise ProductNotFound("CBC.6006:Can not find product x")

        with self.assertRaises(ProductNotFound):
            quote([ECS], "la-south-2", transport=transport)


if __name__ == "__main__":
    unittest.main()
