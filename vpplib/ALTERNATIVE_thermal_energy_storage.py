# -*- coding: utf-8 -*-
"""
Created on Thu Jun 18 16:40:16 2020

@author: andre
"""


import pandas as pd
from .component import Component


class ThermalEnergyStorage(Component):
    def __init__(
        self,
        target_temperature,
        hysteresis,
        mass,
        cp,
        thermal_energy_loss_per_day,
        unit,
        identifier=None,
        environment=None,
        user_profile=None,
        cost=None,
    ):

        """
        Info
        ----
        ...
        
        Parameters
        ----------
        
        The parameter timebase determines the resolution of the given data. 
        Furthermore the parameter environment (Environment) is given to provide weather data and further external influences.
        To account for different people using a component, a use case (VPPUseCase) can be passed in to improve the simulation.
        	
        Attributes
        ----------
        
        ...
        
        Notes
        -----
        
        ...
        
        References
        ----------
        
        ...
        
        Returns
        -------
        
        ...
        
        """

        # Call to super class
        super(ThermalEnergyStorage, self).__init__(
            unit, environment, user_profile, cost
        )

        # Configure attributes
        self.identifier = identifier
        self.target_temperature = target_temperature
        self.current_temperature = target_temperature - hysteresis
        self.timeseries = pd.DataFrame(
            columns=["temperature"],
            index=pd.date_range(
                start=self.environment.start,
                end=self.environment.end,
                freq=self.environment.time_freq,
                name="time",
            ),
        )
        self.hysteresis = hysteresis
        self.mass = mass
        self.cp = cp
        self.state_of_charge = mass * cp * (2 * self.hysteresis)
        # Aus Datenblättern ergibt sich, dass ein Wärmespeicher je Tag rund 10%
        # Bereitschaftsverluste hat (ohne Rohrleitungen!!)
        self.thermal_energy_loss_per_day = thermal_energy_loss_per_day
        self.efficiency_per_timestep = 1 - (
            thermal_energy_loss_per_day
            / (24 * (60 / self.environment.timebase))
        )
        self.needs_loading = None

    def operate_storage(self, timestamp, thermal_energy_generator):

        if self.get_needs_loading():
            thermal_energy_generator.ramp_up(timestamp)
        else:
            thermal_energy_generator.ramp_down(timestamp)

        thermal_energy_demand = self.user_profile.thermal_energy_demand.thermal_energy_demand.loc[
            timestamp
        ]
        observation = thermal_energy_generator.observations_for_timestamp(
            timestamp
        )
        thermal_production = observation["thermal_energy_output"]

        # Formula: E = m * cp * T
        #     <=> T = E / (m * cp)
        self.state_of_charge -= (
            (thermal_energy_demand - thermal_production)
            * 1000
            / (60 / self.environment.timebase)
        )
        self.state_of_charge *= self.efficiency_per_timestep
        self.current_temperature = (
            self.state_of_charge / (self.mass * self.cp)
        ) - 273.15

        if thermal_energy_generator.is_running:
            el_load = observation["el_demand"]
        else:
            el_load = 0

        self.timeseries.temperature[timestamp] = self.current_temperature

        # log timeseries of thermal_energy_generator_class:
        thermal_energy_generator.log_observation(observation, timestamp)

        return self.current_temperature, el_load
    
    def operate_storage_bivalent(self, timestamp, hp, hr, norm_temp):
        # determine bivalence temperature according to norm_temperature
        if norm_temp <= -16:
            biv_temp = -4
        elif (norm_temp > -16) & (norm_temp <= -10):
            biv_temp = -3
        elif norm_temp > -10:
            biv_temp = -2
        # dataframe with temperatures to decide whether hp or hr has to be run    
        temperatures = pd.read_csv("./input/thermal/dwd_temp_15min_2015.csv",
                                   index_col = "time")
        temperatures.index = self.user_profile.thermal_energy_demand.index

        # for temperatures above bivalence the hp is running
        if temperatures.temperature.loc[timestamp] > biv_temp:
            if self.get_needs_loading():
                hp.ramp_up(timestamp)
            else:
                hp.ramp_down(timestamp)

            thermal_energy_demand = self.user_profile.thermal_energy_demand.thermal_energy_demand.loc[
                timestamp
            ]
            observation = hp.observations_for_timestamp(
                timestamp
            )
            thermal_production = observation["thermal_energy_output"]
    
            # Formula: E = m * cp * T
            #     <=> T = E / (m * cp)
            self.state_of_charge -= (
                (thermal_energy_demand - thermal_production)
                * 1000
                / (60 / self.environment.timebase)
            )
            self.state_of_charge *= self.efficiency_per_timestep
            self.current_temperature = (
                self.state_of_charge / (self.mass * self.cp)
            ) - 273.15
            
            #print("tes temp: " + str(self.current_temperature))
    
            if hp.is_running:
                el_load = observation["el_demand"]
            else:
                el_load = 0
    
            self.timeseries.temperature[timestamp] = self.current_temperature
    
            # log timeseries of thermal_energy_generator_class:
            hp.log_observation(observation, timestamp)
            
            return self.current_temperature, el_load
        
        # for temperatures below bivalence the hr is running
        if temperatures.temperature.loc[timestamp] <= biv_temp:
            if self.get_needs_loading():
                hr.ramp_up(timestamp)
            else:
                hr.ramp_down(timestamp)

            thermal_energy_demand = self.user_profile.thermal_energy_demand.thermal_energy_demand.loc[
                timestamp
            ]
            observation = hr.observations_for_timestamp(
                timestamp
            )
            thermal_production = observation["thermal_energy_output"]
    
            # Formula: E = m * cp * T
            #     <=> T = E / (m * cp)
            self.state_of_charge -= (
                (thermal_energy_demand - thermal_production)
                * 1000
                / (60 / self.environment.timebase)
            )
            self.state_of_charge *= self.efficiency_per_timestep
            self.current_temperature = (
                self.state_of_charge / (self.mass * self.cp)
            ) - 273.15
            
            #print("tes temp: " + str(self.current_temperature))
    
            if hr.is_running:
                el_load = observation["el_demand"]
            else:
                el_load = 0
    
            self.timeseries.temperature[timestamp] = self.current_temperature
    
            # log timeseries of thermal_energy_generator_class:
            hr.log_observation(observation, timestamp)
            
            return self.current_temperature, el_load


    def get_needs_loading(self):

        if self.current_temperature <= (
            self.target_temperature - self.hysteresis
        ):
            self.needs_loading = True

        if self.current_temperature >= (
            self.target_temperature + self.hysteresis
        ):
            self.needs_loading = False

        if self.current_temperature < 40:
            raise ValueError(
                "Thermal energy production to low to maintain "
                + "heat storage temperature!"
            )

        return self.needs_loading

    def value_for_timestamp(self, timestamp):

        """
        Info
        ----
        This function takes a timestamp as the parameter and returns the 
        corresponding value for that timestamp. 
        A positiv result represents a load. 
        A negative result represents a generation. 
        
        This abstract function needs to be implemented by child classes.
        Raises an error since this function needs to be implemented by child classes.
        
        Parameters
        ----------
        
        ...
        	
        Attributes
        ----------
        
        ...
        
        Notes
        -----
        
        ...
        
        References
        ----------
        
        ...
        
        Returns
        -------
        
        ...
        
        """

        raise NotImplementedError(
            "value_for_timestamp needs to be implemented by child classes!"
        )

    def observations_for_timestamp(self, timestamp):

        """
        Info
        ----
        This function takes a timestamp as the parameter and returns a 
        dictionary with key (String) value (Any) pairs. 
        Depending on the type of component, different status parameters of the 
        respective component can be queried. 
        
        For example, a power store can report its "State of Charge".
        Returns an empty dictionary since this function needs to be 
        implemented by child classes.
        
        Parameters
        ----------
        
        ...
        	
        Attributes
        ----------
        
        ...
        
        Notes
        -----
        
        ...
        
        References
        ----------
        
        ...
        
        Returns
        -------
        
        ...
        
        """

        return {}

    def prepare_time_series(self):

        """
        Info
        ----
        This function is called to prepare the time series.
        Currently equals reset_time_series. Adjust if needed in later versions.
        
        Parameters
        ----------
        
        ...
        	
        Attributes
        ----------
        
        ...
        
        Notes
        -----
        
        ...
        
        References
        ----------
        
        ...
        
        Returns
        -------
        
        ...
        
        """

        self.timeseries = pd.DataFrame(
            columns=["temperature"],
            index=pd.date_range(
                start=self.environment.start,
                end=self.environment.end,
                freq=self.environment.time_freq,
                name="time",
            ),
        )
        return self.timeseries

    def reset_time_series(self):

        """
        Info
        ----
        This function is called to reset the time series
        
        Parameters
        ----------
        
        ...
        	
        Attributes
        ----------
        
        ...
        
        Notes
        -----
        
        ...
        
        References
        ----------
        
        ...
        
        Returns
        -------
        
        ...
        
        """

        self.timeseries = pd.DataFrame(
            columns=["temperature"],
            index=pd.date_range(
                start=self.environment.start,
                end=self.environment.end,
                freq=self.environment.time_freq,
                name="time",
            ),
        )

        return self.timeseries
    
    def optimize_tes_hp(self, hp, mode):
        if mode == "optimize runtime":
            factor = 20
        elif mode == "overcome shutdown":
            factor = 60
        else:
            raise ValueError("mode needs to be 'optimize runtime' or 'overcome shutdown'.")
            
        th_demand = self.user_profile.thermal_energy_demand
        temps = pd.read_csv("./input/thermal/dwd_temp_15min_2015.csv",
                                  index_col="time")
        
        dataframe = pd.concat([th_demand, temps], axis = 1)
        dataframe.sort_values(by = ['thermal_energy_demand'], ascending = False, inplace = True)
        
        hp.th_power = round(float(dataframe['thermal_energy_demand'][0]), 1)
        hp.el_power = round(float(hp.th_power / hp.get_current_cop(dataframe['temperature'][0])), 1)
        
        density = 1  #kg/l
        
        # mass is multiple of 10
        self.mass = hp.th_power * factor * density
        self.mass = self.mass / 10
        self.mass = round(self.mass, 0)
        self.mass = self.mass * 10 + 10

