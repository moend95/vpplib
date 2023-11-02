import math
import numpy as np
import scipy
import pandas as pd
from scipy.signal import tf2ss, cont2discrete
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
from scipy.optimize import minimize_scalar






class ElectrolysisMoritz:
    def __init__(self,P_elektrolyseur,p2,dt):

           
        # Constants
        self.F = 96485.34  # Faraday's constant [C/mol]
        self.R = 8.314  # ideal gas constant [J/(mol*K)]
        self.n = 2  # number of electrons transferred in reaction
        self.gibbs = 237.24e3
        self.E_th_0 = 1.481  # thermoneutral voltage at standard state
        self.M = 2.016  # molecular weight [g/mol]
        self.lhv = 33.33  # lower heating value of H2 [kWh/kg]
        self.hhv = 39.41  # higher heating value of H2 [kWh/kg]
        self.roh_H2 = 0.08988 #Density in kg/m3
        self.roh_O = 1.429 #Density kg/m3
        self.T = 50 # Grad Celsius
        self.p2=p2 #bar compression
        #Leistungen/Stromdichte
        #self.max_current_density = 2 * self.cell_area                                      # Habe ich hinzugefügt um eine maximale Stromdichte zu haben #self.max_current_density wie komme sonst auf diesen Wert durch I/A oder wird der festgelegt
        #self.P_nominal = self.P_stack * self.n_stacks
        #self.P_stack = self.P_nominal/self.n_stacks
        self.P_nominal = P_elektrolyseur
        self.P_min = self.P_nominal * 0.1
        self.P_max = self.P_nominal
        
        # Stack parameters
        self.n_cells = 10  # Number of cells
        self.cell_area = 2500  # [cm^2] Cell active area
        self.temperature = 50  # [C] stack temperature
        self.max_current = 2.5  # [A/cm^2] current density #2 * self.cell_area              # Ist das nicht das selbe wie self.max_current_density

        self.p_atmo = 101325#2000000  # (Pa) atmospheric pressure / pressure of water
        self.p_anode = self.p_atmo  # (Pa) pressure at anode, assumed atmo
        self.p_cathode = 3000000
        self.n_stacks= P_elektrolyseur/(self.cell_area*self.max_current*self.n_cells)      #max_current_density abgeändert zu self.max_current
        self.P_stack = self.P_nominal/self.n_stacks # für calc_pump
        self.dt=dt
    
    def status_codes(self,df):      #tabelle
        #     long_gap_threshold = 60
    #     short_gap_threshold = 5
    #     # create a mask for power values below P_min
    #     below_threshold_mask = df['P_in'] < self.P_min

    #     # find short gaps (up to 4 steps) where power is below P_min
    #     short_gaps = below_threshold_mask.rolling(window=short_gap_threshold).sum()
    #     hot_mask = (short_gaps <= 4) & below_threshold_mask
    #     df.loc[hot_mask, 'status'] = 'hot'

    #     # find middle gaps (between 5 and 60 steps) where power is below P_min
    #     middle_gaps = below_threshold_mask.rolling(window=long_gap_threshold).sum()
    #     hot_standby_mask = ((5 <= middle_gaps) & (middle_gaps < 60)) & below_threshold_mask
    #     df.loc[hot_standby_mask, 'status'] = 'hot standby'
    #     # find long gaps (over 60 steps) where power is below P_min
    #     long_gaps = below_threshold_mask.rolling(window=long_gap_threshold).sum()
    #     cold_standby_mask = (long_gaps >= 60) & below_threshold_mask
    #     df.loc[cold_standby_mask, 'status'] = 'cold standby'

    #     # mark production periods (above P_min)
    #     production_mask = df['P_in'] >= self.P_min
    #     df.loc[production_mask, 'status'] = 'production'

    #     # add status codes
    #     df['status codes'] = df['status'].replace({
    #         'cold standby': 0,
    #         'hot standby': 1,
    #         'hot': 2,
    #         'production': 4
    #     })

    #     # add 'booting' status
    #     booting_mask = pd.Series(False, index=df.index)
    #     # Identify rows where production is True and previous row is hot standby or cold standby
    #     booting_mask |= (df['status'].eq('production') & df['status'].shift(1).isin(['hot standby', 'cold standby']))

    #     # Identify rows where production is True and status is cold standby for up to 5 rows before

    #     booting_mask |= (df['status'].eq('production') & df['status'].shift(30).eq('cold standby'))

    #     # Identify rows where production is True and status is hot standby for up to 30 rows before
    #     for i in range(1, 15):
    #         booting_mask |= (df['status'].eq('production') & df['status'].shift(i).eq('hot standby'))

    #     df.loc[booting_mask, 'status'] = 'booting'

    #     # add status codes
    #     df['status codes'] = df['status'].replace({
    #         'cold standby': 0,
    #         'hot standby': 1,
    #         'hot': 2,
    #         'production': 4,
    #         'booting': 3
    #     })


        long_gap_threshold = math.ceil(60 / self.dt)
        short_gap_threshold = math.ceil(5 / self.dt)
        # create a mask for power values below P_min
        below_threshold_mask = df['P_in'] < self.P_min

        # find short gaps (up to 4 steps) where power is below P_min
        short_gaps = below_threshold_mask.rolling(window=short_gap_threshold).sum()
        hot_mask = (short_gaps <= math.ceil(4 / self.dt)) & below_threshold_mask
        df.loc[hot_mask, 'status'] = 'hot'

        # find middle gaps (between 5 and 60 steps) where power is below P_min
        middle_gaps = below_threshold_mask.rolling(window=long_gap_threshold).sum()
        hot_standby_mask = ((math.ceil(5 / self.dt) <= middle_gaps) & (middle_gaps < math.ceil(60 / self.dt))) & below_threshold_mask
        df.loc[hot_standby_mask, 'status'] = 'hot standby'
        # find long gaps (over 60 steps) where power is below P_min
        long_gaps = below_threshold_mask.rolling(window=long_gap_threshold).sum()
        cold_standby_mask = (long_gaps >= math.ceil(60 / self.dt)) & below_threshold_mask
        df.loc[cold_standby_mask, 'status'] = 'cold standby'

        # mark production periods (above P_min)
        production_mask = df['P_in'] >= self.P_min
        df.loc[production_mask, 'status'] = 'production'

        # add status codes
        df['status codes'] = df['status'].replace({
            'cold standby': 0,
            'hot standby': 1,
            'hot': 2,
            'production': 4
        })

        # add 'booting' status
        booting_mask = pd.Series(False, index=df.index)
        # Identify rows where production is True and previous row is hot standby or cold standby
        booting_mask |= (df['status'].eq('production') & df['status'].shift(1).isin(['hot standby', 'cold standby']))

        # Identify rows where production is True and status is cold standby for up to 5 rows before

        booting_mask |= (df['status'].eq('production') & df['status'].shift(math.ceil(30 / self.dt)).eq('cold standby'))

        # Identify rows where production is True and status is hot standby for up to 30 rows before
        for i in range(math.ceil(1 / self.dt), math.ceil(15 / self.dt)):
            booting_mask |= (df['status'].eq('production') & df['status'].shift(i).eq('hot standby'))

        df.loc[booting_mask, 'status'] = 'booting'

        # add status codes
        df['status codes'] = df['status'].replace({
            'cold standby': 0,
            'hot standby': 1,
            'hot': 2,
            'production': 4,
            'booting': 3
        })
        return df
    
    def calc_cell_voltage(self, I, T):  #nicht in tabelle
        """
        I [Adc]: stack current
        T [degC]: stack temperature
        return :: V_cell [Vdc/cell]: cell voltage
        """
        T_K = T + 273.15

        # Cell reversible voltage:
        E_rev_0 = self.gibbs / (self.n * self.F)  # Reversible cell voltage at standard state
        p_atmo = self.p_atmo
        p_anode = 200000
        p_cathode = 3000000

        # Arden Buck equation T=C, https://www.omnicalculator.com/chemistry/vapour-pressure-of-water#vapor-pressure-formulas
        p_h2O_sat = (0.61121 * np.exp((18.678 - (T / 234.5)) * (T / (257.14 + T)))) * 1e3  # (Pa)

       # General Nernst equation
        E_rev = E_rev_0 + ((self.R * T_K) / (self.n * self.F)) * (
           np.log( ((p_anode - p_h2O_sat) / p_atmo)* np.sqrt((p_cathode - p_h2O_sat) / p_atmo)))

        #E_rev = E_rev_0 - ((E_rev_0* 10**-3 * T_K) + 9.523 * 10**-5 * np.log(T_K) + 9.84*10**-8* T_K**2) #empirical equation


        T_anode = T_K

        T_cathode = T_K

        # anode charge transfer coefficient
        alpha_a = 2

        # cathode charge transfer coefficient
        alpha_c = 0.5

        # anode exchange current density
        i_0_a = 2 * 10 ** (-7)

        # cathode exchange current density
        i_0_c = 10 ** (-3)

        i = I / self.cell_area

        # derived from Butler-Volmer eqs
       # V_act_a = ((self.R * T_anode) / (alpha_a * self.F)) * np.arcsinh(i / (2*i_0_a))
        #V_act_c = ((self.R * T_cathode) / (alpha_c * self.F)) * np.arcsinh(i / (2*i_0_c))
        # alternate equations for Activation overpotential
        # Option 2: Dakota: I believe this may be more accurate, found more
        # frequently in lit review
        # https://www.sciencedirect.com/science/article/pii/S0360319918309017

        z_a = 4 # stoichiometric coefficient of electrons transferred at anode
        z_c = 2 # stoichometric coefficient of electrons transferred at cathode
        i_0_a = 10**(-9) # anode exchange current density TODO: update to be f(T)?
        i_0_c = 10**(-3) # cathode exchange current density TODO: update to be f(T)?

        V_act_a = ((self.R*T_anode)/(alpha_a*z_a*self.F)) * np.log(i/i_0_a)
        V_act_c = ((self.R*T_cathode)/(alpha_c*z_c*self.F)) * np.log(i/i_0_c)

        # pulled from https://www.sciencedirect.com/science/article/pii/S0360319917309278?via%3Dihub
        lambda_nafion = 25
        t_nafion = 0.01  # cm

        sigma_nafion = ((0.005139 * lambda_nafion) - 0.00326) * np.exp(
            1268 * ((1 / 303) - (1 / T_K)))
        R_ohmic_ionic = t_nafion / sigma_nafion

        R_ohmic_elec = 50e-3

        V_ohmic = i * (R_ohmic_elec + R_ohmic_ionic)

        V_cell = E_rev + V_act_a + V_act_c + V_ohmic

        return V_cell

    def create_polarization(self):  #nicht in tabelle
        currents = np.arange(1, 5010, 10)
        voltage = []
        for i in range(len(currents)):
            voltage.append(self.calc_cell_voltage(currents[i],self.T))
        df = pd.DataFrame({"current_A": currents, "voltage_U": voltage})
        df['power_W'] = df["current_A"]*df["voltage_U"]
        #df['current_A'] = df['current_A']/self.cell_area
        return df

    def calculate_cell_current(self, P_dc): #nicht in tabelle
        '''
        P_in: Power DC in Watt
        P_cell: Power each cell
        return I: Current each cell in Ampere
        '''
        P_cell = P_dc /self.n_cells
        df = self.create_polarization()
        x = df['power_W'].to_numpy()
        y = df['current_A'].to_numpy()
        f = interp1d(x, y, kind='linear')
        return f(P_cell)

    def stack_nominal(self):    #nicht in tabelle
        '''
        stack nominal in kW
        :return:
        '''
        P_nominal = (self.create_polarization().iloc[500,0] * self.create_polarization().iloc[500,1]*self.n_cells) /1000
        return P_nominal

    def power_electronics(self, P_nominal, P_ac):  #nicht in tabelle     
        # Wirkungsgradkurve definieren
        relative_performance = [0.0,0.09,0.12,0.15,0.189,0.209,0.24,0.3,0.4,0.54,0.7,1.001]
        eta = [0.86,0.91,0.928,0.943,0.949,0.95,0.954,0.96,0.965,0.97,0.973,0.977]
        # Interpolationsfunktion erstellen
        f_eta = interp1d(relative_performance, eta)

        # Eigenverbrauch berechnen
        eta_interp = f_eta(P_ac / P_nominal)  # Interpoliere den eta-Wert

        P_electronics = P_ac * (1 - eta_interp)  # Berechne den Eigenverbrauch

        return P_electronics

    def power_dc(self, P_ac):       #tabelle
        '''
        :param P_ac:
        :return:
        '''
        P_dc = P_ac - self.power_electronics(P_ac, self.stack_nominal()/100)

        return P_dc

    def run(self, P_dc):        #tabelle
        """
        P_in [Wdc]: stack power input
        return :: H2_mfr [kg/dt]: hydrogen mass flow rate
        """
        power_left= P_dc



        I = self.calculate_cell_current(P_dc)
        V = self.calc_cell_voltage(I, self.temperature)
        eta_F = self.calc_faradaic_efficiency(I)
        mfr = (eta_F * I * self.M * self.n_cells) / (self.n * self.F)
        #power_left -= self.calc_stack_power(I, self.temperature) * 1e3
        H2_mfr = (mfr*3600)/1000 #kg/dt

        return H2_mfr

    def calc_O_mfr(self, H2_mfr):       #tabelle
        '''
        H2_mfr = massen flow rate H2 in kg/dt
        return: Oxygen flow rate in kg/dt
        '''
        roh_O = 1.429 #density Oxigen kg/m3
        O_mfr_m3 = (H2_mfr/self.roh_H2)/2
        O_mfr = O_mfr_m3*roh_O
        return O_mfr

    def calc_H2O_mfr(self, H2_mfr):     #tabelle
        '''
        H2_mfr: Hydrogen mass flow in kg
        O_mfr: Oxygen mass flow in kg
        return: needed water mass flow in kg
        '''
        M_H2O = 18.010 #mol/g
        roh_H2O = 997 #kg/m3

        ratio_M = M_H2O/self.M # (mol/g)/(mol/g)
        H2O_mfr = H2_mfr * ratio_M + 40#H2O_mfr in kg
        #H2O_mfr = H2O_mfr_kg / roh_H2O

        return H2O_mfr

    def calc_faradaic_efficiency(self, I):  #nicht in tabelle
        """
            #     I [A]: stack current
            #     return :: eta_F [-]: Faraday's efficiency
            #     Reference: https://res.mdpi.com/d_attachment/energies/energies-13-04792/article_deploy/energies-13-04792-v2.pdf
            #     """
        p = 20 #electrolyze pressure in bar
        i = I/self.cell_area

        a_1 = -0.0034
        a_2 = -0.001711
        b = -1
        c = 1

        eta_f = (a_1*p+a_2)*((i)**b)+c

        return eta_f

    def gas_drying(self,mfr_H2):
        '''
        input n_h2: mass flow in kg/h
        :param n_H2:
        :return:
        '''
        M_H2 = 2.016*10**-3  # kg/mol Molare Masse H2
        nH2 = (mfr_H2/3600)/M_H2 #kg/h in kg/s in mol/s
        cp_H2 = 14300  # J/kg*K Wärmekapazität H2

        X_in = 0.1 #Mol H2O/Mol H2
        X_out = 1 #minimum needed
        n = (X_in/(X_out-X_in))*nH2
        dT=300-20 #Temperaturdifferenz zwischen Adsorbtion und Desorption

        P_hz = cp_H2*M_H2*n*dT

        Q_des = 48600*n #J/s
        P_gasdrying = P_hz + Q_des #in W
        return P_gasdrying

    def compression(self,p2):       #tabelle
        '''
        :param p2: needed pressure in bar
        :param T: electrolyze temperature
        :return: needed Power for compression in kW/kg
        '''
        #w_isotherm = R * T * Z * ln(p2 / p1)
        #p1=101325 #p atmo in pascal
        T2 = 273.15+30
        p1 = 30 #bar
        Z = 0.95
        k = 1.4
        kk = k / (k - 1)
        eta_Ver = 0.75
        w_isentrop = kk * self.R * T2 * Z*(((p2 / p1)**kk) - 1)
        #T2 = T*(p2 / p1) ** kk
        P_compression = (((w_isentrop/self.M)/1000) * (1/3600)) / eta_Ver
        return P_compression

    def heat_cell(self, P_dc):          #tabelle
        '''
        P_dc: in W
        return: q cell in W
        '''
        V_th = self.E_th_0
        I = self.calculate_cell_current(P_dc)
        U_cell = self.calc_cell_voltage(I, self.temperature)

        q_cell = self.n_cells*(U_cell - V_th)*I
        return q_cell

    def heat_sys(self, q_cell, mfr_H2O):
        '''
        Q_cell: in kWh
        mfr_H20: in kg/dt
        return: q_loss in kW
                q_H20_fresh in kW
        '''
        c_pH2O = 0.001162 #kWh/kg*k
        dt = self.T - 20 #operate temp. - ambient temp.

        q_H2O_fresh = - c_pH2O * mfr_H2O * dt * 1.5 #multyplied with 1.5 for transport water
        q_loss = - (q_cell + q_H2O_fresh) * 0.14

        return q_loss, q_H2O_fresh

    def calc_mfr_cool(self, q_system):
        '''
        q_system in kWh
        return: mfr cooling water in kg/h
        '''
        q_system = q_system#kWh
        c_pH2O = 0.001162 #kWh/kg*k
        #operate temperature - should temperature
        mfr_cool = ((q_system)/(c_pH2O*(50-20)))

        return mfr_cool

    def calc_pump(self, mfr_H2O, P_dc, pressure):
        '''
        mfr_H2o: in kg/h
        P_stack: kw
        P_dc:kw
        pressure: in Pa
        return: kW
        '''
        # Wirkungsgradkurve Kreiselpumpe: https://doi.org/10.1007/978-3-642-40032-2
        relative_performance_pump = [0.0,0.05,0.1,0.15,0.2,0.25,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.001]
        eta_pump = [0.627,0.644,0.661,0.677,0.691,0.704,0.715,0.738,0.754,0.769,0.782,0.792,0.797,0.80]
        # Interpolationsfunktion erstellen
        f_eta_pump = interp1d(relative_performance_pump, eta_pump, kind='linear')
        # Wirkungsgrad berechnen für aktuellen
        eta_interp_pump = f_eta_pump(P_dc/(self.P_stack))  # Interpoliere den eta-Wert

        #Druckverlust Leitungen in Pa
        relative_performance_pressure = [0.0, 0.02, 0.07, 0.12, 0.16, 0.2, 0.25, 0.32, 0.36, 0.4, 0.47, 0.54, 0.59,
                                         0.63, 0.67, 0.71, 0.74, 0.77, 0.8, 0.83, 0.86, 0.89, 0.92, 0.95, 0.98, 1.01]
        dt_pressure = [0.0, 330, 1870, 3360, 5210, 8540, 12980, 21850, 27020, 32930, 44000, 59500, 70190, 80520, 90850,
                        100810,110400, 119990, 128840, 138420, 148010, 158330, 169760, 181190, 191890, 200000]
        # Interpolationsfunktion erstellen
        f_dt_pressure = interp1d(relative_performance_pressure, dt_pressure)
        # Eigenverbrauch berechnen
        dt_interp_pressure = f_dt_pressure(P_dc/(self.P_stack))  # Interpoliere den eta-Wert

        vfr_H2O = (mfr_H2O/997) #mass in volume with 997 kg/m3
        P_pump_fresh =  (vfr_H2O/3600) * (2000000) * (1-eta_interp_pump)
        P_pump_cool = (vfr_H2O / 3600) * (dt_interp_pressure) * (1 - eta_interp_pump)

        return P_pump_fresh, P_pump_cool

    
    #TODO: woher kommt mfr_H2?
    #TODO: woher kommt mfr_H20?
    #TODO: wenn windleistung 0 fehler
    def prepare_timeseries(self, ts):
        
        # #power_dc 
        ts['P_in'] = 0.0
        
        for i in range(len(ts.index)):
            if ts.loc[ts.index[i], 'P_ac'] > 0:
                ts.loc[ts.index[i], 'P_in'] = self.power_dc(ts.loc[ts.index[i], 'P_ac'])
            else:
                #WENN AC 0 = dann setzt er p_in auch auf 0
                ts.loc[ts.index[i], 'P_in'] = 0  # Beispiel: Setzen von P_in auf 0

        #status_codes
        ts = self.status_codes(ts)
        
         
        ts['hydrogen production [Kg/dt]'] = 0.0 #neue Spalte mit hydrogenproduction = 0.0 "platzhalter"
        ts['surplus electricity [kW]'] = 0.0
        ts['H20 [kg/dt]'] = 0.0
        ts['Heat Cell [W/dt]'] = 0.0
        ts['Oxygen [kg/dt]'] = 0.0
        ts['compression [kw/kg]'] = 0.0
        ts['efficiency [%]'] = 0.0
        ts['efficency with compression [%]'] = 0.0


        for i in range(len(ts.index)): #Syntax überprüfen! 
            
            
            # komtrolliert ob in der zeile status die zahl 4 steht (production)
            if ts.loc[ts.index[i], 'status'] == 'production':
                
                 
                
                #wenn die Eingangsleistung kleiner als p_eletrolyseur ist
                if ts.loc[ts.index[i], 'P_in'] <= self.P_nominal:
                    #hydrogen Nm3/dt
                    ts.loc[ts.index[i], 'hydrogen production [Kg/dt]'] = self.run(ts.loc[ts.index[i], 'P_in'])
                    #H20  kg/dt
                    ts.loc[ts.index[i], 'H20 [kg/dt]'] = self.calc_H2O_mfr(ts.loc[ts.index[i], 'hydrogen production [Kg/dt]'])
                    #Heat Cell
                    ts.loc[ts.index[i], 'Heat Cell [W/dt]'] = self.heat_cell(ts.loc[ts.index[i], 'P_in'])
                    #oxygen
                    ts.loc[ts.index[i], 'Oxygen [kg/dt]'] = self.calc_O_mfr(ts.loc[ts.index[i], 'hydrogen production [Kg/dt]'])
                    #compression
                    ts.loc[ts.index[i], 'compression [kw/kg]'] = self.compression(self.p2)*ts.loc[ts.index[i], 'hydrogen production [Kg/dt]']
                    #efficiency
                    ts.loc[ts.index[i], 'efficiency [%]'] = (((ts.loc[ts.index[i], 'hydrogen production [Kg/dt]'])*33000)/(ts.loc[ts.index[i], 'P_in'])) *100
                    #efficency with compression
                    ts.loc[ts.index[i], 'efficency with compression [%]'] = (((ts.loc[ts.index[i], 'hydrogen production [Kg/dt]'])*33000)/((ts.loc[ts.index[i], 'P_in'])+1000*ts.loc[ts.index[i], 'compression [kw/kg]'])) *100
                #wenn die Eingangsleistung größer als p_eletrolyseur ist
                else:
                    #hydrogen Nm3/dt
                    ts.loc[ts.index[i], 'hydrogen production [Kg/dt]'] = self.run(self.P_nominal)
                    #surplus electricity [kW]
                    ts.loc[ts.index[i], 'surplus electricity [kW]'] = ts.loc[ts.index[i], 'P_in'] - self.P_nominal  
                    #H20  kg/dt
                    ts.loc[ts.index[i], 'H20 [kg/dt]'] = self.calc_H2O_mfr(ts.loc[ts.index[i], 'hydrogen production [Kg/dt]'])
                    #Heat Cell
                    ts.loc[ts.index[i], 'Heat Cell [W/dt]'] = self.heat_cell(self.P_nominal)
                    #oxygen
                    ts.loc[ts.index[i], 'Oxygen [kg/dt]'] = self.calc_O_mfr(ts.loc[ts.index[i], 'hydrogen production [Kg/dt]'])
                    #compression
                    ts.loc[ts.index[i], 'compression [kw/kg]'] = self.compression(self.p2)*ts.loc[ts.index[i], 'hydrogen production [Kg/dt]']
                    #efficiency
                    ts.loc[ts.index[i], 'efficiency [%]'] = (((ts.loc[ts.index[i], 'hydrogen production [Kg/dt]'])*33000)/((ts.loc[ts.index[i], 'P_in'])-ts.loc[ts.index[i], 'surplus electricity [kW]'])) *100
                    #efficency with compression
                    ts.loc[ts.index[i], 'efficency with compression [%]'] = (((ts.loc[ts.index[i], 'hydrogen production [Kg/dt]'])*33000)/((ts.loc[ts.index[i], 'P_in'])-ts.loc[ts.index[i], 'surplus electricity [kW]']+1000*ts.loc[ts.index[i], 'compression [kw/kg]'])) *100
            
            #hochfahren
            elif ts.loc[ts.index[i], 'status'] == 'booting':
                ts.loc[ts.index[i], 'surplus electricity [kW]'] = ts.loc[ts.index[i], 'P_in'] - 0.0085*self.P_nominal
            else:
                ts.loc[ts.index[i], 'surplus electricity [kW]'] = ts.loc[ts.index[i], 'P_in']
        return ts
    


    