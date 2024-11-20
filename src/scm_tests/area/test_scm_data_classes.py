from scm.scm_dataclasses import AreaFees, FeeContainer


class TestAreaFees:
    # pylint: disable=attribute-defined-outside-init

    def setup_method(self):
        self.area_fees = AreaFees(
            grid_import_fee_const=0.2,
            grid_export_fee_const=0.1,
            grid_fees_reduction=0.0,
            per_kWh_fees={
                "taxes_surcharges": FeeContainer(value=0.01),
                "other_fee": FeeContainer(value=0.001),
            },
            monthly_fees={
                "monthly_fee": FeeContainer(value=0.002),
                "other_monthly_fee": FeeContainer(value=0.0002),
            },
        )

    def test_price_as_dict_returns_correct_values(self):
        for fee in self.area_fees.per_kWh_fees.values():
            fee.price = 0.1
        for fee in self.area_fees.monthly_fees.values():
            fee.price = 0.1
        assert self.area_fees.prices_as_dict() == {
            "taxes_surcharges": 0.1,
            "other_fee": 0.1,
            "monthly_fee": 0.002,
            "other_monthly_fee": 0.0002,
        }
