#Revision 2.0 (12/11/2022) - Removed hard coding of device naming(argument one), com port(argument two), output file path(argument three). 
####Added command line arguments for improved overall system functionality when being paired with the automated test station.
###Solenoid activations per every second are now counted, solenoid pulse must exceed 200mA to be valid.

import sys
import time
import serial
import datetime
import logging
import numpy as np
from threading import Thread
import os

#CSV name (make sure to end with .csv to open in excel)
output_type = '.csv'
device = sys.argv[1]
comport = sys.argv[2]
output_path = sys.argv[3] + '\\CurrentRanger\\'
logfile_dir = sys.argv[3] + '\\CurrentRanger\\Logging\\'
logfile = logfile_dir+'CurrentRanger.log'

class CurrentRanger:
    def __init__(self):
        self.stream_data = True
        self.port = comport
        self.baud = 9600
        self.thread = None
        self.serialConnection = None
        self.sample_count = 0
        self.solenoid_activated = False

    def serialStart(self):
        try:
            os.chdir(logfile_dir)
        except IOError:
            os.makedirs(logfile_dir)

        logging.basicConfig()
        logging.info("Trying to connect to port='{}' baud='{}'".format(self.port, self.baud))      
        try:
            self.serialConnection = serial.Serial(self.port, self.baud, timeout=5)
            logging.info("Connected to {} at baud {}".format(self.port, self.baud))
        except serial.SerialException as e:
            logging.error("Error connecting to serial port: {}".format(e))
            return False
        except:
            logging.error("Error connecting to serial port, unexpected exception:{}".format(sys.exc_info()))
            return False

        if self.thread == None:
            self.thread = Thread(target=self.serialStream)
            self.thread.start()

            print('Initializing data capture:', end='')
            wait_timeout = 100
            while wait_timeout > 0 and self.sample_count == 0:
                print('.', end='', flush=True)
                time.sleep(0.01)
                wait_timeout -= 1

            if (self.sample_count == 0):
                logging.error("Error: No data samples received. Aborting")
                return False

            print("OK\n")
            return True

    def serialStream(self):
        #Write to CurrrentRanger to turn on bias reading first to ensure autoranging is always enabled
        self.serialConnection.write(b'5\n')
        self.serialConnection.write(b'6\n')

        #Write to Current ranger to enable USB logging
        self.serialConnection.write(b'u\n')

        self.serialConnection.reset_input_buffer()
        self.sample_count = 0
        line_count = 0
        error_count = 0
        self.dataStartTS = datetime.datetime.now()

        # data timeout threshold (seconds) - bails out of no samples received
        data_timeout_ths = 0.5

        line = None
        device_data = bytearray()

        logging.info("Starting USB streaming loop")

        amperage = 0.0000000000
        sampling = 0
        previousSampleTime = datetime.datetime.now()
        sampleTS = datetime.datetime.now()

        while (self.stream_data):

            try:
                # get the timestamp before the data string, likely to align better with the actual reading
                ts = datetime.datetime.now()

                chunk_len = device_data.find(b"\n")
                if chunk_len >= 0:
                    line = device_data[:chunk_len]
                    device_data = device_data[chunk_len+1:]
                else:
                    line = None
                    while line == None and self.stream_data:
                        chunk_len = max(1, min(4096, self.serialConnection.in_waiting))
                        chunk = self.serialConnection.read(chunk_len)
                        chunk_len = chunk.find(b"\n")
                        if chunk_len >= 0:
                            line = device_data + chunk[:chunk_len]
                            device_data[0:] = chunk[chunk_len+1:]
                        else:
                            device_data.extend(chunk)

                if line == None:
                    continue

                line = line.decode(encoding="ascii", errors="strict")

                if (line.startswith("USB_LOGGING")):
                    if (line.startswith("USB_LOGGING_DISABLED")):
                        # must have been left open by a different process/instance
                        logging.info("CR USB Logging was disabled. Re-enabling")
                        self.serialConnection.write(b'u')
                        self.serialConnection.flush()
                    continue

                data = float(line)
                self.sample_count += 1
                line_count += 1


                #Collect amperage per "sample" and write to file after one second of sampling
                now = datetime.datetime.now()
                if now.second == previousSampleTime.second:
                    #if sampling == 0:
                    #    sampleTS = datetime.datetime.now()
                    if data >= (.250):
                        self.solenoid_counter += 1
                    else:
                        if self.solenoid_counter > 0:
                            self.solenoid_counter -= 1
                    if self.solenoid_counter == 5:
                        self.solenoid_activated = True
                        self.solenoid_counter = 0
                    amperage = amperage + float(data)
                    sampling = sampling + 1
                else:
                    try:
                        
                        avgAmperage = float(amperage / sampling)
                        #print(avgAmperage)
                        #print(sampling)
                        name = output_path + device + " - {date}".format(date = now.strftime("%Y%m%d%H")) + output_type
                        f = open(name, 'a')
                        #data = "{ts_start},{ts_stop},{avgAmerage_perSamples},{numberOfSamples}\n".format(ts_start = previousSampleTime, ts_stop = now ,avgAmerage_perSamples = avgAmperage,numberOfSamples = sampling)
                        data = "{ts_start},{ts_stop},{avgAmerage_perSamples},{solenoid_bool}\n".format(ts_start = previousSampleTime, ts_stop = now ,avgAmerage_perSamples = avgAmperage, solenoid_bool = self.solenoid_activated)
                        f.write(data)
                        f.close()
                        self.solenoid_activated = False
                        previousSampleTime = datetime.datetime.now()
                        sampling = 0
                        amperage = 0.0000000000
                        self.solenoid_activated = False
                    except:
                        pass
                
            except KeyboardInterrupt:
                logging.info('Terminated by user')
                break

            except ValueError:
                logging.error("Invalid data format: '{}': {}".format(line, sys.exc_info()))
                error_count += 1
                last_sample = (np.datetime64(datetime.now()) - (self.timestamps[-1] if self.sample_count else np.datetime64(datetime.now())))/np.timedelta64(1, 's')
                if (error_count > 100) and  last_sample > data_timeout_ths:
                    logging.error("Aborting. Error rate is too high {} errors, last valid sample received {} seconds ago".format(error_count, last_sample))
                    self.stream_data = False
                    break
                pass

            except serial.SerialException as e:
                logging.error('Serial read error: {}: {}'.format(e.strerror, sys.exc_info()))
                self.stream_data = False
                break

        self.stream_data = False

        # stop streaming so the device shuts down if in auto mode
        logging.info('Telling CR to stop USB streaming')
        
        try:
            # this will throw if the device has failed.disconnected already
            self.serialConnection.write(b'u')
        except:
            logging.warning('Was not able to clean disconnect from the device')

        logging.info('Serial streaming terminated')

    def isStreaming(self) -> bool:
        return self.stream_data

    def close(self):
        self.stream_data = False
        if self.thread != None:
            self.thread.join()
        if self.serialConnection != None:
            self.serialConnection.close()
        logging.info("Connection closed.")

def main():
    CR = CurrentRanger()
    CR.serialStart()
    try:
        while CR.isStreaming():
            time.sleep(0.01)
    except KeyboardInterrupt:
        logging.info('Terminated')
        print("Program terminated due to Keyboard Interrupt")
        CR.close()
    CR.close()

if __name__ == '__main__':
  main()