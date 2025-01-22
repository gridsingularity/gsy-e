# Individual COP model integration

This document describes to train COP models, developed by [Tekniker](https://www.tekniker.es/en/) by deploying the [DOE-2](https://www.doe2.com/) building energy analysis program, to yield a statistical model by leveraging measurements of select heat pump manufacturers under predefined operational conditions.

## COP model training

The goal of training the COP model is to produce a JSON file that contains the COP model parameters for a specific heat pump.
For training the COP model, performance data for the selected heat pump is needed, that comply to the characteristics listed in the following section.

### Heat Pump performance data characteristics
#### Heat production data

A table of heat production (Q) in kW as a function of air temperature and condensor temperature needs to be provided for the full load operation of the heat pump.
The temperature range that is provided, is the range that the COP model will produce valid data.
Consequently, a large range and a high resolution of input data will result in more realistic output values.
In the following, an example table is shown.

| Q_heating [kW]                      |    | Condenser <br/>outlet <br/>temperature <br/>ºC |    |    |    |
|-------------------------------------|----|------------------------------------------------|----|----|----|
|                                     |    | 35                                             | 40 | 45 | 50 |
| Air <br/>supply <br/>temperature ºC | -5 |                                                |    |    |    |
|                                     | 0  |                                                |    |    |    |
|                                     | 5  |                                                |    |    |    |
|                                     | 15 |                                                |    |    |    |


#### Electric power consumption data

For the same data points as the heat production data, the corresponding electrical power consumption (P) in kW under full load needs to be provided:

| P_elec [kW]                         |    | Condenser <br/>outlet <br/>temperature <br/>ºC |    |    |    |
|-------------------------------------|----|------------------------------------------------|----|----|----|
|                                     |    | 35                                             | 40 | 45 | 50 |
| Air <br/>supply <br/>temperature ºC | -5 |                                                |    |    |    |
|                                     | 0  |                                                |    |    |    |
|                                     | 5  |                                                |    |    |    |
|                                     | 15 |                                                |    |    |    |

#### Partial load data

The partial load data represents the full range of load to be simulated by the model.
A combination of Q and P for different loads of the heat pump needs tp be provided in table form.
There must be a minimum of three distinct part-load data points for the same temperature conbination.


| % partial load | Condenser <br/>outlet <br/>temperature <br/>ºC | Air <br/>supply <br/>temperature ºC | Q_heating [kW] | P_elec [kW] |
|----------------|------------------------------------------------|-------------------------------------|----------------|-------------|
| 100            | 45                                             | 11                                  |                |             |
| 75             | 45                                             | 11                                  |                |             |
| 50             | 45                                             | 11                                  |                |             |
| 25             | 45                                             | 11                                  |                |             |

### How to train COP model for the heat pump strategy
1. Install the software requirements with `pip install -r requirements.txt`
2. Create an excel file in the `input_data` folder with 3 tabs each containing tables listed in the former section. Example files can be found in the `input_data` folder.
2. Run `python cop_model_fitter.py` that will read all input data in excel files and, fits the models and saves the model parameters into JSON files.


## How to integrate the COP model into the gsy-e

1. Move the newly generated JSON file to `src/gsy_e/models/strategy/energy_parameters/heatpump/cop_models/model_data`
2. Add an entry in the `COPModelType` enum** that is named after the heat pump model.
3. Add entry in the `MODEL_TYPE_FILENAME_MAPPING`**  mapping where the value should be the JSON file name that contains the model parameters.

** = can be found in the `src/gsy_e/models/strategy/energy_parameters/heatpump/cop_models/cop_models.py` module

Now, the pre-trained COP model can be selected in the HeatPump strategies by providing the newly added enum to the `cop_model_type` input parameter.
