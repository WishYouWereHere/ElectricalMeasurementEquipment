import pandas as pd

#FILE_NAME = "file"
FILE_NAME= "C:\\Data\\sensor_six 120mm 07-18-2022-20-28-35" + ".csv"

#Finds rising edge for channel 1. This value corresponds to the start pulse from the TDC1000 sensor.
#pulse steady state needs to be compared against the iterating rising edge value (3 volts) to determine start pulse.
def start_pulse_edge(waveform):
    start_pulse = 0
    rows = waveform.shape[0]
    pulse_steady_state = abs(waveform.iloc[2,1])
    for itr in range(rows):
        rising_edge = abs(waveform.iloc[itr,1])
        rising_edge = rising_edge - pulse_steady_state
        if rising_edge > 3:
            #print(rising_edge)
            #print(itr)
            start_pulse = itr + 2 
            break
    return(start_pulse)

#Calculates the amplitude of the noise echo, noise echo amplitude calculation will stop if there is a water level pulse 
#detection (stop_pulse).
def calculate_noise_echo(waveform,start_pulse, stop_pulse):
    itr = start_pulse
    itr_stop_value = stop_pulse
    max_peak = waveform.iloc[start_pulse,2]
    min_peak = waveform.iloc[start_pulse,2]
    #print(itr)
    while (itr <= itr_stop_value):
        #print(itr)
        current_value = waveform.iloc[itr,2]
        if max_peak < current_value:
            max_peak = current_value
        elif min_peak > current_value:
            min_peak = current_value
        itr = itr + 1
    noise_echo_amplitude = max_peak - min_peak
    print("Noise echo amplitude equals = ", noise_echo_amplitude, "Volts")

#Calcuates noise echo time duration before returning to steady state based of % of noise of circuit versus noise of 
#noise echo pulse. Signal noise deviation is 1% of the static signal noise. Calculation works from end of waveform or
#start of stop pulse (channel 3 / water level echo pulse).
def calculate_noise_echo_time(waveform,start_pulse, stop_pulse):
    #Calculate signal noise deviation boundaries by iterating 100 times to smooth out any noise_sampling peaks/valleys
    signal_noise_deviation = .01
    noise_sampling = waveform.iloc[2,2]
    for itr in range(3, 103):
        noise_sampling = waveform.iloc[itr,2] + noise_sampling
        noise_sampling = noise_sampling / 2
    upper_noise_sampling = noise_sampling + (noise_sampling*signal_noise_deviation)
    lower_noise_sampling = noise_sampling - (noise_sampling*signal_noise_deviation)
    #print("Noise sampling value = ", noise_sampling, "Volts")
    #print("upper noise samping value = ", upper_noise_sampling)
    #print("lower noise samping value = ", lower_noise_sampling)

    noise_echo_start = waveform.iloc[start_pulse,0]
    noise_echo_stop = 0

    #Water level echo stop pulse was found
    if stop_pulse != 0:
        itr = stop_pulse
        #print("Water level echo detected")
    #No water level echo found
    else:
        itr = waveform.shape[0] - 1
        #print("No water level echo detected")
    #Begin sampling/calcuating noise echo length
    sampling = 0
    while sampling != 25:
        noise_echo = waveform.iloc[itr,2]
        #print("noise echo", noise_echo)
        if (noise_echo > upper_noise_sampling or noise_echo < lower_noise_sampling):
            sampling = 0
            itr = itr - 1
        else:
            sampling = sampling + 1
            itr = itr - 1
    #print(itr)
    noise_echo_stop = waveform.iloc[itr,0]
    noise_echo_steady_state = itr
    noise_echo_length = float(noise_echo_stop) - float(noise_echo_start)
    print("Noise echo length =",noise_echo_length ,"seconds")
    return noise_echo_steady_state
     

#Finds rising edge for channel three. This value corresponds to the stop pulse from the TDC1000 sensor
def stop_pulse_edge(waveform):
    stop_pulse = 0
    pulse_steady_state = abs(waveform.iloc[2,3])
    rows = waveform.shape[0]
    for itr in range(rows):
        rising_edge = abs(waveform.iloc[itr,3])
        rising_edge = rising_edge - pulse_steady_state
        if rising_edge > 3:
            #print(rising_edge)
            #print(itr)
            stop_pulse = itr
            break
    return(stop_pulse)

#Calculates the amplitude of the water level echo
def calculate_waterlevel_echo(waveform,stop_pulse):
    max_peak = waveform.iloc[stop_pulse,2]
    min_peak = waveform.iloc[stop_pulse,2]
    if stop_pulse != 0:
        itr = stop_pulse
        rows = waveform.shape[0]
        #print(itr)
        while (itr < rows):
            #print(itr)
            current_value = waveform.iloc[itr,2]
            if max_peak < current_value:
                max_peak = current_value
            elif min_peak > current_value:
                min_peak = current_value          
            itr = itr + 1
        waterlevel_echo_amplitude = max_peak - min_peak
        print("Water level echo amplitude equals = ", waterlevel_echo_amplitude, "Volts")

#Calculates the time of flight by finding the corresponding time values associated with the 3 Volts rising edge of channel
#one and channel three. Will not calculate a time of flight if a stop pulse is not found.
def calculate_tof(waveform,start_pulse,stop_pulse):
    start_time = waveform.iloc[start_pulse,0]
    if stop_pulse != 0:
        stop_time = waveform.iloc[stop_pulse,0] 
        time_of_flight = float(stop_time) - float(start_time)
        print("Time of flight = ", time_of_flight, "seconds")
    
#Open csv file and perform calculations
def main():
    filename = FILE_NAME 
    waveform = pd.read_csv(filename)
    start_pulse = start_pulse_edge(waveform)
    stop_pulse = stop_pulse_edge(waveform)
    calculate_waterlevel_echo(waveform,stop_pulse)
    noise_echo_steady_state = calculate_noise_echo_time(waveform,start_pulse, stop_pulse)
    calculate_noise_echo(waveform,start_pulse,noise_echo_steady_state)
    calculate_tof(waveform,start_pulse,stop_pulse)

    #write values to excel file 
    #try:
    #    with open(filename, 'r+') as filehandle:
    #        print("write to file")        
    #except:
    #    print("no file found")

main()