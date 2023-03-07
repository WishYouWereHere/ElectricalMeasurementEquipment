# =============================================================================
# Python for Test and Measurement
# =============================================================================
import pyvisa as visa
import sys
import time
import numpy as np
import os

def quickscan(file_name):
    ## Number of Points to request
    USER_REQUESTED_POINTS = 50000

    ## Save Locations for CSV files
    BASE_FILE_NAME = file_name
    print(file_name)
    BASE_DIRECTORY = "C:\\Data\\"

    # VISA address ################################################################
    # Get the VISA address (or alias) from Keysight Connection Expert
    # Video: Connecting to Instruments Over LAN, USB, and GPIB in Keysight
    # Connection Expert: https://youtu.be/sZz8bNHX5u4
    VISA_ADDRESS = 'USB0::0x0957::0x17A6::MY61410127::0::INSTR'

    # Define VISA Resource Manager
    rm = visa.ResourceManager('C:\\Windows\\System32\\visa32.dll')
    # Open connection to the inst by its VISA address:
    try:
        print('\nConnecting to: {}'.format(VISA_ADDRESS))
        inst = rm.open_resource(VISA_ADDRESS)
    except Exception:
        print('Unable to connect to oscilloinst at {}. Aborting.\n'
            .format(VISA_ADDRESS))
        sys.exit()

    # Set I/O timeout to 5 seconds
    inst.timeout = 5000
    # Clear the remote interface
    inst.clear()
    IDN = str(inst.query('*IDN?'))
    print('Connected to: {}'.format(IDN))

    ##########################################################
    ##########################################################
    ## Determine Which channels are on AND have acquired data - Scope should have already acquired data and be in a stopped state (Run/Stop button is red).

    #########################################
    ## Get Number of analog channels on scope
    ## Parse IDN
    IDN = IDN.split(',') # IDN parts are separated by commas, so parse on the commas
    MODEL = IDN[1]
    if list(MODEL[1]) == "9": # This is the test for the PXIe scope, M942xA)
        NUMBER_ANALOG_CHS = 2
    else:
        NUMBER_ANALOG_CHS = int(MODEL[len(MODEL)-2])
    if NUMBER_ANALOG_CHS == 2:
        CHS_LIST = [0,0] # Create empty array to store channel states
    else:
        CHS_LIST = [0,0,0,0]
    NUMBER_CHANNELS_ON = 0
    ## After the CHS_LIST array is filled it could, for example look like: if chs 1,3 and 4 were on, CHS_LIST = [1,0,1,1]


    #############################################
    ## Get INFO for saving Waveform JPG
    #This is done by parsing the scope's identification string and looking for the 'X'.
    model = IDN[1]
    #SN = IDN[2]
    FW = IDN[3]
    FW = float(FW[:(5-len(FW))])

    scopeTypeCheck = list(model)
    if scopeTypeCheck[3] == "-" or "X" or scopeTypeCheck[1] == "9":
        generation = "X_Series"
    else:
        generation = "Older_Series"
    del scopeTypeCheck, model



    ###############################################
    ## Pre-allocate holders for the vertical Pre-ambles and Channel units

    ANALOGVERTPRES = np.zeros([12])
        ## For readability: ANALOGVERTPRES = (Y_INCrement_Ch1, Y_INCrement_Ch2, Y_INCrement_Ch3, Y_INCrement_Ch4, Y_ORIGin_Ch1, Y_ORIGin_Ch2, Y_ORIGin_Ch3, Y_ORIGin_Ch4, Y_REFerence_Ch1, Y_REFerence_Ch2, Y_REFerence_Ch3, Y_REFerence_Ch4)

    CH_UNITS = ["BLANK", "BLANK", "BLANK", "BLANK"]

    #########################################
    ## Actually find which channels are on, have acquired data, and get the pre-amble info if needed.
    ## The assumption here is that, if the channel is off, even if it has data behind it, data will not be retrieved from it.
    ## Note that this only has to be done once for repetitive acquisitions if the channel scales (and on/off) are not changed.

    inst.write(":WAVeform:POINts:MODE MAX") # MAX mode works for all acquisition types, so this is done here to avoid Acq. Type vs points mode problems. Adjusted later for specific acquisition types.

    ch = 1 
    for each_value in CHS_LIST:
        On_Off = int(inst.query(":CHANnel" + str(ch) + ":DISPlay?")) 
        if On_Off == 1: 
            Channel_Acquired = int(inst.query(":WAVeform:SOURce CHANnel" + str(ch) + ";POINts?")) 
        else:
            Channel_Acquired = 0
        if Channel_Acquired == 0 or On_Off == 0: 
            inst.write(":CHANnel" + str(ch) + ":DISPlay OFF") 
            CHS_LIST[ch-1] = 0 
        else: 
            CHS_LIST[ch-1] = 1 
            NUMBER_CHANNELS_ON += 1
            ## Might as well get the pre-amble info now
            Pre = inst.query(":WAVeform:PREamble?").split(',') # ## The programmer's guide has a very good description of this, under the info on :WAVeform:PREamble.
                ## In above line, the waveform source is already set; no need to reset it.
            ANALOGVERTPRES[ch-1]  = float(Pre[7]) # Y INCrement, Voltage difference between data points; Could also be found with :WAVeform:YINCrement? after setting :WAVeform:SOURce
            ANALOGVERTPRES[ch+3]  = float(Pre[8]) # Y ORIGin, Voltage at center screen; Could also be found with :WAVeform:YORigin? after setting :WAVeform:SOURce
            ANALOGVERTPRES[ch+7]  = float(Pre[9]) # Y REFerence, Specifies the data point where y-origin occurs, always zero; Could also be found with :WAVeform:YREFerence? after setting :WAVeform:SOURce
            ## In most cases this will need to be done for each channel as the vertical scale and offset will differ. However,
                ## if the vertical scales and offset are identical, the values for one channel can be used for the others.
                ## For math waveforms, this should always be done.
            CH_UNITS[ch-1] = str(inst.query(":CHANnel" + str(ch) + ":UNITs?").strip('\n')) 
        ch += 1
    del ch, each_value, On_Off, Channel_Acquired

    ##########################
    if NUMBER_CHANNELS_ON == 0:
        inst.clear()
        inst.close()
        sys.exit("No data has been acquired. Properly closing scope and aborting script.")

    ############################################
    ## Find first channel on (as needed/desired)
    ch = 1
    for each_value in CHS_LIST:
        if each_value == 1:
            FIRST_CHANNEL_ON = ch
            break
        ch +=1
    del ch, each_value

    ############################################
    ## Find last channel on (as needed/desired)
    ch = 1
    for each_value in CHS_LIST:
        if each_value == 1:
            LAST_CHANNEL_ON = ch
        ch +=1
    del ch, each_value

    ############################################
    ## Create list of Channel Numbers that are on
    CHS_ON = [] # Empty list
    ch = 1
    for each_value in CHS_LIST:
        if each_value == 1:
            CHS_ON.append(int(ch))
        ch +=1
    del ch, each_value
    #####################################################

    ################################################################################################################
    ## Setup data export - For repetitive acquisitions, this only needs to be done once unless settings are changed

    inst.write(":WAVeform:FORMat WORD") 
    inst.write(":WAVeform:BYTeorder LSBFirst")
    inst.write(":WAVeform:UNSigned 0") 

    #########################################################
    ## Determine Acquisition Type to set points mode properly
    ## Note:
        ## :WAVeform:POINts:MODE RAW corresponds to saving the ASCII XY or Binary data formats to a USB stick on the scope
        ## :WAVeform:POINts:MODE NORMal corresponds to saving the CSV or H5 data formats to a USB stick on the scope
    ACQ_TYPE = str(inst.query(":ACQuire:TYPE?")).strip("\n")
    if ACQ_TYPE == "AVER" or ACQ_TYPE == "HRES": 
        POINTS_MODE = "NORMal" 
    else:
        POINTS_MODE = "RAW" 

    inst.write(":WAVeform:SOURce CHANnel" + str(FIRST_CHANNEL_ON))
    inst.write(":WAVeform:POINts MAX") 
    inst.write(":WAVeform:POINts:MODE " + str(POINTS_MODE))
    MAX_CURRENTLY_AVAILABLE_POINTS = int(inst.query(":WAVeform:POINts?"))

    if MAX_CURRENTLY_AVAILABLE_POINTS < 100:
        MAX_CURRENTLY_AVAILABLE_POINTS = 100

    if USER_REQUESTED_POINTS > MAX_CURRENTLY_AVAILABLE_POINTS or ACQ_TYPE == "PEAK":
        USER_REQUESTED_POINTS = MAX_CURRENTLY_AVAILABLE_POINTS

    ## If one wants some other number of points...
    ## Tell it how many points you want
    inst.write(":WAVeform:POINts " + str(USER_REQUESTED_POINTS))

    ## Then ask how many points it will actually give you, as it may not give you exactly what you want.
    NUMBER_OF_POINTS_TO_ACTUALLY_RETRIEVE = int(inst.query(":WAVeform:POINts?"))

    #####################################################################################################################################
    #####################################################################################################################################
    ## Get timing pre-amble data and create time axis
    ## One could just save off the preamble factors and #points and post process this later...

    Pre = inst.query(":WAVeform:PREamble?").split(',') 
    X_INCrement = float(Pre[4]) # Time difference between data points; Could also be found with :WAVeform:XINCrement? after setting :WAVeform:SOURce
    X_ORIGin    = float(Pre[5]) # Always the first data point in memory; Could also be found with :WAVeform:XORigin? after setting :WAVeform:SOURce
    X_REFerence = float(Pre[6]) # Specifies the data point associated with x-origin; The x-reference point is the first point displayed and XREFerence is always 0.; Could also be found with :WAVeform:XREFerence? after setting :WAVeform:SOURce
    del Pre

    DataTime = ((np.linspace(0,NUMBER_OF_POINTS_TO_ACTUALLY_RETRIEVE-1,NUMBER_OF_POINTS_TO_ACTUALLY_RETRIEVE)-X_REFerence)*X_INCrement)+X_ORIGin
    if ACQ_TYPE == "PEAK": 
        DataTime = np.repeat(DataTime,2)

    #####################################################################################################################################
    #####################################################################################################################################
    ## Pre-allocate data array

    if ACQ_TYPE == "PEAK": # This means peak detect mode ### SEE IMPORTANT NOTE ABOUT PEAK DETECT MODE AT VERY END, specific to fast time scales
        Wav_Data = np.zeros([NUMBER_CHANNELS_ON,2*NUMBER_OF_POINTS_TO_ACTUALLY_RETRIEVE])
        ## Peak detect mode returns twice as many points as the points query, one point each for LOW and HIGH values
    else: # For all other acquistion modes
        Wav_Data = np.zeros([NUMBER_CHANNELS_ON,NUMBER_OF_POINTS_TO_ACTUALLY_RETRIEVE])

    ###################################################################################################
    ###################################################################################################
    ## Determine number of bytes that will actually be transferred and set the "chunk size" accordingly.

    ## Get the waveform format
    WFORM = str(inst.query(":WAVeform:FORMat?"))
    if WFORM == "BYTE":
        FORMAT_MULTIPLIER = 1
    else: #WFORM == "WORD"
        FORMAT_MULTIPLIER = 2

    if ACQ_TYPE == "PEAK":
        POINTS_MULTIPLIER = 2 # Recall that Peak Acq. Type basically doubles the number of points.
    else:
        POINTS_MULTIPLIER = 1

    TOTAL_BYTES_TO_XFER = POINTS_MULTIPLIER * NUMBER_OF_POINTS_TO_ACTUALLY_RETRIEVE * FORMAT_MULTIPLIER + 11
        ## Why + 11?  The IEEE488.2 waveform header for definite length binary blocks (what this will use) consists of 10 bytes.  The default termination character, \n, takes up another byte.
            ## If you are using mutliplr termination characters, adjust accordingly.
        ## Note that Python 2.7 uses ASCII, where all characters are 1 byte.  Python 3.5 uses Unicode, which does not have a set number of bytes per character.

    ## Set chunk size:
        ## More info @ http://pyvisa.readthedocs.io/en/stable/resources.html
    if TOTAL_BYTES_TO_XFER >= 400000:
        inst.chunk_size = TOTAL_BYTES_TO_XFER

    #####################################################
    #####################################################
    ## Pull waveform data, scale it

    now = time.perf_counter() # Only to show how long it takes to transfer and scale the data.
    i  = 0 # index of Wav_data, recall that python indices start at 0, so ch1 is index 0
    for channel_number in CHS_ON:
            ## Gets the waveform in 16 bit WORD format
        ## The below method uses an IEEE488.2 compliant definite length binary block transfer invoked by :WAVeform:DATA?.
            ## ASCII transfers are also possible, but MUCH slower.
            Wav_Data[i,:] = np.array(inst.query_binary_values(':WAVeform:SOURce CHANnel' + str(channel_number) + ';DATA?', "h", False)) # See also: https://PyVisa.readthedocs.io/en/stable/rvalues.html#reading-binary-values

            ## Notice that the waveform source is specified, and the actual data query is concatenated into one line with a semi-colon (;) essentially like this:
                ## :WAVeform:SOURce CHANnel1;DATA?
                ## This makes it "go" a little faster.

            ## When the data is being exported w/ :WAVeform:DATA?, the oscilloscope front panel knobs don't work; they are blocked like :DIGitize, and the actions take effect AFTER the data transfer is complete.
            ## The :WAVeform:DATA? query can be interrupted without an error by doing a device clear: KsInfiniiVisionX.clear()

            ## Scales the waveform
            ## One could just save off the preamble factors and post process this later.
            Wav_Data[i,:] = ((Wav_Data[i,:]-ANALOGVERTPRES[channel_number+7])*ANALOGVERTPRES[channel_number-1])+ANALOGVERTPRES[channel_number+3]
                ## For clarity: Scaled_waveform_Data[*] = [(Unscaled_Waveform_Data[*] - Y_reference) * Y_increment] + Y_origin

            i +=1

    ## Reset the chunk size back to default if needed.
    if TOTAL_BYTES_TO_XFER >= 400000:
        inst.chunk_size = 20480

    del i, channel_number
    print("\n\nIt took " + str(time.perf_counter() - now) + " seconds to transfer and scale " + str(NUMBER_CHANNELS_ON) + " channel(s). Each channel had " + str(NUMBER_OF_POINTS_TO_ACTUALLY_RETRIEVE) + " points.\n")
    del now

    # Close instrument connection
    #inst.close()
    #del inst
    #print('Done.')

    ########################################################
    ## Save As CSV - easy to deal with later, but slow and large
    ########################################################

    ## Create column titles
    column_titles = "Time (s),"
    for channel_number in CHS_ON:
        if channel_number == LAST_CHANNEL_ON:
            column_titles = column_titles + "Channel " + str(channel_number) + " (" + CH_UNITS[channel_number-1] + ")\n"
        else:
            column_titles = column_titles + "Channel " + str(channel_number) + " (" + CH_UNITS[channel_number-1] + "),"
    del channel_number

    ## Save data
    ## The np.insert essentially deals with the fact that Wav_Data is a multi-dimensional array and DataTime is a 1 1D array, and cannot otherwise be concatenated easily.

    NewData = (np.insert(Wav_Data, 0, DataTime, axis = 0)).T
    now = time.perf_counter() # Only to show how long it takes to save
    filename = BASE_DIRECTORY + BASE_FILE_NAME + ".csv"
    with open(filename, 'w') as filehandle: # w means open for writing; can overwrite
        np.savetxt(filename, NewData, delimiter= ',', header = column_titles)
            
    print("It took " + str(time.perf_counter() - now) + " seconds to save " + str(NUMBER_CHANNELS_ON) + " channels and the time axis in csv format. Each channel had " + str(NUMBER_OF_POINTS_TO_ACTUALLY_RETRIEVE) + " points.\n")
    del now

    ## Read csv data back into python with:
    #with open(filename, 'r') as filehandle: # r means open for reading
    #    recalled_csv_data = np.loadtxt(filename,delimiter=',',skiprows=1)
    #del filehandle, filename, column_titles
    #print('CSV data has been recalled into "recalled_csv_data".\n')


    ### save image file
    #Set the directory where you want the screen image to save
    #os.chdir('C:\\Data')  #change the working directory
    #workingdirectory = os.getcwd()  #check working directory again

    #print ("The working directory is now: " + workingdirectory)


    ##############################################################################################################################################################################
    ##############################################################################################################################################################################
    ## Get and parse the IDN string to determine scope generation
    ##############################################################################################################################################################################
    ##############################################################################################################################################################################





        # The following function takes the raw PNG image data, which is an IEEE binary 
        #block, and interprets the header.  The header tells us how many bytes are
        #in the image file.  The function strips off the header and outputs the 
        #rest of the data to be saved to a .png file.
        #Note: A python function can be defined anywhere in the program, as long 
        #as it is defined prior to being called.
    def binblock_raw(data_in):

        #Grab the beginning section of the image file, which will contain the header.
        Header = str(data_in[0:12])
        print("Header is " + str(Header))
        
        #Find the start position of the IEEE header, which starts with a '#'.
        startpos = Header.find("#")
        print("Start Position reported as " + str(startpos))
        
        #Check for problem with start position.
        if startpos < 0:
            raise IOError("No start of block found")
            
        #Find the number that follows '#' symbol.  This is the number of digits in the block length.
        Size_of_Length = int(Header[startpos+1])
        print("Size of Length reported as " + str(Size_of_Length))
        
        ##Now that we know how many digits are in the size value, get the size of the image file.
        Image_Size = int(Header[startpos+2:startpos+2+Size_of_Length])
        print("Number of bytes in image file are: " + str(Image_Size))
        
        # Get the length from the header
        offset = startpos+Size_of_Length
        
        # Extract the data out into a list.
        return data_in[offset:offset+Image_Size]
        
    ###########################################################################


    inst.query(':SYSTEM:DSP "";*OPC?') # Turns off previously displayed (non-error) messages

    #The following command defines whether the image background will be black or white.
    #If you want to save ink, turn on this 'inKsaver' setting.
    inst.write(":HARDCOPY:INKsAVER OFF")
    # Ask scope for screenshot in png format
    if generation == "Older_Series":
        inst.write(":DISPlAY:DATA? PNG, SCREEN, COLOR") # The older InfiniiVisions have 3 parameters
    elif generation == "X_Series":
        if FW >= 7.2:
            inst.write(":DISPlay:MESSage:CLEar") # This gets rid of the "Remote Operation Complete" system message
        inst.write(":DISPlay:DATA? PNG,COLor") # The newer InfiniiVision-Xs do not have the middle parameter above
        ## Note that for repeated acquisitions on scopes not running sw rev 7.20 and higher, the only way to prevent the 
            ## "Remote Operation Complete" message is to insert a short wait.

    Image_Data = inst.read_raw()
    print("Image has been read.\n")
    #Returns image data as a List of floating values
    Image_Data = binblock_raw(Image_Data)

    #open a file and write the data to it.
    #Feel free to change the file name.
    filename =  BASE_DIRECTORY + BASE_FILE_NAME + ".png"
    print(filename)
    file = open(filename, "wb") # wb means open for writing in binary; can overwrite
    print(str(file))
    file.write(Image_Data)
    file.close()


    # Close instrument connection
    inst.close()
    del inst
    print('Done.')
