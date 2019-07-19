from pywr.parameters import Parameter, load_parameter
import numpy as np
from skyfield import api as skyfield_api
skyfield_ts = skyfield_api.load.timescale()


class SolarGenerationParameter(Parameter):
    """Parameter for solar generation.

    This parameter calculates the power generated by an array of solar PV
    collectors. It uses `skyfield` to calculate the relative position of the sun
    to the collector's position and orientation. This relative position is used
    to factor in direct and diffuse radiation rates, which are provided as
    parameters to this class.

    Parameters
    ==========
    model: `pywr.model.Model`
    direct_radiation_parameter : `pywr.parameters.Parameter` or `None`
        Parameter that provides direct radiation per unit area.
    diffuse_radiation_parameter : `pywr.parameters.Parameter`
        Parameter that provides diffuse radiation per unit area.
    position : dict
        dict of keywords to pass to `skyfield.Topos` class. This defines the
        geographic location of the generator.
    collector_azimuth : float
        Orientation (azimuth) of the collector relative to north in radians.
    collector_tilt : float
        Vertical angle from the horizontal of the collector in radians.
    collector_area : float
        Area of the collector.

    """
    def __init__(self, model, **kwargs):
        self.direct_radiation_parameter = kwargs.pop('direct_radiation_parameter', None)
        self.diffuse_radiation_parameter = kwargs.pop('diffuse_radiation_parameter', None)
        self.position = kwargs.pop('position')
        self.collector_azimuth = kwargs.pop('collector_azimuth')
        self.collector_tilt = kwargs.pop('collector_tilt')
        self.collector_area = kwargs.pop('collector_area')
        super().__init__(model, **kwargs)

        self._skyfield_position = None
        self._skyfield_sun = None

    def setup(self):
        super().setup()
        # setup the skyfield objects
        planets = skyfield_api.load('de421.bsp')
        earth = planets['earth']
        self._skyfield_sun = planets['sun']
        self._skyfield_position = earth + skyfield_api.Topos(**self.position)

    def value(self, ts, si):

        skyfield_time = skyfield_ts.utc(ts.datetime.replace(tzinfo=skyfield_api.utc))
        astrometric = self._skyfield_position.at(skyfield_time).observe(self._skyfield_sun)
        alt, az, d = astrometric.apparent().altaz()

        if alt.radians < 0:
            return 0.0

        incidence_factor = np.cos(alt.radians)*np.cos(az.radians - self.collector_azimuth)*np.sin(self.collector_tilt)
        incidence_factor += np.sin(alt.radians)*np.cos(self.collector_tilt)
        incidence_factor = max(incidence_factor, 0.0)

        diffuse_factor = (1 + np.cos(self.collector_tilt)) / 2
        diffuse_factor = max(diffuse_factor, 0.0)

        if self.direct_radiation_parameter is not None:
            direct_radiation = self.direct_radiation_parameter.get_value(si)
        else:
            direct_radiation = 0.0
        direct_radiation = max(direct_radiation, 0.0)

        if self.diffuse_radiation_parameter is not None:
            diffuse_radiation = self.diffuse_radiation_parameter.get_value(si)
        else:
            diffuse_radiation = 0.0
        diffuse_radiation = max(diffuse_radiation, 0.0)

        collector_radiation = direct_radiation * incidence_factor + diffuse_factor * diffuse_radiation
        # print(ts, direct_radiation, incidence_factor, diffuse_radiation, collector_radiation)
        return collector_radiation * self.collector_area

    @classmethod
    def load(cls, model, data):

        direct_radiation_parameter = data.pop('direct_radiation_parameter', None)
        if direct_radiation_parameter is not None:
            direct_radiation_parameter = load_parameter(model, direct_radiation_parameter)

        diffuse_radiation_parameter = data.pop('diffuse_radiation_parameter', None)
        if diffuse_radiation_parameter is not None:
            diffuse_radiation_parameter = load_parameter(model, diffuse_radiation_parameter)

        return cls(model, direct_radiation_parameter=direct_radiation_parameter,
                   diffuse_radiation_parameter=diffuse_radiation_parameter, **data)

SolarGenerationParameter.register()


class HourlyDiurnalParameter(Parameter):
    def __init__(self, model, values, **kwargs):
        super().__init__(model, **kwargs)
        self.values = values

    def value(self, ts, si):
        hour = ts.hour
        return self.values[hour-1]

HourlyDiurnalParameter.register()
