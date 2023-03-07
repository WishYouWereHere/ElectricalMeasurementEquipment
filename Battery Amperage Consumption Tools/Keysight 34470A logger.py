# Title: 34470A Data Logging Program
#Description: This program takes a sampling measurement with the 34470A and puts it out to a csv file in the same directory
#Revision 2.0 (12/11/2022) - Removed hard coding of Keysight instrument, output file path, device naming. 
####Added command line arguments for improved overall system functionality when being paired with the automated test station.
###Solenoid activations per every second are now counted, solenoid pulse must exceed 200mA to be valid.

# import python modules
import pyvisa as visa
import numpy as np
import time
import sys
from datetime import datetime
import os

device = sys.argv[1]
output_type = '.csv'
output_path = sys.argv[2] + '\\Keysight34470A\\'


class keysightMultimeter:
    #Open Connection
    rm = visa.ResourceManager('C:\\Windows\\System32\\visa32.dll')
    instrument_available = rm.list_resources()
    #Change the following line to connect to VISA Address. Here are some examples of VISA addresses
    #USB Connection: 'USB0::xxxxxx::xxxxxx::xxxxxxxxxx::0::INSTR'
    myinst = rm.open_resource(instrument_available[0])
    #myinst = rm.open_resource("USB0::0x2A8D::0x0201::MY60043129::0::INSTR")

    def __init__(self):
        self.datastream = True
        try:
            os.chdir(output_path)
        except IOError:
                os.makedirs(output_path)

    def reset(self):
        self.myinst.write("*RST")
        self.myinst.write("*CLS")
        #Configure DCV Measurement
        self.myinst.write("CONF:CURRent:DC")
        self.myinst.write("SENSe:CURRent:DC:NPLC .006")
        self.myinst.write("TRIGger:DELay MIN") #Remove to slow down sampling rate to 500 samples in 1.8 seconds
        self.myinst.write("SENSe:CURRent:DC:TERMinals 3")
        self.myinst.write("SENSe:CURRent:DC:RANGe 1")


    def initialize(self):
        self.myinst.write("*RST")
        self.myinst.write("*CLS")
        #Configure DCV Measurement
        self.myinst.write("CONF:CURRent:DC")
        self.myinst.write("SENSe:CURRent:DC:NPLC .006")
        self.myinst.write("TRIGger:DELay MIN") #Remove to slow down sampling rate to 500 samples in 1.8 seconds
        self.myinst.write("SENSe:CURRent:DC:TERMinals 3")
        self.myinst.write("SENSe:CURRent:DC:RANGe 1")

    def run_KeysightMultimeter(self)-> bool:
        return self.datastream

    def logdata(self):
        while self.datastream == True:
            try:
                ts_start = datetime.now()
                self.myinst.write("SAMPle:COUNt 1000")
                self.myinst.write("TRIG:COUN 1")
                self.myinst.write("TRIG:SOUR IMM")
                self.myinst.write("INIT")
                average_amperage_consumption = np.sum(self.myinst.query_ascii_values('FETC?'))
                if (np.max(self.myinst.query_ascii_values('FETC?')) > .200):
                    solenoid_activated = True
                else:
                    solenoid_activated = False
                ts_stop = datetime.now()
                self.myinst.write("CALCulate:CLEar")
            except KeyboardInterrupt:
                self.datastream = False
            except:
                try:
                    #attempt to reset the meter otherwise close the thread and start a new connection
                    #This print statement seems to causes issues with hanging.
                    #print("ERROR grabbing data points")
                    self.reset()
                except:
                    self.datastream = False
                    self.myinst.close()
                return

            try:
                now = datetime.now()
                name = output_path + device + " - {date}".format(date = now.strftime("%Y%m%d%H")) + output_type
                f = open(name, 'a')
                average_amperage_consumption = average_amperage_consumption / 1000
                data = "{ts_start},{ts_stop},{avgAmerage},{solenoid_bool}\n".format(ts_start = ts_start, ts_stop = ts_stop,avgAmerage = average_amperage_consumption, solenoid_bool = solenoid_activated)
                f.write(data)
                f.close()
            except KeyboardInterrupt:
                self.datastream = False
            except:
                print("ERROR writing to file")
                pass

def main():
    multimeter = keysightMultimeter()
    multimeter.initialize()
    try:
        while multimeter.run_KeysightMultimeter:
            multimeter.logdata()
            time.sleep(.000001)   
    except KeyboardInterrupt:
        print("Program terminated due to Keyboard Interrupt")
        multimeter.myinst.close()

if __name__ == '__main__':
  main()