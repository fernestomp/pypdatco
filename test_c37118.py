# -*- coding: utf-8 -*-
#declaring coding is useful when we are working with other platforms
#like raspberry pi (ie degress symbol)
import socket
import time
import math
import crcmod
from get_crc16 import get_crc16 #own function
from request_cfg2 import request_cfg2 #own function
from decode_cfg2 import decode_cfg2 #own function
from send_command import send_command #own function
from decode_dataframe import decode_dataframe #own function
from read_data import read_data #own function

#PMU idcode
idcode=1
tcpip= "10.10.200.22"
tcpport = 4712
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
s.connect((tcpip, tcpport))

#ask for cfg2 to get the PMU parameters to use with the received dataframe
cfg2 = request_cfg2(s,idcode)
#decode cfg2 and get parameters of the pmu in a dict
diccfg2=decode_cfg2(cfg2)

#send command to turn ON data transmission
cmd = 0b0010
send_command(s,idcode,cmd)


#read  measurements
#this code is not optimal, n frames per second are expected
#is only for testing purposes, data could be lost or superimposed
n= 0
dataframenumber = 0 #counter for dataframes
#ask for n dataframes
for i in range(5):
    [dframe,crcok] = read_data(s)
    print('Dataframe # {}, CRC OK: {}:-----------------------------------------'.format(i+1,crcok))
#     print(dframe.hex())
    #Important: if the crc of the dataframe is wrong, is better to not
    #decode data because magnitudes of voltage could be wrong and cause
    #trouble, also, the function decode_dataframe is tested only
    #with good dataframes
    if crcok:
        dictdf = decode_dataframe(dframe,diccfg2,verbose=False)
        print('ACK byte: {}'.format(dictdf['ACK']))
        print('Frame type: {}'.format(dictdf['frameType']))
        print('Frame type string: {}'.format(dictdf['frameTypeStr']))
        print('Protocol version: {}'.format(dictdf['protocolVer']))
        print('Framesize: {}'.format(dictdf['FRAMESIZE']))
        print('IDCODE: {}'.format(dictdf['IDCODE']))
        print('SOC: {}'.format(dictdf['SOC']))
        print('FRACSEC raw: {}'.format(dictdf['FRACSEC']))
        print('TIME_QUALITY raw: {}'.format(dictdf['TIME_QUALITY']))
        print('Unix Time: {}'.format(dictdf['TIME_UNIX']))
        print('Human readable time: {}'.format(dictdf['TIME']))
        print('Stat bits raw: {}'.format(dictdf['STAT_bits'].hex()))
        print('Data is valid: {}'.format(dictdf['STAT_VALID_DATA']))
        print('PMU error: {}'.format(dictdf['STAT_PMU_ERROR']))
        print('PMU sync: {}'.format(dictdf['STAT_TIME_SYNC']))
        print('Data sorting: {}'.format(dictdf['STAT_DATA_SORTING']))
        print('PMU trigger detected: {}'.format(dictdf['STAT_TRIGGER_DETECTED']))
        print('Configuration changed: {}'.format(dictdf['STAT_CONFIG_CHANGED']))
        print('Unlocked time: {}'.format(dictdf['STAT_UNLOCKED_TIME']))
        print('Trigger reason: {}'.format(dictdf['STAT_TRIGGER_REASON']))
        for i in range(diccfg2['PHNMR']):
            print('Phasor #{}: {}, {:0.2f}{} {:0.2f}°'.format(
                i+1,diccfg2['PHASOR_names'][i],dictdf['PHASORS_magnitude'][i],
                    diccfg2['PHUNIT_str'][i][0],dictdf['PHASORS_angle'][i]))

        for i,n in enumerate(diccfg2['ANALOG_names']):
            print('Analog value #{}: {}, {:0.3f}'.format(
                i+1,n,round(dictdf['ANALOG'][i],3)))
        print('Frequency: {:0.6f}'.format(dictdf['FREQ']))
        print('DFREQ: {:0.6f}'.format(dictdf['DFREC']))
        print('Digital word: 0x{}'.format(dictdf['DIGITAL'].hex()))
    print('')

#send command to turn off data transmission
cmd = 0b000
send_command(s,idcode,cmd)
s.close()
