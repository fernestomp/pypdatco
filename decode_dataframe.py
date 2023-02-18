# -*- coding: utf-8 -*-
#useful with raspberry pi
import struct
import math
from datetime import datetime
def decode_dataframe(data,cfg2dict,verbose = False):
    '''
        Function to decode the dataframe.

        Parameters
        ----------
        cfg2frame: bytearray
            Configuration frame 2 to decode.

        verbose: bool
            If true, it will print the decoded data.

        Returns
        -------
        dict
            Dictionary with the decoded data.
        '''
    #####################################################
    # 1 field SYNC
    field1_1 = data[0] #it has to be 0xAA
    if field1_1 != 0xAA:
        print('Transmission error: SYNC byte is {}'.format(field1_1.hex()))
    field1_2 = data[1] #version number
    ACKread = field1_1
    DATAFRAMETYPEread = field1_2 & 0b01110000 #bits 6-4
    if DATAFRAMETYPEread == 0b000:
        strDATAFRAMETYPEread = 'Data Frame'

    elif DATAFRAMETYPEread == 0b001:
        strDATAFRAMETYPEread = 'Header Frame'

    elif DATAFRAMETYPEread == 0b010:
        strDATAFRAMETYPEread = 'Configuration Frame 1'

    elif DATAFRAMETYPEread == 0b011:
        strDATAFRAMETYPEread = 'Configuration Frame 2'

    elif DATAFRAMETYPEread == 0b100:
        strDATAFRAMETYPEread = 'Command Frame'
    else:
        assert False, 'Decoding dataframe error: dataframe type {}'.format(DATAFRAMETYPEread)

    VERread = field1_2 &0b00001111
    #######################################################
    #2 FRAMESIZE
    #it's always 18 because im not using the EXTFRAME data (table 12-command frame configuration)
    [field2_1, field2_2] =data[2:4]
    FRAMESIZEread = int.from_bytes([field2_1,field2_2],'big')
    #######################################################
    # 3 field IDCODE
    #dividir en dos bytes y hacer un bitshift 8 lugares a la derecha
    [field3_1, field3_2] = data[4:6]
    IDCODEread = int.from_bytes([field3_1,field3_2],'big')
    #######################################################
    #4 SOC
    [field4_1, field4_2, field4_3, field4_4] = data[6:10]
    SOCread = int.from_bytes([field4_1,field4_2,field4_3,field4_4],'big')
    #######################################################
    #5 FRACSEC
    [field5_1, field5_2, field5_3, field5_4] = data[10:14]
    FRACSECread = int.from_bytes([field5_2,field5_3,field5_4],'big')

    TIME_QUALITY = field5_1
    TQbit7 = TIME_QUALITY & 128 #reserved
    TQbit6 = TIME_QUALITY & 64 #leap second direction 0 for add, 1 for delete
    #Leap second ocurred. Set in the first second after the leap
    #second occurs and remains set for 24h.
    TQbit5 = TIME_QUALITY & 32
    #Leap second pending. Set before a leap second occurs and cleared
    #in the second anfter the leap second occurs.
    TQbit4 = TIME_QUALITY & 16
    TQbits3_0 = TIME_QUALITY & 15

    TIME_POSIX = SOCread + (FRACSECread/cfg2dict['TIME_BASE']);
    #from unix timestamp to human readable time
    TIMEread = datetime.utcfromtimestamp(TIME_POSIX).strftime('%Y-%m-%d %H:%M:%S.%f')
    ########################################################
    #6 STAT
    # Bitmapped flags.
    # Bit 15: Data valid, 0 when PMU data is valid, 1 when invalid or PMU is in
    # test mode.
    # Bit 14: PMU error including configuration error, 0 when no error.
    # Bit 13: PMU sync, 0 when in sync.
    # Bit 12: Data sorting, 0 by time stamp, 1 by arrival.
    # Bit 11: PMU trigger detected, 0 when no trigger.
    # Bit 10: Configuration changed, set to 1 for 1 min when configuration
    # changed.
    # Bits 09–06: Reserved for security, presently set to 0.
    # Bits 05–04: Unlocked time: 00 = sync locked, best quality
    # 01 = Unlocked for 10 s
    # 10 = Unlocked for 100 s
    # 11 = Unlocked over 1000 s
    # Bits 03–00: Trigger reason:
    # 1111–1000: Available for user definition
    # 0111: Digital 0110: Reserved
    # 0101: df/dt high 0100: Frequency high/low
    # 0011: Phase-angle diff 0010: Magnitude high
    # 0001: Magnitude low 0000: Manual
    STATread = data[14:16]
    STATbit15 = (STATread[0] & 0b10000000) >> 7
    STATbit14 = (STATread[0] & 0b01000000) >> 6
    STATbit13 = (STATread[0] & 0b00100000) >> 5
    STATbit12 = (STATread[0] & 0b00010000) >> 4
    STATbit11 = (STATread[0] & 0b00001000) >> 3
    STATbit10 = (STATread[0] & 0b00000100) >> 2
    STATbit09 = (STATread[0] & 0b00000010) >> 1
    STATbit08 = STATread[0] & 0b00000001

    STATbit05_04 = (STATread[1] & 0b00110000) >> 4
    STATbit03_00 = STATread[1] & 0b00001111

    if STATbit15 == 0:
        #print('STATbit15: {}. Data is valid.'.format(STATbit15))
        STAT_VALID_DATA = True
    elif STATbit15 ==1:
        #print('STATbit15: {}. Data is not valid or PMU is in test mode'.format(
        #    STATbit15))
        STAT_VALID_DATA = False

    if STATbit14 == 0:
        #print('STATbit14: {}. PMU error: No error'.format(STATbit14))
        STAT_PMU_ERROR = False
    elif STATbit14 == 1:
        #print('STATbit14: {}. PMU error: Error'.format(STATbit14))
        STAT_PMU_ERROR = True

    if STATbit13 == 0:
        #print('STATbit13: {}. Time synchronized: Sync'.format(STATbit13))
        STAT_TIME_SYNC = True
    elif STATbit13 == 1:
        STAT_TIME_SYNC = False
        #print('STATbit13: {}. Time synchronized: Time synchronization lost'.format(STATbit13))

    if STATbit12 == 0:
        #print('STATbit12: {}. Data sorting: by timestamp'.format(STATbit12))
        STAT_DATA_SORTING ='timestamp'
    elif STATbit12 == 1:
        #print('STATbit12: {}. Data sorting: by arrival'.format(STATbit12))
        STAT_DATA_SORTING ='arrival'

    if STATbit11 == 0:
        #print('STATbit11: {}. Trigger detected: No Trigger'.format(STATbit11))
        STAT_TRIGGER_DETECTED = False
    elif STATbit11 == 1:
        #print('STATbit11: {}. Trigger detected: Yes'.format(STATbit11))
        STAT_TRIGGER_DETECTED = True

    if STATbit10 == 0:
        #print('STATbit10: {}. Configuration changed: No'.format(STATbit10))
        STAT_CONFIG_CHANGED = False
    elif STATbit10 == 1:
        #print('STATbit10: {}. Configuration changed: Yes'.format(STATbit10))
        STAT_CONFIG_CHANGED = True

    if STATbit05_04 == 0b00:
        #print('STATbit05_04: {}. sync locked, best quality'.format(STATbit05_04))
        STAT_UNLOCKED_TIME = 'sync_locked'
    elif STATbit05_04 == 0b01:
        #print('STATbit05_04: {}. Unlocked for 10 s'.format(STATbit05_04))
        STAT_UNLOCKED_TIME = 'unlocked_10'
    elif STATbit05_04 == 0b10:
        #print('STATbit05_04: {}. Unlocked for 100 s'.format(STATbit05_04))
        STAT_UNLOCKED_TIME = 'unlocked_100'
    elif STATbit05_04 == 0b11:
        #print('STATbit05_04: {}. Unlocked for over 1000 s'.format(STATbit05_04))
        STAT_UNLOCKED_TIME = 'unlocked_1000'

    if STATbit03_00 == 0b0111:
        STAT_TRIGGER_REASON = 'digital'
        #print('STATbit03_00: {}. Trigger reason: Digital'.format(STATbit03_00))
    elif STATbit03_00 == 0b0101:
        #print('STATbit03_00: {}. Trigger reason: df/dt high'.format(STATbit03_00))
        STAT_TRIGGER_REASON = 'dfdt_high'
    elif STATbit03_00 == 0b0011:
        #print('STATbit03_00: {}. Trigger reason: Phase-angle diff'.format(STATbit03_00))
        STAT_TRIGGER_REASON = 'phangle_diff'
    elif STATbit03_00 == 0b0001:
    #    print('STATbit03_00: {}. Trigger reason: Magnitude low'.format(STATbit03_00))
        STAT_TRIGGER_REASON = 'magnitude_low'
    elif STATbit03_00 == 0b0110:
        #print('STATbit03_00: {}. Trigger reason NA: reserved bits'.format(STATbit03_00))
        STAT_TRIGGER_REASON = 'reserved_bits'
    elif STATbit03_00 == 0b100:
        #print('STATbit03_00: {}. Trigger reason: Frequency high/low'.format(STATbit03_00))
        STAT_TRIGGER_REASON = 'freq_high_low'
    elif STATbit03_00 == 0b010:
        #print('STATbit03_00: {}. Trigger reason: Magnitude high'.format(STATbit03_00))
        STAT_TRIGGER_REASON = 'magnitude_high'
    elif STATbit03_00 == 0b000:
    #    print('STATbit03_00: {}. Trigger reason: Manual'.format(STATbit03_00))
        STAT_TRIGGER_REASON = 'manual'
    elif STATbit03_00  > 0b1000 and STATbit03_00  <0b1111:
        #print('STATbit03_00: {}. Trigger reason: user definition'.format(STATbit03_00))
        STAT_TRIGGER_REASON = 'user'
    ##############################################
    #PHASORS
    #float type: 8 bytes
    if cfg2dict['FORMAT_phasor'] == 'float':
        nbytes= 8
        phEndbyte = 16 + (nbytes*cfg2dict['PHNMR'])
        phasors = data[16:phEndbyte]
        phasorMagnitude = []
        phasorAngle =[]
        if cfg2dict['PHASOR_notation'] == 'polar':
            #first 4 bytes are the magnitude, next four bytes are the angle (i+4:i+8)
            for i in range(0,(cfg2dict['PHNMR']*nbytes),nbytes):
                #to convert bytestring to 32 bit floating point number
                phasorMagnitude.append(struct.unpack('>f', phasors[i:i+4])[0])
                #conversion to degrees
                phasorAngle.append(math.degrees( struct.unpack('>f', phasors[i+4:i+8])[0]))

        elif cfg2dict['PHASOR_notation'] == 'rectangular':
            print('Rectangular notation not implemented yet')

    elif cfg2dict['FORMAT_phasor'] == 'int':
        print('Integer phasor format not implemented yet')
    ######################################################
    #FREQ
    if cfg2dict['FORMAT_freq_dfreq'] == 'float':
        nbytes= 4
        freqEndbyte = phEndbyte + nbytes
        #to convert bytestring to 32 bit floating point number
        FREQread = struct.unpack('>f', data[phEndbyte:freqEndbyte])[0]

    elif cfg2dict['FORMAT_freq_dfreq'] =='int':
        #not tested yet
        nbytes= 2
        freqEndbyte = phEndbyte + nbytes
        #to convert bytestring to 32 bit floating point number
        FREQread = int.from_bytes(data[phEndbyte:freqEndbyte],'big')
    ###############################################################
    #DFREQ
    if cfg2dict['FORMAT_freq_dfreq'] == 'float':
        nbytes= 4
        dFreqEndbyte = freqEndbyte + nbytes
        #to convert bytestring to 32 bit floating point number
        DFREQread = struct.unpack('>f', data[freqEndbyte:dFreqEndbyte])[0]

    elif cfg2dict['FORMAT_freq_dfreq'] == 'int':
        #not tested yet
        nbytes= 2
        dFreqEndbyte = freqEndbyte + nbytes
        #to convert bytestring to 16 bits integer number
        DFREQread = int.from_bytes(data[freqEndbyte:dFreqEndbyte],'big')
    #################################################################
    #ANALOG
    if cfg2dict['FORMAT_analog'] == 'float':
        nbytes = 4
        analogEndbyte = dFreqEndbyte + (nbytes * cfg2dict['ANNMR'])
        ANALOGSread = data[dFreqEndbyte:analogEndbyte]
        ANALOGvalues = []
        for i in range(0,(cfg2dict['ANNMR']*nbytes),nbytes):
            ANALOGvalues.append(struct.unpack('>f', ANALOGSread[i:i+nbytes])[0])
    elif cfg2dict['FORMAT_analog'] == 'int':
        #not tested yet
        nbytes= 2
        analogEndbyte = dFreqEndbyte + (nbytes * cfg2dict['ANNMR'])
        ANALOGSread = data[dFreqEndbyte:analogEndbyte]
        #to convert bytestring to 16 bits integer number
        ANALOGvalues = int.from_bytes(ANALOGSread[i:i+nbytes],'big')
    ################################################################
    #DIGITAL
    nbytes = 2
    digitalEndbyte = analogEndbyte + nbytes
    DIGITALread = data[analogEndbyte:digitalEndbyte]
    ###############################################################
    #CREATE DICT WITH DATAFRAME VALUES TO return
    dictDATAread = {
        'ACK': field1_1,
        'frameType': DATAFRAMETYPEread,
        'frameTypeStr': strDATAFRAMETYPEread,
        'protocolVer': VERread,
        'FRAMESIZE': FRAMESIZEread,
        'IDCODE': IDCODEread,
        'SOC': SOCread,
        'FRACSEC': FRACSECread,
        'TIME_QUALITY': TIME_QUALITY,
        'TIME_UNIX': TIME_POSIX,
        'TIME': TIMEread,
        'STAT_bits': STATread,
        'STAT_VALID_DATA': STAT_VALID_DATA,
        'STAT_PMU_ERROR': STAT_PMU_ERROR,
        'STAT_TIME_SYNC': STAT_TIME_SYNC,
        'STAT_DATA_SORTING': STAT_DATA_SORTING,
        'STAT_TRIGGER_DETECTED': STAT_TRIGGER_DETECTED,
        'STAT_CONFIG_CHANGED': STAT_CONFIG_CHANGED,
        'STAT_UNLOCKED_TIME': STAT_UNLOCKED_TIME,
        'STAT_TRIGGER_REASON': STAT_TRIGGER_REASON,
        'PHASORS_magnitude': phasorMagnitude,
        'PHASORS_angle': phasorAngle,
        'FREQ': FREQread,
        'DFREC': DFREQread,
        'ANALOG': ANALOGvalues,
        'DIGITAL':DIGITALread,
    }
    ################################################################
    #PRINT VALUES
    if verbose == True:
        print('ACK: {}'.format(hex(ACKread).upper()))
        print('Dataframe type: {}'.format(strDATAFRAMETYPEread))
        print('Protocol version: {}'.format(VERread))
        print('Framesize: {}'.format(FRAMESIZEread))
        print('IDCODE: {}'.format(IDCODEread))
        print('SOC: {}'.format(SOCread))
        print('Fraction of second (raw): {}'.format(FRACSECread))
        ##############################################################
        # decode time quality bits
        if TQbit6 ==0:
                print('Leap second direction: False')
        elif TQbit6 ==1:
                print('Leap second direction: True')
        #probar que TQbit6 sea 0 o 1, si no manda un error
        assert TQbit6   <=1, 'TQbit6 debe ser 0 o 1,no {}'.format(TQbit6)
        if TQbit5 ==0:
                print('Leap second ocurred: False')
        elif TQbit5 ==1:
                print('Leap second ocurred: True')
        #probar que TQbit5 sea 0 o 1, si no manda un error
        assert TQbit5   <=1, 'TQbit5 debe ser 0 o 1,no {}'.format(TQbit5)
        if TQbit4 ==0:
                print('Leap second pending: False')
        elif TQbit4 ==1:
                print('Leap second pending: True')
        #probar que TQbit4 sea 0 o 1, si no manda un error
        assert TQbit4   <=1, 'TQbit4 debe ser 0 o 1,no {}'.format(TQbit4)

        if TQbits3_0 == 15:
            print('Fault-Clock failure, time not reliable.')
        if TQbits3_0 == 11:
            print('Clock unlocked, time within 10 s.')
        if TQbits3_0 == 10:
            print('Clock unlocked, time within 1 s.')
        if TQbits3_0 == 9:
            print('Clock unlocked, time within 10E-1 s.')
        if TQbits3_0 == 8:
            print('Clock unlocked, time within 10E-2 s.')
        if TQbits3_0 == 7:
            print('Clock unlocked, time within 10E-3 s.')
        if TQbits3_0 == 6:
            print('Clock unlocked, time within 10E-4 s.')
        if TQbits3_0 == 5:
            print('Clock unlocked, time within 10E-5 s.')
        if TQbits3_0 == 4:
            print('Clock unlocked, time within 10E-6 s.')
        if TQbits3_0 == 3:
            print('Clock unlocked, time within 10E-7 s.')
        if TQbits3_0 == 2:
            print('Clock unlocked, time within 10E-8 s.')
        if TQbits3_0 == 1:
            print('Clock unlocked, time within 10E-9 s.')
        if TQbits3_0 == 0:
            print('Normal operation, clock locked')
        #########################################################
        print('SOC time stamp: {} UTC'.format(TIMEread))
        ##########################################################
        if STATbit15 == 0:
            print('STATbit15: {}. Data is valid.'.format(STATbit15))
        elif STATbit15 ==1:
            print('STATbit15: {}. Data is not valid or PMU is in test mode'.format(
                STATbit15))

        if STATbit14 == 0:
            print('STATbit14: {}. PMU error: No error'.format(STATbit14))
        elif STATbit14 == 1:
            print('STATbit14: {}. PMU error: Error'.format(STATbit14))

        if STATbit13 == 0:
            print('STATbit13: {}. Time synchronized: Sync'.format(STATbit13))
        elif STATbit13 == 1:
            print('STATbit13: {}. Time synchronized: Time synchronization lost'.format(STATbit13))

        if STATbit12 == 0:
            print('STATbit12: {}. Data sorting: by timestamp'.format(STATbit12))
        elif STATbit12 == 1:
            print('STATbit12: {}. Data sorting: by arrival'.format(STATbit12))

        if STATbit11 == 0:
            print('STATbit11: {}. Trigger detected: No Trigger'.format(STATbit11))
        elif STATbit11 == 1:
            print('STATbit11: {}. Trigger detected: Yes'.format(STATbit11))

        if STATbit10 == 0:
            print('STATbit10: {}. Configuration changed: No'.format(STATbit10))
        elif STATbit10 == 1:
            print('STATbit10: {}. Configuration changed: Yes'.format(STATbit10))

        if STATbit05_04 == 0b00:
            print('STATbit05_04: {}. sync locked, best quality'.format(STATbit05_04))
        elif STATbit05_04 == 0b01:
            print('STATbit05_04: {}. Unlocked for 10 s'.format(STATbit05_04))
        elif STATbit05_04 == 0b10:
            print('STATbit05_04: {}. Unlocked for 100 s'.format(STATbit05_04))
        elif STATbit05_04 == 0b11:
            print('STATbit05_04: {}. Unlocked for over 1000 s'.format(STATbit05_04))

        if STATbit03_00 == 0b0111:
            print('STATbit03_00: {}. Trigger reason: Digital'.format(STATbit03_00))
        elif STATbit03_00 == 0b0101:
            print('STATbit03_00: {}. Trigger reason: df/dt high'.format(STATbit03_00))
        elif STATbit03_00 == 0b0011:
            print('STATbit03_00: {}. Trigger reason: Phase-angle diff'.format(STATbit03_00))
        elif STATbit03_00 == 0b0001:
            print('STATbit03_00: {}. Trigger reason: Magnitude low'.format(STATbit03_00))
        elif STATbit03_00 == 0b0110:
            print('STATbit03_00: {}. Trigger reason NA: reserved bits'.format(STATbit03_00))
        elif STATbit03_00 == 0b100:
            print('STATbit03_00: {}. Trigger reason: Frequency high/low'.format(STATbit03_00))
        elif STATbit03_00 == 0b010:
            print('STATbit03_00: {}. Trigger reason: Magnitude high'.format(STATbit03_00))
        elif STATbit03_00 == 0b000:
            print('STATbit03_00: {}. Trigger reason: Manual'.format(STATbit03_00))
        elif STATbit03_00  > 0b1000 and STATbit03_00  <0b1111:
            print('STATbit03_00: {}. Trigger reason: user definition'.format(STATbit03_00))
        ###########################################################################
        for i in range(cfg2dict['PHNMR']):
            print('Phasor #{}: {}, {:0.2f}{} {:0.2f}°'.format(
                i+1,cfg2dict['PHASOR_names'][i],phasorMagnitude[i],
                    cfg2dict['PHUNIT_str'][i][0],phasorAngle[i]))

        for i,n in enumerate(cfg2dict['ANALOG_names']):
            print('Analog value #{}: {}, {:0.3f}'.format(
                i+1,n,round(ANALOGvalues[i],3)))
    return dictDATAread
