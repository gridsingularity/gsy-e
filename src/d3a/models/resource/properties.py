from enum import Enum


class ApplianceType(Enum):
    UNCONTROLLED = 1
    TIME_SHIFTABLE = 2
    BUFFER_STORAGE = 3
    UNCONSTRAINED = 4


class MeasurementParamType(Enum):
    POWER = 1
    VOLTAGE = 2
    FREQUENCY = 3
    CURRENT = 4


class ApplianceProperties:
    def __init__(self, builder: ApplianceProfileBuilder = None):
        """
        Class to contain properties associated with an appliance.
        :param builder: builder containing profile related information.
        """
        if builder is None:
            builder = ApplianceProfileBuilder(None, None)

        self.name = builder.name
        self.location = builder.location
        self.applianceType = builder.applianceType
        self.manufacturer = builder.manufacturer
        self.modelInfoURL = builder.modelInfoURL
        self.iconURL = builder.iconURL
        self.contactURL = builder.contactURL
        self.uuid = builder.uuid

    def get_appliance_name(self):
        return self.name

    def get_location(self):
        return self.location

    def get_appliance_type(self):
        return self.applianceType

    def get_manufacturer(self):
        return self.manufacturer

    def get_model_info_url(self):
        return self.modelInfoURL

    def get_icon_url(self):
        return self.iconURL

    def get_contact_url(self):
        return self.contactURL

    def get_uuid(self):
        return self.uuid


class ApplianceProfileBuilder():
    def __init__(self, name: str, location: str, appliancetype: ApplianceType=ApplianceType.UNCONTROLLED):
        """
        Class acting as builder to ApplianceProfile class, handles setting optional params.

        :param name: Use assigned name of appliance
        :param location: location of appliance withing an area/home
        :param appliancetype: type of appliance, Uncontrolled, Time Shiftable, Buffer Storage, or Unconstrained

        """
        self.name = name
        self.location = location
        self.applianceType = appliancetype
        self.manufacturer = None
        self.modelInfoURL = None
        self.iconURL = None
        self.contactURL = None
        self.uuid = None

    def set_manufacturer(self, manufacturer: str):
        """
        :param manufacturer: Name of manufacturer
        :return: ApplianceProfileBuilder
        """
        self.manufacturer = manufacturer
        return self

    def set_model_url(self, url: str):
        """
        :param url: URL to get more info about this model
        :return: ApplianceProfileBuilder
        """
        self.modelInfoURL = url
        return self

    def set_icon_url(self, url: str):
        """
        :param url: URL to get appliance icon
        :return: ApplianceProfileBuilder
        """
        self.iconURL = url
        return self

    def set_contact_url(self, url: str):
        """
        :param url: URL to reach out to manufacturer
        :return: ApplianceProfileBuilder
        """
        self.contactURL = url
        return self

    def set_uuid(self, uuid: str):
        """
        :param uuid: Universal unique identifier
        :return: ApplianceProfileBuilder
        """
        self.uuid = uuid
        return self

    def build(self):
        """
        Builds the concrete object with all the params provided by user.
        :return: ApplianceProfile
        """
        profile = ApplianceProperties(self)
        return profile


class ElectricalProperties:
    def __init__(self, min_operational_voltage: float = 0.0,
                 max_operational_voltage: float = 0.0, freq: int = 50, country: str = "US"):
        """
        Class to set electrical properties of an appliance
        :param min_operational_voltage: Minimum operating voltage of the appliance
        :param max_operational_voltage: Maximum operating volate of the appliance
        :param freq: Grid frequency
        :param country: Country
        """
        self.minVoltage = min_operational_voltage
        self.maxVoltage = max_operational_voltage
        self.frequency = freq
        self.country = country

    def get_min_operational_voltage(self):
        return self.minVoltage

    def get_max_operational_voltage(self):
        return self.maxVoltage

    def get_operating_frequency(self):
        return self.frequency

    def get_country(self):
        return self.country

