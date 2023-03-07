import numpy as np
import pandas as pd
import os

#directory = "C:\\Users\\phelpsa\\Desktop\\batteryconsumption\\sleep mode\\"
directory = "C:\\Users\\phelpsa\\Desktop\\batteryconsumption\\FPS\\1262023\\CurrentRanger\\"
newfile = "C:\\Users\\phelpsa\\Desktop\\batteryconsumption\\FPS\\1262023\\CurrentRanger\\consumptiondata2.csv"

def readfiles():
    print("reading file")
    for filename in os.listdir(directory):
        file = directory + filename
        with open(file, 'r') as f: # open in readonly mode
        # do your stuff
            df = pd.read_csv(file, header = None)
            df2 = df.mean(axis='rows', numeric_only = True )
            #debug 
            #print(df2.to_string(index= False))
            #print(file)
            consumption = df2.to_string(index= False)
            try:
                g = open(newfile, 'a')
                data = "{consumption},{file}\n".format(consumption = consumption,file = file)
                g.write(data)
                g.close()
            except:
                print("ERROR writing to file")
                pass
            


def main():
    readfiles()

if __name__ == '__main__':
  main()