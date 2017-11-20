from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.facebook_device import FacebookDeviceStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House1',  # House 1 in a village of 25 houses # Low Lighting, Mobile Charger, TV
                [

                    Area('Mobile Charger H1', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H1', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                    Area('TV H1', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                    Area('PV H1', strategy=PVStrategy(1, 40),
                         appliance=PVAppliance()),
                    Area('Storage H1', strategy=StorageStrategy(initial_capacity=1.2),
                         appliance=SimpleAppliance()),
                    ]
            ),
            Area(
                'House2',  # House 2 in a village of 25 houses # Low Lighting, Mobile Charger, TV
                [

                    Area('Mobile Charger H2', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H2', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                    Area('TV H2', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'House3',  # House 3 in a village of 25 houses # Low Lighting, Mobile Charger, TV
                [

                    Area('Mobile Charger H3', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H3', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                    Area('TV H3', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'House4',  # House 4 in a village of 25 houses # Low Lighting, Mobile Charger
                [

                    Area('Mobile Charger H4', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H4', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                    Area('PV H4', strategy=PVStrategy(1, 40),
                         appliance=PVAppliance()),
                    Area('Storage H4', strategy=StorageStrategy(initial_capacity=1.2),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'House5',  # House 5 in a village of 25 houses # Low Lighting, Mobile Charger
                [

                    Area('Mobile Charger H5', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H5', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'House6',  # House 6 in a village of 25 houses # Low Lighting, Mobile Charger
                [

                    Area('Mobile Charger H6', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H6', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                    Area('PV H6', strategy=PVStrategy(2, 40),
                         appliance=PVAppliance()),

                ]
            ),
            Area(
                'House7',  # House 7 in a village of 25 houses # Low Lighting, Mobile Charger
                [

                    Area('Mobile Charger H7', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H7', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                    Area('PV H7', strategy=PVStrategy(1, 40),
                         appliance=PVAppliance()),
                    Area('Storage H7', strategy=StorageStrategy(initial_capacity=1.2),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'House8',  # # House 8 in a village of 25 houses # Low Lighting, Mobile Charger
                [

                    Area('Mobile Charger H8', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H8', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                    Area('PV H8', strategy=PVStrategy(1, 40),
                         appliance=PVAppliance()),

                ]
            ),
            Area(
                'House9',  # # House 9 in a village of 25 houses # Low Lighting, Mobile Charger
                [

                    Area('Mobile Charger H9', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H9', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'House10',  # # House 10 in a village of 25 houses # Low Lighting, Mobile Charger
                [

                    Area('Mobile Charger H10', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H10', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'House11',  # # House 11 in a village of 25 houses # Low Lighting, Mobile Charger
                [

                    Area('Mobile Charger H11', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H11', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'House12',  # # House 12 in a village of 25 houses # Low Lighting, Mobile Charger
                [

                    Area('Mobile Charger H12', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H12', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'House13',  # # House 13 in a village of 25 houses # Low Lighting, Mobile Charger
                [

                    Area('Mobile Charger H13', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H13', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                    Area('PV H13', strategy=PVStrategy(1, 40),
                         appliance=PVAppliance()),
                    Area('Storage H13', strategy=StorageStrategy(initial_capacity=1.2),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'House14',  # # House 14 in a village of 25 houses # Low Lighting, Mobile Charger
                [

                    Area('Mobile Charger H14', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Low_Lighting H14', strategy=FacebookDeviceStrategy(26.25, 3.5),
                         appliance=SimpleAppliance()),
                ]
            ),
            # House 15 in a village of 25 houses # Medium Lighting, Mobile Charger, TV
            Area(
                'House15',
                [
                    Area('Mobile Charger H15', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Med_Lighting H15', strategy=FacebookDeviceStrategy(60, 4),
                         appliance=SimpleAppliance()),
                    Area('TV H15', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                    Area('Storage H15', strategy=StorageStrategy(initial_capacity=1.2),
                         appliance=SimpleAppliance()),
                ]
            ),
            # House 16 in a village of 25 houses # Medium Lighting, Mobile Charger, TV
            Area(
                'House16',
                [

                    Area('Mobile Charger H16', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Med_Lighting H16', strategy=FacebookDeviceStrategy(60, 4),
                         appliance=SimpleAppliance()),
                    Area('TV H16', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                ]
            ),
            # House 17 in a village of 25 houses # Medium Lighting, Mobile Charger, TV
            Area(
                'House17',
                [

                    Area('Mobile Charger H17', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Med_Lighting H17', strategy=FacebookDeviceStrategy(60, 4),
                         appliance=SimpleAppliance()),
                    Area('TV H17', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                ]
            ),
            # House 18 in a village of 25 houses # Medium Lighting, Mobile Charger, TV
            Area(
                'House18',
                [

                    Area('Mobile Charger H18', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Med_Lighting H18', strategy=FacebookDeviceStrategy(60, 4),
                         appliance=SimpleAppliance()),
                    Area('TV H18', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                ]
            ),
            # House 19 in a village of 25 houses # Medium Lighting, Mobile Charger, TV
            Area(
                'House19',
                [

                    Area('Mobile Charger H19', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Med_Lighting H19', strategy=FacebookDeviceStrategy(60, 4),
                         appliance=SimpleAppliance()),
                    Area('TV H19', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                ]
            ),
            # House 20 in a village of 25 houses # Medium Lighting, Mobile Charger
            Area(
                'House20',
                [

                    Area('Mobile Charger H20', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('Med_Lighting H20', strategy=FacebookDeviceStrategy(60, 4),
                         appliance=SimpleAppliance()),
                    Area('PV H1', strategy=PVStrategy(1, 40),
                         appliance=PVAppliance()),
                    Area('Storage H1', strategy=StorageStrategy(initial_capacity=1.2),
                         appliance=SimpleAppliance()),
                ]
            ),
            # House 21 in a village of 25 houses # High Lighting, Mobile Charger, TV
            Area(
                'House21',
                [

                    Area('Mobile Charger H21', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('High_Lighting H21', strategy=FacebookDeviceStrategy(155, 4),
                         appliance=SimpleAppliance()),
                    Area('TV H21', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                ]
            ),
            # House 22 in a village of 25 houses # High Lighting, Mobile Charger, TV
            Area(
                'House22',
                [

                    Area('Mobile Charger H22', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('High_Lighting H22', strategy=FacebookDeviceStrategy(155, 4),
                         appliance=SimpleAppliance()),
                    Area('TV H22', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                ]
            ),
            # House 23 in a village of 25 houses # High Lighting, Mobile Charger, TV
            Area(
                'House23',
                [

                    Area('Mobile Charger H23', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('High_Lighting H23', strategy=FacebookDeviceStrategy(155, 4),
                         appliance=SimpleAppliance()),
                    Area('TV H23', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                    Area('PV H1', strategy=PVStrategy(1, 40),
                         appliance=PVAppliance()),
                ]
            ),
            # House 24 in a village of 25 houses # High Lighting, Mobile Charger, TV
            Area(
                'House24',
                [

                    Area('Mobile Charger H24', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('High_Lighting H24', strategy=FacebookDeviceStrategy(155, 4),
                         appliance=SimpleAppliance()),
                    Area('TV H24', strategy=FacebookDeviceStrategy(50, 4),
                         appliance=SimpleAppliance()),
                ]
            ),
            # House 25 in a village of 25 houses # High Lighting, Mobile Charger
            Area(
                'House25',
                [

                    Area('Mobile Charger H25', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                    Area('High_Lighting H25', strategy=FacebookDeviceStrategy(155, 4),
                         appliance=SimpleAppliance()),
                    Area('PV H1', strategy=PVStrategy(1, 40),
                         appliance=PVAppliance()),
                ]
            ),

            # The Cell tower is currently programmed as a conventional load
            Area('Cell Tower', strategy=FacebookDeviceStrategy(100, 24),
                 appliance=SimpleAppliance()),
        ],
        config=config

    )
    return area
