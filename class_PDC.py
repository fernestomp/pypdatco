# -*- coding: utf-8 -*-
import time
import math
import socket
from datetime import datetime
import struct
import warnings
import pandas as pd
from threading import Thread
from threading import Event
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import ThreadPoolExecutor

import multiprocessing

# to capture exceptions
import traceback

# own function
from get_crc16 import get_crc16


class PDC:
    def __init__(self, ip, port=4712, idcode=1):
        self.thread_pool_exec = ThreadPoolExecutor(8)
        self.dataframe_raw = None
        self.cfg2_raw = None
        self.event_stop_reading = Event()
        self.thd_read_dataframes = None
        self.dataframes_read = pd.DataFrame()
        self.process = None
        self.thd_read_dataframes = None
        self.dataFrame = None
        self.ip = ip
        self.port = port
        self.idcode = idcode
        self.buffersize = 2048
        self.PMUSocket = None
        self.frameTypeStr = None
        self.protocolVer = None
        self.frameSize = None
        self.timeQualitybits = None
        self.timeBase = None
        self.numPMU = None
        self.station = None
        self.formatFreqDfreq = None
        self.formatAnalog = None
        self.formatPhasor = None
        self.phasorNotation = None
        self.phasorNumber = None
        self.analogNumber = None
        self.digitalNumber = None
        self.phasorNames = None
        self.analogNames = None
        self.digitalLabels = None
        self.phasorUnit = None
        self.phasorUnitStr = None
        self.phasorUnitFactor = None
        self.analogUnit = None
        self.analogUnitFactor = None
        self.analogUnitValue = None
        self.digitalUnit = None
        self.freqNominal = None
        self.dataRate = None
        self.CHK = None
        self.dfCFG2 = None
        self.dfPMU_info = None
        self.isReading=False

    def __open_socket(self):
        self.PMUSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.PMUSocket.settimeout(5)
        self.PMUSocket.connect((self.ip, self.port))

    def __close_socket(self):
        self.PMUSocket.close()

    def __fill_pmu_info(self):
        # Create the dfPMU_info Dataframe
        num_pmus = self.dfCFG2[self.dfCFG2['field'] == 'NUM_PMU']['value'].values[0]
        lst_dict = []
        for pmu_num in range(1, num_pmus + 1):
            ph_names = self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_CHNAM_PHASORS'.format(pmu_num)]['value'].values[0]
            # spliting names
            lst_ph_names = [ph_names[i:i + 16] for i in range(0, len(ph_names), 16)]

            dict_PMU = {'PMU_NUM': 'PMU{}'.format(pmu_num)}

            stn_names = self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_STN'.format(pmu_num)]['value'].values[0]
            lst_stn_names = [stn_names[i:i + 16] for i in range(0, len(stn_names), 16)]
            for name in lst_stn_names:
                dict_PMU['STN'] = name

            dict_PMU['IDCODE'] = self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_IDCODE'.format(pmu_num)]['value'].values[0]

            dict_PMU['PHNMR'] = self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_PHNMR'.format(pmu_num)]['value'].values[0]
            dict_PMU['ANNMR'] = self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_ANNMR'.format(pmu_num)]['value'].values[0]
            dict_PMU['DGNMR'] = self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_DGNMR'.format(pmu_num)]['value'].values[0]
            fnom_code = self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_FNOM'.format(pmu_num)]['value'].values[0]
            # bit 0 is the only that matters
            if fnom_code & 1:
                dict_PMU['FREQ'] = 50
            else:
                dict_PMU['FREQ'] = 60
            dict_PMU['CFGCNT'] = self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_CFGCNT'.format(pmu_num)]['value'].values[0]
            dict_PMU['FORMAT_FREQ_DFREQ'] = \
                self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_FORMAT_FREQ_DFREQ'.format(pmu_num)]['value'].values[0]
            dict_PMU['FORMAT_ANALOG'] = \
                self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_FORMAT_ANALOG'.format(pmu_num)]['value'].values[0]

            dict_PMU['PHASOR_FORMAT'] = \
                self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_FORMAT_PHASOR'.format(pmu_num)]['value'].values[0]
            dict_PMU['PHASOR_NOTATION'] = \
                self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_PHASOR_NOTATION'.format(pmu_num)]['value'].values[0]
            for pn, name in enumerate(lst_ph_names, 1):
                dict_PMU['PHASOR{}_NAME'.format(pn)] = name
                dict_PMU['PHASOR{}_UNIT'.format(pn)] = \
                    self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_PHASOR{}_UNIT'.format(pmu_num, pn)]['value'].values[0]
                dict_PMU['PHASOR{}_CONV_FACTOR'.format(pn)] = \
                    self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_PHASOR{}_CONV_FACTOR'.format(pmu_num, pn)][
                        'value'].values[0]
            lst_dict.append(dict_PMU)

            self.dfPMU_info = pd.DataFrame.from_records(lst_dict)

    def connect(self):
        self.__open_socket()
        cfg2 = self.request_cfg2()
        self.decode_cfg2V2(cfg2)  # to populate the pmu configuration data
        self.__fill_pmu_info()

    def disconnect(self):
        self.__close_socket()

    def request_cfg2(self):
        SYNC_1 = 0xAA  # ACK
        SYNC_2 = 0x41
        FRAMESIZE_1 = 0x0
        FRAMESIZE_2 = 0x12
        [IDCODE_1, IDCODE_2] = int(self.idcode).to_bytes(2, 'big')
        PCtime = time.time()  # unix time
        [SOC_1, SOC_2, SOC_3, SOC_4] = int(PCtime).to_bytes(4, 'big')
        FRACSEC_1 = 0x00
        CMD_1 = 0X00
        CMD_2 = 0X05
        [FRACSEC_2, FRACSEC_3, FRACSEC_4] = int(str(round(math.fmod(PCtime, 1), 7))[2:]).to_bytes(3, 'big')
        msgNoCHK = [SYNC_1, SYNC_2, FRAMESIZE_1, FRAMESIZE_2, IDCODE_1, IDCODE_2, SOC_1, SOC_2, SOC_3, SOC_4, FRACSEC_1,
                    FRACSEC_2, FRACSEC_3, FRACSEC_4, CMD_1, CMD_2]
        [crcbyte1, crcbyte2, crc_16] = get_crc16(bytearray(msgNoCHK))
        message = msgNoCHK.copy()
        message.append(crcbyte1)
        message.append(crcbyte2)
        try:
            self.PMUSocket.sendall(bytearray(message))
        except Exception as e:  # work on python 3.x
            print(e)
            return
        self.cfg2_raw = self.PMUSocket.recv(self.buffersize)  # cfg2 received
        return self.cfg2_raw

    def decode_cfg2(self, cgf2frame, verbose=False):
        SYNCread = cgf2frame[0:2]
        leadingbyteSYNC = SYNCread[0]  # it should be 0xAA
        if not leadingbyteSYNC == 0xAA:
            warnings.warn("First byte is not 0xAA is {}".format(leadingbyteSYNC))

        secondbyteSYNC = SYNCread[1]

        frametypebits = (secondbyteSYNC & 112) >> 4  # 112 = 01110000b

        if frametypebits == 0:
            strframetype = 'Data Frame'

        elif frametypebits == 1:
            strframetype = 'Header Frame'

        elif frametypebits == 2:
            strframetype = 'Configuration frame 1'

        elif frametypebits == 3:
            strframetype = 'Configuration frame 2'

        elif frametypebits == 4:
            strframetype = 'Command frame'
        protocolversion = secondbyteSYNC & 15  # 00001111b = 15

        FRAMESIZEread = cgf2frame[2:4]

        decFRAMESIZE = int.from_bytes(FRAMESIZEread, 'big')

        IDCODEread = cgf2frame[4:6]
        decIDCODE = int.from_bytes(IDCODEread, 'big')

        SOCread = cgf2frame[6:10]
        # SOC en formato decimal, convertir 4 bytes a entero, big endian
        decSOC = int.from_bytes(SOCread, 'big')

        FRACSECread = cgf2frame[10:14]
        decFRACSEC = int.from_bytes(FRACSECread[1:4], 'big')
        # FRACSEC en formato decimal, convertir 4 bytes a entero, big endian
        TIME_QUALITY = FRACSECread[0]
        TQbit7 = TIME_QUALITY & 128  # reserved
        TQbit6 = TIME_QUALITY & 64  # leap second direction 0 for add, 1 for delete
        # Leap second ocurred. Set in the first second after the leap
        # second occurs and remains set for 24h.
        TQbit5 = TIME_QUALITY & 32
        # Leap second pending. Set before a leap second occurs and cleared
        # in the second anfter the leap second occurs.
        TQbit4 = TIME_QUALITY & 16
        TQbits3_0 = TIME_QUALITY & 15

        TIME_BASEread = cgf2frame[14:18]
        # TIME_BASE en formato decimal, convertir 4 bytes a entero, big endian
        decTIME_BASE = int.from_bytes(TIME_BASEread, 'big')

        NUM_PMUread = cgf2frame[18:20]
        decNUM_PMU = int.from_bytes(NUM_PMUread, 'big')

        STNread = cgf2frame[20:36]

        # idcode de donde vienen los datos
        IDCODESRCread = cgf2frame[36:38]
        decIDCODESRC = int.from_bytes(IDCODESRCread, 'big')

        FORMATread = cgf2frame[38:40]

        FRMTbit3 = (FORMATread[1] & 8) >> 3
        FRMTbit2 = (FORMATread[1] & 4) >> 2
        FRMTbit1 = (FORMATread[1] & 2) >> 1
        FRMTbit0 = (FORMATread[1] & 1)

        if FRMTbit3 == 0:
            FORMAT_FREQ_DFREQ = 'int'
        elif FRMTbit3 == 1:
            FORMAT_FREQ_DFREQ = 'float'

        if FRMTbit2 == 0:
            FORMAT_ANALOG = 'int'
        elif FRMTbit2 == 1:
            FORMAT_ANALOG = 'float'

        if FRMTbit1 == 0:
            FORMAT_PHASOR = 'int'
        elif FRMTbit1 == 1:
            FORMAT_PHASOR = 'float'

        if FRMTbit0 == 0:
            PHASOR_NOTATION = 'rectangular'
        elif FRMTbit0 == 1:
            PHASOR_NOTATION = 'polar'

        PHNMRread = cgf2frame[40:42]
        decPHNMR = int.from_bytes(PHNMRread, 'big')

        ANNMRread = cgf2frame[42:44]
        decANNMR = int.from_bytes(ANNMRread, 'big')

        DGNMRread = cgf2frame[44:46]
        decDGNMR = int.from_bytes(DGNMRread, 'big')

        nbytes_CHNAM = 16 * (decPHNMR + decANNMR + (16 * decDGNMR))
        CHNAMread = cgf2frame[46:46 + nbytes_CHNAM]
        # lista para hacer un slice de los nombres cada 16 bytes
        listslice = list(range(0, int(nbytes_CHNAM + 16), 16))
        listCHNAM = []
        for i in range(len(listslice) - 1):
            # lista completa de los nombres de los canales
            listCHNAM.append(CHNAMread[listslice[i]:listslice[i + 1]])
        # nombres de fasores
        # PHASORNAMES = [x.decode('utf-8') for x in listCHNAM[0:decPHNMR] ]
        PHASORNAMES = listCHNAM[0:decPHNMR]
        # nombre de valores analogicos
        ANALOGNAMES = listCHNAM[decPHNMR:decPHNMR + decANNMR]
        # ANALOGNAMES = [x.decode('utf-8') for x in listCHNAM[decPHNMR:decPHNMR+decANNMR] ]
        # digital status labels
        DIGITALLABELS = listCHNAM[decPHNMR + decANNMR:decPHNMR + decANNMR + decDGNMR * 16]

        numbytesPHUNIT = 4 * decPHNMR
        PHUNITbegintbyte = 46 + nbytes_CHNAM
        PHUNITendbyte = PHUNITbegintbyte + numbytesPHUNIT
        PHUNITread = cgf2frame[PHUNITbegintbyte:PHUNITendbyte]
        listslice = list(range(0, int(numbytesPHUNIT + 4), 4))  # 4 bytes en pasos de 4 bytes
        listPHUNIT = []
        for i in range(len(listslice) - 1):
            # lista completa los factores de conversion
            listPHUNIT.append(PHUNITread[listslice[i]:listslice[i + 1]])
        PHUNIT_str = []  # list of strings for PHUNIT (volt or ampere)
        PHUNIT_factor = []  # list of factors for PHUNIT
        # convirtiendo los valores a texto
        for i in range(len(listPHUNIT)):
            if listPHUNIT[i][0] == 0:
                PHUNIT_str.append('Volt')  # unit = 'Volt'
            elif listPHUNIT[i][0] == 1:
                PHUNIT_str.append('Ampere')  # unit = 'Ampere'
            PHUNIT_factor.append(int.from_bytes(listPHUNIT[i][1:4], 'big'))

        numbytesANUNIT = 4 * decANNMR
        ANUNITendbyte = PHUNITendbyte + numbytesPHUNIT
        ANUNITread = cgf2frame[PHUNITendbyte:ANUNITendbyte]
        listslice = list(range(0, int(numbytesANUNIT + 4), 4))  # 4 bytes en pasos de 4 bytes
        listANUNIT = []
        for i in range(len(listslice) - 1):
            # lista completa los factores de conversion
            listANUNIT.append(ANUNITread[listslice[i]:listslice[i + 1]])
        ANUNIT_factor = []  # list of factors decoded for ANUNIT
        ANUNIT_value = []  # list of values decoded for ANUNIT
        # convertir a texto
        for i in range(len(listANUNIT)):
            if listANUNIT[i][0] == 0:
                ANUNIT_factor.append('single point-on-wave')  # factor = 'single point-on-wave'
            elif listANUNIT[i][0] == 1:
                ANUNIT_factor.append('rms of analog input')  # factor = 'rms of analog input'
            elif listANUNIT[i][0] == 2:
                ANUNIT_factor.append('peak of analog input')  # factor = 'peak of analog input'
            ANUNIT_value.append(int.from_bytes(listANUNIT[i][1:4], 'big'))

        numbytesDIGUNIT = 4 * decDGNMR
        DIGUNITendbyte = ANUNITendbyte + numbytesDIGUNIT
        DIGUNITread = cgf2frame[ANUNITendbyte:DIGUNITendbyte]
        listslice = list(range(0, int(numbytesDIGUNIT + 4), 4))  # 4 bytes en pasos de 4 bytes
        listDIGUNIT = []
        for i in range(len(listslice) - 1):
            # lista completa los factores de conversion
            listDIGUNIT.append(DIGUNITread[listslice[i]:listslice[i + 1]])

        FNOMendbyte = DIGUNITendbyte + 2
        FNOMread = cgf2frame[DIGUNITendbyte:FNOMendbyte]

        FNOMbit0 = FNOMread[0] & 1
        if FNOMbit0 == 1:
            decFNOM = 50
        elif FNOMbit0 == 0:
            decFNOM = 60

        CFGCNTendbyte = FNOMendbyte + 2
        CFGCNTread = cgf2frame[FNOMendbyte:CFGCNTendbyte]
        decCFGCNT = int.from_bytes(CFGCNTread, 'big')

        DATA_RATEendbyte = CFGCNTendbyte + 2
        DATA_RATEread = cgf2frame[CFGCNTendbyte:DATA_RATEendbyte]
        decDATA_RATE = int.from_bytes(DATA_RATEread, 'big')
        assert decDATA_RATE != 0, 'DATA_RATE cannot be zero'

        CHKendbyte = DATA_RATEendbyte + 2
        CHKread = cgf2frame[DATA_RATEendbyte:CHKendbyte]
        decCHK = int.from_bytes(CHKread, 'big')

        # create a dict with all values
        dictDATAread = {'ACK': leadingbyteSYNC, 'frameType': frametypebits, 'frameTypeStr': strframetype,
                        'protocolVer': protocolversion, 'FRAMESIZE': decFRAMESIZE, 'IDCODE': decIDCODE, 'SOC': decSOC,
                        'FRACSEC': decFRACSEC, 'TIME_QUALITY': TIME_QUALITY, 'TIME_BASE': decTIME_BASE,
                        'NUM_PMU': decNUM_PMU, 'STN': STNread, 'IDCODEsrc': decIDCODESRC, 'FORMAT': FORMATread,
                        'FORMAT_freq_dfreq': FORMAT_FREQ_DFREQ, 'FORMAT_analog': FORMAT_ANALOG,
                        'FORMAT_phasor': FORMAT_PHASOR, 'PHASOR_notation': PHASOR_NOTATION, 'PHNMR': decPHNMR,
                        'ANNMR': decANNMR, 'DGNMR': decDGNMR, 'PHASOR_names': PHASORNAMES, 'ANALOG_names': ANALOGNAMES,
                        'DIGITAL_labels': DIGITALLABELS, 'PHUNIT': listPHUNIT, 'PHUNIT_str': PHUNIT_str,
                        'PHUNIT_factor': PHUNIT_factor, 'ANUNIT': listANUNIT, 'ANUNIT_factor': ANUNIT_factor,
                        'ANUNIT_value': ANUNIT_value, 'DIGUNIT': listDIGUNIT, 'FNOM': decFNOM, 'CFGNT': decCFGCNT,
                        'DATA_RATE': decDATA_RATE, 'CHK': decCHK}
        # class values
        self.frameTypeStr = strframetype
        self.protocolVer = protocolversion
        self.frameSize = decFRAMESIZE
        self.timeQualitybits = TIME_QUALITY
        self.timeBase = decTIME_BASE
        self.numPMU = decNUM_PMU
        self.station = STNread
        self.formatFreqDfreq = FORMAT_FREQ_DFREQ
        self.formatAnalog = FORMAT_ANALOG
        self.formatPhasor = FORMAT_PHASOR
        self.phasorNotation = PHASOR_NOTATION
        self.phasorNumber = decPHNMR
        self.analogNumber = decANNMR
        self.digitalNumber = decDGNMR
        self.phasorNames = PHASORNAMES
        self.analogNames = ANALOGNAMES
        self.digitalLabels = DIGITALLABELS
        self.phasorUnit = listPHUNIT
        self.phasorUnitStr = PHUNIT_str
        self.phasorUnitFactor = PHUNIT_factor
        self.analogUnit = listANUNIT
        self.analogUnitFactor = ANUNIT_factor
        self.analogUnitValue = ANUNIT_value
        self.digitalUnit = listDIGUNIT
        self.freqNominal = decFNOM
        self.dataRate = decDATA_RATE
        self.CHK = decCHK

        # print values (verbose=True)
        if verbose == True:
            print('------------------------------------------------------------------')
            print('SYNC byte: {}'.format(dictDATAread['ACK']))
            print('Dataframe type: {}'.format(dictDATAread['frameType']))
            print('Protocol version: {}'.format(dictDATAread['protocolVer']))
            print('Framesize: {}'.format(dictDATAread['FRAMESIZE']))
            print('IDCODE: {}'.format(dictDATAread['IDCODE']))
            print('SOC: {}'.format(dictDATAread['SOC']))
            print('FRACSEC: {}'.format(dictDATAread['FRACSEC']))
            # decode time quality bits
            if TQbit6 == 0:
                print('Leap second direction: False')
            elif TQbit6 == 1:
                print('Leap second direction: True')
            # probar que TQbit6 sea 0 o 1, si no manda un error
            assert TQbit6 <= 1, 'TQbit6 debe ser 0 o 1,no {}'.format(TQbit6)
            if TQbit5 == 0:
                print('Leap second ocurred: False')
            elif TQbit5 == 1:
                print('Leap second ocurred: True')
            # probar que TQbit5 sea 0 o 1, si no manda un error
            assert TQbit5 <= 1, 'TQbit5 debe ser 0 o 1,no {}'.format(TQbit5)
            if TQbit4 == 0:
                print('Leap second pending: False')
            elif TQbit4 == 1:
                print('Leap second pending: True')
            # probar que TQbit4 sea 0 o 1, si no manda un error
            assert TQbit4 <= 1, 'TQbit4 debe ser 0 o 1,no {}'.format(TQbit4)

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
            print('TIME_BASE: {}'.format(dictDATAread['TIME_BASE']))
            print('Number of PMUs: {}'.format(dictDATAread['NUM_PMU']))
            print('Station name: {}'.format(dictDATAread['STN']))
            print('Source IDCODE: {}'.format(dictDATAread['IDCODEsrc']))
            print('FREQ/DFREQ format: {}'.format(dictDATAread['FORMAT_freq_dfreq']))
            print('Analog values format: {}'.format(dictDATAread['FORMAT_analog']))
            print('Phasor format: {}'.format(dictDATAread['FORMAT_phasor']))
            print('Phasor notation: {}'.format(dictDATAread['PHASOR_notation']))
            print('Number of phasors: {}'.format(dictDATAread['PHNMR']))
            print('Number of analog values: {}'.format(dictDATAread['ANNMR']))
            print('Number of digital status words: {}'.format(dictDATAread['DGNMR']))
            print('Phasor names:')
            for i in dictDATAread['PHASOR_names']:
                print(i)
            print('Analog values:')
            for i in dictDATAread['ANALOG_names']:
                print(i)
            print('Digital status labels')
            for i in dictDATAread['DIGITAL_labels']:
                print(i)
            for i in range(len(dictDATAread['PHUNIT_str'])):
                print('#{} factor: {} * 10^-5, unit: {}'.format(i + 1, dictDATAread['PHUNIT_factor'][i],
                                                                dictDATAread['PHUNIT_str'][i]))
            for i in range(len(dictDATAread['ANUNIT_factor'])):
                print('Factor for analog value #{}: {}, value: {}'.format(i + 1, dictDATAread['ANUNIT_factor'][i],
                                                                          dictDATAread['ANUNIT_value'][i]))
            for i, w in enumerate(range(len(dictDATAread['DIGUNIT']))):
                print('Digital status word #{}: {}'.format(i + 1, dictDATAread['DIGUNIT'][i]))
            print('Nominal line frequency: {}'.format(dictDATAread['FNOM']))
            print('Configuration change count: {}'.format(dictDATAread['CFGNT']))
            if dictDATAread['DATA_RATE'] > 0:
                print('{} frame(s) per second'.format(dictDATAread['DATA_RATE']))
            elif dictDATAread['DATA_RATE'] < 0:
                print('1 frame per {} seconds'.format(dictDATAread['DATA_RATE']))
            print('CRC: {}'.format(hex(dictDATAread['CHK'])))
        return dictDATAread

    def decode_cfg2V2(self, cfg2frame, verbose=False):
        beginingByte = 0
        # filling dicts with cfg2 data
        fldvalue = cfg2frame[0:1]  # field value
        dictCFG2_SYNC = {'field': 'SYNC', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue, 'size': 1,
                         'begin': 0, 'end': 1}
        if not dictCFG2_SYNC['hex_val'] == bytes.fromhex('AA'):
            warnings.warn("First byte is not 0xAA is {}".format(dictCFG2_SYNC['hex_val']))

        fldvalue = cfg2frame[1:2]

        frametypebits = (int.from_bytes(fldvalue, 'big') & 112) >> 4  # 112 = 01110000b

        if frametypebits == 0:
            strframetype = 'Data Frame'

        elif frametypebits == 1:
            strframetype = 'Header Frame'

        elif frametypebits == 2:
            strframetype = 'Configuration frame 1'

        elif frametypebits == 3:
            strframetype = 'Configuration frame 2'

        elif frametypebits == 4:
            strframetype = 'Command frame'

        dictCFG2_FRAME_TYPE = {'field': 'FRAME_TYPE', 'value': strframetype,
                               'hex_val': int.to_bytes(frametypebits, length=1, byteorder='big', signed=False),
                               'size': 1, 'begin': 1, 'end': 2}
        protocolversion = int.from_bytes(fldvalue, 'big') & 15  # 00001111b = 15

        dictCFG2_PROTOCOL_VERSION = {'field': 'PROTOCOL_VERSION', 'value': protocolversion,
                                     'hex_val': int.to_bytes(protocolversion, length=1, byteorder='big', signed=False),
                                     'size': 1, 'begin': 1, 'end': 2}

        fldvalue = cfg2frame[2:4]
        dictCFG2_FRSIZE = {'field': 'FRAME_SIZE', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue,
                           'size': 2, 'begin': 2, 'end': 4}
        fldvalue = cfg2frame[4:6]
        dictCFG2_IDCODE_DC = {'field': 'IDCODE_DC', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue,
                              'size': 2, 'begin': 4, 'end': 6}
        fldvalue = cfg2frame[6:10]
        dictCFG2_SOC = {'field': 'SOC', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue, 'size': 4,
                        'begin': 6, 'end': 10}

        TIME_QUALITY = cfg2frame[10:11]
        decTIME_QUALITY = int.from_bytes(TIME_QUALITY, 'big')
        dictCFG2_TIME_QUALITY = {'field': 'TIME_QUALITY', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue,
                                 'size': 1, 'begin': 10, 'end': 11}

        TQbit7 = decTIME_QUALITY & 128  # reserved
        TQbit6 = decTIME_QUALITY & 64
        TQbit5 = decTIME_QUALITY & 32
        TQbit4 = decTIME_QUALITY & 16
        TQbits3_0 = decTIME_QUALITY & 15

        # decode time quality bits
        if TQbit6 == 0:
            leap_sec_dir_str = 'Leap second direction: add'
        elif TQbit6 == 1:
            leap_sec_dir_str = 'Leap second direction: delete'
        # probar que TQbit6 sea 0 o 1, si no manda un error
        assert TQbit6 <= 1, 'TQbit6 debe ser 0 o 1,no {}'.format(TQbit6)
        if TQbit5 == 0:
            leap_sec_ocur_str = 'Leap second ocurred: False'
        elif TQbit5 == 1:
            leap_sec_ocur_str = 'Leap second ocurred: True'
        # probar que TQbit5 sea 0 o 1, si no manda un error
        assert TQbit5 <= 1, 'TQbit5 debe ser 0 o 1,no {}'.format(TQbit5)
        if TQbit4 == 0:
            leap_sec_pending_str = 'Leap second pending: False'
        elif TQbit4 == 1:
            leap_sec_pending_str = 'Leap second pending: True'
        # probar que TQbit4 sea 0 o 1, si no manda un error
        assert TQbit4 <= 1, 'TQbit4 debe ser 0 o 1,no {}'.format(TQbit4)

        if TQbits3_0 == 15:
            tq_indicator_code_str = 'Fault-Clock failure, time not reliable.'
        if TQbits3_0 == 11:
            tq_indicator_code_str = 'Clock unlocked, time within 10 s.'
        if TQbits3_0 == 10:
            tq_indicator_code_str = 'Clock unlocked, time within 1 s.'
        if TQbits3_0 == 9:
            tq_indicator_code_str = 'Clock unlocked, time within 10E-1 s.'
        if TQbits3_0 == 8:
            tq_indicator_code_str = 'Clock unlocked, time within 10E-2 s.'
        if TQbits3_0 == 7:
            tq_indicator_code_str = 'Clock unlocked, time within 10E-3 s.'
        if TQbits3_0 == 6:
            tq_indicator_code_str = 'Clock unlocked, time within 10E-4 s.'
        if TQbits3_0 == 5:
            tq_indicator_code_str = 'Clock unlocked, time within 10E-5 s.'
        if TQbits3_0 == 4:
            tq_indicator_code_str = 'Clock unlocked, time within 10E-6 s.'
        if TQbits3_0 == 3:
            tq_indicator_code_str = 'Clock unlocked, time within 10E-7 s.'
        if TQbits3_0 == 2:
            tq_indicator_code_str = 'Clock unlocked, time within 10E-8 s.'
        if TQbits3_0 == 1:
            tq_indicator_code_str = 'Clock unlocked, time within 10E-9 s.'
        if TQbits3_0 == 0:
            tq_indicator_code_str = 'Normal operation, clock locked'

        dictCFG2_TIME_QUALITY_BIT_6 = {'field': 'TQ_BIT_6', 'value': leap_sec_dir_str,
                                       'hex_val': int.to_bytes(TQbit6, 1, 'big'), 'size': 1, 'begin': 10, 'end': 11}
        dictCFG2_TIME_QUALITY_BIT_5 = {'field': 'TQ_BIT_5', 'value': leap_sec_ocur_str,
                                       'hex_val': int.to_bytes(TQbit5, 1, 'big'), 'size': 1, 'begin': 10, 'end': 11}
        dictCFG2_TIME_QUALITY_BIT_4 = {'field': 'TQ_BIT_4', 'value': leap_sec_pending_str,
                                       'hex_val': int.to_bytes(TQbit4, 1, 'big'), 'size': 1, 'begin': 10, 'end': 11}
        dictCFG2_TIME_QUALITY_BIT_3_0 = {'field': 'TQ_IND_CODE', 'value': tq_indicator_code_str,
                                         'hex_val': int.to_bytes(TQbits3_0, 3, 'big'), 'size': 1, 'begin': 10,
                                         'end': 11}

        fracsec = cfg2frame[11:14]

        dictCFG2_FRACSEC = {'field': 'FRACSEC', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue,
                            'size': 3, 'begin': 11, 'end': 14}
        # =====================================================
        #               TIME BASE
        # =====================================================

        fldvalue = cfg2frame[14:18]
        dictCFG2_TIME_BASE = {'field': 'TIME_BASE', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue,
                              'size': 4, 'begin': 14, 'end': 18}
        fldvalue = cfg2frame[18:20]
        dictCFG2_NUM_PMU = {'field': 'NUM_PMU', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue,
                            'size': 2, 'begin': 18, 'end': 20}

        endingByte = dictCFG2_NUM_PMU['end']

        # begining of list to form a cfg2
        ldict = [dictCFG2_SYNC, dictCFG2_FRAME_TYPE, dictCFG2_PROTOCOL_VERSION, dictCFG2_FRSIZE, dictCFG2_IDCODE_DC,
                 dictCFG2_SOC, dictCFG2_FRACSEC, dictCFG2_TIME_QUALITY, dictCFG2_TIME_QUALITY_BIT_6,
                 dictCFG2_TIME_QUALITY_BIT_5, dictCFG2_TIME_QUALITY_BIT_4, dictCFG2_TIME_QUALITY_BIT_3_0,
                 dictCFG2_TIME_BASE, dictCFG2_NUM_PMU]
        # =====================================================
        #                       FOR LOOP
        # =====================================================
        ## repeat as many times as pmus in pmu/pdc
        for pmu_num in range(1, dictCFG2_NUM_PMU['value'] + 1):
        # =====================================================
        #                       STN
        # =====================================================
            beginingByte = endingByte
            endingByte = beginingByte + 16
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_STN = {'field': 'PMU{}_STN'.format(pmu_num), 'value': fldvalue.decode(), 'hex_val': fldvalue,
                            'size': endingByte - beginingByte, 'begin': beginingByte, 'end': endingByte}
            
            # =====================================================
            #                       IDCODE
            # =====================================================
            beginingByte = dictCFG2_STN['end']
            endingByte = beginingByte + 2
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_IDCODE_PMU = {'field': 'PMU{}_IDCODE'.format(pmu_num), 'value': int.from_bytes(fldvalue, 'big'),
                                   'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                                   'end': endingByte}
            # =====================================================
            #                      FORMAT
            # =====================================================
            beginingByte = endingByte
            endingByte = beginingByte + 2
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_FORMAT = {'field': 'PMU{}_FORMAT'.format(pmu_num), 'value': int.from_bytes(fldvalue, 'big'),
                               'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                               'end': endingByte}
            FORMATBytes_dec = dictCFG2_FORMAT['hex_val'][1]
            FRMTbit3 = (FORMATBytes_dec & 8) >> 3
            FRMTbit2 = (FORMATBytes_dec & 4) >> 2
            FRMTbit1 = (FORMATBytes_dec & 2) >> 1
            FRMTbit0 = (FORMATBytes_dec & 1)

            if FRMTbit3 == 0:
                FORMAT_FREQ_DFREQ = 'int'
            elif FRMTbit3 == 1:
                FORMAT_FREQ_DFREQ = 'float'

            if FRMTbit2 == 0:
                FORMAT_ANALOG = 'int'
            elif FRMTbit2 == 1:
                FORMAT_ANALOG = 'float'

            if FRMTbit1 == 0:
                FORMAT_PHASOR = 'int'
            elif FRMTbit1 == 1:
                FORMAT_PHASOR = 'float'

            if FRMTbit0 == 0:
                PHASOR_NOTATION = 'rectangular'
            elif FRMTbit0 == 1:
                PHASOR_NOTATION = 'polar'

            dictCFG2_FORMAT_BIT_3 = {'field': 'PMU{}_FORMAT_FREQ_DFREQ'.format(pmu_num), 'value': FORMAT_FREQ_DFREQ,
                                     'hex_val': int.to_bytes(FRMTbit3, 1, 'big'), 'size': endingByte - beginingByte,
                                     'begin': beginingByte, 'end': endingByte}

            dictCFG2_FORMAT_BIT_2 = {'field': 'PMU{}_FORMAT_ANALOG'.format(pmu_num), 'value': FORMAT_ANALOG,
                                     'hex_val': int.to_bytes(FRMTbit2, 1, 'big'), 'size': endingByte - beginingByte,
                                     'begin': beginingByte, 'end': endingByte}
            dictCFG2_FORMAT_BIT_1 = {'field': 'PMU{}_FORMAT_PHASOR'.format(pmu_num), 'value': FORMAT_PHASOR,
                                     'hex_val': int.to_bytes(FRMTbit1, 1, 'big'), 'size': endingByte - beginingByte,
                                     'begin': beginingByte, 'end': endingByte}

            dictCFG2_FORMAT_BIT_0 = {'field': 'PMU{}_PHASOR_NOTATION'.format(pmu_num), 'value': PHASOR_NOTATION,
                                     'hex_val': int.to_bytes(FRMTbit3, 1, 'big'), 'size': endingByte - beginingByte,
                                     'begin': beginingByte, 'end': endingByte}

            beginingByte = endingByte
            endingByte = beginingByte + 2
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_PHNMR = {'field': 'PMU{}_PHNMR'.format(pmu_num), 'value': int.from_bytes(fldvalue, 'big'),
                              'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                              'end': endingByte}

            beginingByte = endingByte
            endingByte = beginingByte + 2
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_ANNMR = {'field': 'PMU{}_ANNMR'.format(pmu_num), 'value': int.from_bytes(fldvalue, 'big'),
                              'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                              'end': endingByte}

            beginingByte = endingByte
            endingByte = beginingByte + 2
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_DGNMR = {'field': 'PMU{}_DGNMR'.format(pmu_num), 'value': int.from_bytes(fldvalue, 'big'),
                              'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                              'end': endingByte}
            # ========================================================
            #                       CHNAM
            # ========================================================
            # need cfg2 data to know how many bytes.....
            beginingByte = endingByte
            endingByte = beginingByte + 16 * (
                    dictCFG2_PHNMR['value'] + dictCFG2_ANNMR['value'] + (16 * dictCFG2_DGNMR['value']))
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_CHNAM = {'field': 'PMU{}_CHNAM'.format(pmu_num), 'value': fldvalue.decode(), 'hex_val': fldvalue,
                              'size': endingByte - beginingByte, 'begin': beginingByte, 'end': endingByte}

            CHNAM = dictCFG2_CHNAM['value']  # all channels together
            # list of chnames. 16 bytes per channel name

            number_of_phasors = dictCFG2_PHNMR['value']
            number_of_analogs = dictCFG2_ANNMR['value']
            number_of_digitals = dictCFG2_DGNMR['value']
            beginingByte = dictCFG2_CHNAM['end']
            endingByte = beginingByte + (16 * pmu_num)
            dictCFG2_CHNAM_PHASORS = {'field': 'PMU{}_CHNAM_PHASORS'.format(pmu_num),
                                      'value': fldvalue[0:endingByte].decode(), 'hex_val': fldvalue[0:endingByte],
                                      'size': endingByte - beginingByte, 'begin': beginingByte, 'end': endingByte}

            lstCHNAM = [dictCFG2_CHNAM_PHASORS]
            a = number_of_phasors
            b = number_of_phasors + number_of_analogs
            if number_of_analogs > 0:
                beginingByte = dictCFG2_CHNAM_PHASORS['end']
                endingByte = beginingByte + dictCFG2_ANNMR['value'] * 16
                dictCFG2_CHNAM_ANALOGS = {'field': 'PMU{}_CHNAM_ANALOGS'.format(pmu_num), 'value': fldvalue[a:b],
                                          'hex_val': fldvalue[a:b], 'size': endingByte - beginingByte,
                                          'begin': beginingByte, 'end': endingByte}
                lstCHNAM.append(dictCFG2_CHNAM_ANALOGS)
            if number_of_digitals > 0:
                a = b
                beginingByte = dictCFG2_CHNAM_PHASORS['end']
                endingByte = beginingByte + dictCFG2_DGNMR['value'] * 16
                dictCFG2_CHNAM_DIGITALS = {'field': 'PMU{}_CHNAM_DIGITALS'.format(pmu_num), 'value': fldvalue[a:],
                                           'hex_val': fldvalue[a:], 'size': endingByte - beginingByte,
                                           'begin': beginingByte, 'end': endingByte}
                lstCHNAM.append(dictCFG2_CHNAM_DIGITALS)
            # ===================================================================
            #                           PHUNIT
            # ===================================================================
            beginingByte = dictCFG2_CHNAM['end']
            endingByte = beginingByte + (4 * dictCFG2_PHNMR['value'])
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_PHUNIT_DATA = {'field': 'PMU{}_PHUNIT_DATA'.format(pmu_num),
                                    'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue,
                                    'size': endingByte - beginingByte, 'begin': beginingByte, 'end': endingByte}
            lstPHUNIT = []  # d list of dicts
            PHUNIT = dictCFG2_PHUNIT_DATA['hex_val']
            # list of phunit data (no dicts)
            lst_phunit_split = [PHUNIT[i:i + 4] for i in range(0, len(PHUNIT), 4)]
            beginingByte = dictCFG2_PHUNIT_DATA['end']
            for pn, u in enumerate(lst_phunit_split, 1):
                endingByte = beginingByte + 1
                unit_v_a = None
                if u[0] == 0:
                    unit_v_a = 'volt'
                if u[0] == 1:
                    unit_v_a = 'amp'
                dictCFG2_PHUNIT_UNIT = {'field': 'PMU{}_PHASOR{}_UNIT'.format(pmu_num, pn), 'value': unit_v_a,
                                        'hex_val': u[0], 'size': endingByte - beginingByte, 'begin': beginingByte,
                                        'end': endingByte}
                lstPHUNIT.append(dictCFG2_PHUNIT_UNIT)
                beginingByte = endingByte
                endingByte = beginingByte + 3
                dictCFG2_PHUNIT_CONV_FACTOR = {'field': 'PMU{}_PHASOR{}_CONV_FACTOR'.format(pmu_num, pn),
                                               'value': int.from_bytes(u[1:], 'big', signed=False), 'hex_val': u[1:],
                                               'size': endingByte - beginingByte, 'begin': beginingByte,
                                               'end': endingByte}
                beginingByte = endingByte
                lstPHUNIT.append(dictCFG2_PHUNIT_CONV_FACTOR)
            # ------------------------------------------------------------
            beginingByte = dictCFG2_PHUNIT_DATA['end']
            endingByte = beginingByte + 4 * dictCFG2_ANNMR['value']
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_ANUNIT = {'field': 'PMU{}_ANUNIT'.format(pmu_num), 'value': int.from_bytes(fldvalue, 'big'),
                               'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                               'end': endingByte}
            # ============================================================
            #                           ANUNIT
            # ============================================================
            lstANUNIT = []
            if number_of_analogs > 0:
                # hex bytes to binary string
                num_of_bits = 32
                ANUNIT_bits = bin(int(dictCFG2_ANUNIT['hex_value'], 16))[2:].zfill(num_of_bits)
                cf_string_bits = int(ANUNIT_bits[0:2])
                if cf_string_bits == 0:
                    cf_string = 'single point-on-wave'
                elif cf_string_bits == 1:
                    cf_string = 'rms of analog input'
                elif cf_string_bits == 2:
                    cf_string = 'peak of analog input'

                dictCFG2_ANUNIT_STRING = {'field': 'PMU{}_CONV_FACTOR_STR'.format(pmu_num), 'value': cf_string,
                                          'hex_val': int.to_bytes(cf_string_bits, 1, 'big'),
                                          'size': endingByte - beginingByte, 'begin': beginingByte, 'end': endingByte}
                lstANUNIT.append(dictCFG2_ANUNIT_STRING)
                cf_user_def = ANUNIT_bits[7:]
                dictCFG2_ANUNIT_USER_DEFINED = {'field': 'PMU{}_USER_DEFINED'.format(pmu_num), 'value': cf_user_def,
                                                'hex_val': int.to_bytes(cf_user_def, 1, 'big'),
                                                'size': endingByte - beginingByte, 'begin': beginingByte,
                                                'end': endingByte}
                lstANUNIT.append(dictCFG2_ANUNIT_USER_DEFINED)

                cf = dictCFG2_ANUNIT['hex_val'][1:]
                dictCFG2_ANUNIT_CF = {'field': 'PMU{}_CONVERSION_FACTOR'.format(pmu_num),
                                      'value': int.from_bytes(cf, 'big'), 'hex_val': cf,
                                      'size': endingByte - beginingByte, 'begin': beginingByte, 'end': endingByte}
                lstANUNIT.append(dictCFG2_ANUNIT_CF)

            # ============================================================
            #                        DIGUNIT
            # ============================================================
            beginingByte = dictCFG2_ANUNIT['end']
            endingByte = beginingByte + 4 * dictCFG2_DGNMR['value']
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_DIGUNIT = {'field': 'PMU{}_DIGUNIT'.format(pmu_num), 'value': int.from_bytes(fldvalue, 'big'),
                                'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                                'end': endingByte}
            # ============================================================
            #                        FNOM
            # ============================================================
            beginingByte = dictCFG2_DIGUNIT['end']
            endingByte = beginingByte + 2
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_FNOM = {'field': 'PMU{}_FNOM'.format(pmu_num), 'value': int.from_bytes(fldvalue, 'big'),
                             'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                             'end': endingByte}
            # ============================================================
            #                       CFGCNT
            # ============================================================
            beginingByte = dictCFG2_FNOM['end']
            endingByte = beginingByte + 2
            fldvalue = cfg2frame[beginingByte:endingByte]
            dictCFG2_CFGCNT = {'field': 'PMU{}_CFGCNT'.format(pmu_num), 'value': int.from_bytes(fldvalue, 'big'),
                               'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                               'end': endingByte}
            beginingByte = dictCFG2_CFGCNT['end']

            # adding phasor to list that conforms cfg2
            ldict.extend(
                [dictCFG2_STN, dictCFG2_IDCODE_PMU, dictCFG2_FORMAT, dictCFG2_FORMAT_BIT_3, dictCFG2_FORMAT_BIT_2,
                 dictCFG2_FORMAT_BIT_1, dictCFG2_FORMAT_BIT_0, dictCFG2_PHNMR, dictCFG2_ANNMR, dictCFG2_DGNMR,
                 dictCFG2_CHNAM])
            ldict.extend(lstCHNAM)
            ldict.append(dictCFG2_PHUNIT_DATA)
            ldict.extend(lstPHUNIT)
            ldict.append(dictCFG2_ANUNIT)
            ldict.extend(lstANUNIT)
            ldict.extend([dictCFG2_DIGUNIT, dictCFG2_FNOM, dictCFG2_CFGCNT])

            ldict.extend(lstANUNIT)

        # end for
        # ============================================================
        #                       DATA_RATE
        # ============================================================
        endingByte = beginingByte + 2
        fldvalue = cfg2frame[beginingByte:endingByte]
        dictCFG2_DATA_RATE = {'field': 'DATA_RATE', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue,
                              'size': endingByte - beginingByte, 'begin': beginingByte, 'end': endingByte}
        # ============================================================
        #                       CHK
        # ============================================================
        beginingByte = dictCFG2_DATA_RATE['end']
        endingByte = beginingByte + 2
        fldvalue = cfg2frame[beginingByte:endingByte]
        dictCFG2_CHK = {'field': 'CHK'.format(pmu_num), 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue,
                        'size': endingByte - beginingByte, 'begin': beginingByte, 'end': endingByte}
        ldict.append(dictCFG2_CHK)
        ldict.append(dictCFG2_DATA_RATE)

        dfCFG2 = pd.DataFrame.from_records(ldict)

        # class values
        self.frameTypeStr = dfCFG2.iloc[1]['value']
        self.protocolVer = dfCFG2.iloc[2]['value']
        self.frameSize = dfCFG2.iloc[3]['value']
        self.timeQualitybits = dfCFG2.iloc[7]['value']
        self.timeBase = dfCFG2.iloc[12]['value']
        self.numPMU = dfCFG2.iloc[13]['value']
        self.station = dfCFG2[dfCFG2['field'].str.contains('STN')]['value']
        self.formatFreqDfreq = dfCFG2[dfCFG2['field'].str.contains('FORMAT_FREQ')]['value']
        self.formatAnalog = dfCFG2[dfCFG2['field'].str.contains('FORMAT_ANALOG')]['value']
        self.formatPhasor = dfCFG2[dfCFG2['field'].str.contains('FORMAT_PHASOR')]['value']
        self.phasorNotation = dfCFG2[dfCFG2['field'].str.contains('PHASOR_NOTATION')]['value']
        self.phasorNumber = dfCFG2[dfCFG2['field'].str.contains('PHNMR')]['value']
        self.analogNumber = dfCFG2[dfCFG2['field'].str.contains('ANNMR')]['value']
        self.digitalNumber = dfCFG2[dfCFG2['field'].str.contains('DGNMR')]['value']
        self.phasorNames = dfCFG2[dfCFG2['field'].str.contains('CHNAME_PHASORS')]['value']
        for i in range(1, dfCFG2[dfCFG2['field'] == 'NUM_PMU']['value'].values[0]):
            if dfCFG2[dfCFG2['field'] == 'PMU{}_ANNMR'.format(i)]['value'].values[0] > 0:
                self.analogNames = dfCFG2[dfCFG2['field'].str.contains('CHNAME_ANALOGS')]['value']
                self.analogUnitFactor = dfCFG2[dfCFG2['field'].str.contains('CONV_FACTOR_STR')]['value']
                self.analogUnitValue = dfCFG2[dfCFG2['field'].str.contains('CONVERSION_FACTOR')]['value']
            if dfCFG2[dfCFG2['field'] == 'PMU{}_DGNMR'.format(i)]['value'].values[0] > 0:
                self.digitalLabels = dfCFG2[dfCFG2['field'].str.contains('CHNAME_DIGITALS')]['value']
        self.phasorUnit = dfCFG2[dfCFG2['field'].str.contains('UNIT_DATA')]['value']
        self.phasorUnitStr = dfCFG2[dfCFG2['field'].str.contains('UNIT')]['value']
        self.phasorUnitFactor = dfCFG2[dfCFG2['field'].str.contains('CONVERSION_FACTOR')]['value']
        self.analogUnit = dfCFG2[dfCFG2['field'].str.contains('ANUNIT')]['value']
        self.digitalUnit = dfCFG2[dfCFG2['field'].str.contains('DIGUNIT')]['value']
        self.freqNominal = dfCFG2[dfCFG2['field'].str.contains('FNOM')]['value']
        self.dataRate = dfCFG2[dfCFG2['field'].str.contains('DATA_RATE')]['value']
        self.CHK = dfCFG2[dfCFG2['field'].str.contains('CHK')]['value']

        # print values (verbose=True)
        if verbose == True:
            print('------------------------------------------------------------------')
            print('SYNC byte: {}'.format(dfCFG2[dfCFG2['field'].str.contains('SYNC')]['value']))
            print('Dataframe type: {}'.format(self.frameTypeStr))
            print('Protocol version: {}'.format(self.protocolVer))
            print('Framesize: {}'.format(self.frameSize))
            print('IDCODE: {}'.format(self.idcode))
            print('SOC: {}'.format(dfCFG2[dfCFG2['field'].str.contains('SOC')]['value']))
            print('FRACSEC: {}'.format(dfCFG2[dfCFG2['field'].str.contains('FRACSEC')]['value']))
            # decode time quality bits
            print('TIME_BASE: {}'.format(self.timeBase))
            print('Number of PMUs: {}'.format(self.numPMU))
            for i in range(self.phasorNumber):
                print('Station name: {}'.format(dfCFG2[dfCFG2['field'] == 'STN_{}'.format(i + 1)]['value']))
                print('Source IDCODE: {}'.format(dfCFG2[dfCFG2['field'] == 'IDCODE_PMU_{}'.format(i + 1)]['value']))
                print('PHASOR format: {}'.format(dfCFG2[dfCFG2['field'] == 'FORMAT_PHASOR_{}'.format(i + 1)]['value']))
                print('FREQ/DFREQ format: {}'.format(
                    dfCFG2[dfCFG2['field'] == 'FORMAT_FREQ_DFREQ_{}'.format(i + 1)]['value']))
                print('Analog values format: {}'.format(
                    dfCFG2[dfCFG2['field'] == 'FORMAT_ANALOG_{}'.format(i + 1)]['value']))
                print(
                    'Phasor notation: {}'.format(dfCFG2[dfCFG2['field'] == 'PHASOR_NOTATION{}'.format(i + 1)]['value']))

            if self.dataRate > 0:
                print('{} frame(s) per second'.format(self.dataRate))
            elif self.dataRate < 0:
                print('1 frame per {} seconds'.format(self.dataRate))
            print('CRC: {}'.format(self.CHK))
            print('tot bytes {} ending byte {}'.format(len(cfg2frame), endingByte))
        self.dfCFG2 = dfCFG2
        return dfCFG2

    def send_command(self, cmd):
        '''
        Function to send a predefined set of commands to the PMU.

        Parameters
        ----------
        sockobj: socket
            Socket stream where the command will be sent. The Socket
            should have been opened before, and it should be connected to
            the PMU.

        idcode: int
            IDCODE of the PMU.

        cmd: str or int
            Command to be sent to the PMU.
        '''
        # 1 field SYNC
        field1_1 = 170  # AA.
        field1_2 = 65  # 0-reservado100-data frame comando0001-2005
        # 2 FRAMESIZE
        # it's always 18 because im not using the EXTFRAME data (table 12-command frame configuration)
        field2_1 = 0
        field2_2 = 18
        # 3 field IDCODE
        # dividir en dos bytes y hacer un bitshift 8 lugares a la derecha
        [field3_1, field3_2] = int(self.idcode).to_bytes(2, 'big')
        # 4 SOC
        # send unix time
        PCtime = time.time()
        t = int(PCtime).to_bytes(4, 'big')
        field4_1 = t[0]
        field4_2 = t[1]
        field4_3 = t[2]
        field4_4 = t[3]
        # 5 FRACSEC
        # fmod:get fractional part,
        # round: to convert fractional part to 3 bytes (precision is lost)
        # str:to do slicing and remove "0." part
        # int to_bytes: list of 3 bytes of the fractional part
        fsec = int(str(round(math.fmod(PCtime, 1), 7))[2:]).to_bytes(3, 'big')
        field5_1 = 0  # time quality flags, ignore leap seconds
        field5_2 = fsec[0]
        field5_3 = fsec[1]
        field5_4 = fsec[2]
        # 6 CMD
        field6_1 = 0  # first byte is zero
        # check if the command is the number representation
        # or a string Command
        if isinstance(cmd, (int, float, complex)) and not isinstance(cmd, bool):
            field6_2 = int(cmd)
        else:
            if cmd == 'stop':
                field6_2 = 0b0001
            elif cmd == 'start':
                field6_2 = 0b0010
            elif cmd == 'sendHDR':
                field6_2 = 0b0011
            elif cmd == 'sendCFG1':
                field6_2 = 0b0100
            elif cmd == 'sendCFG2':
                field6_2 = 0b0101
            elif cmd == 'extended':
                print('Extended frame not implemented.')
                return
        # 7 EXTFRAME no se usa
        # 8 CHK
        # mensajae sin CHK
        messnoCHK = [field1_1, field1_2, field2_1, field2_2, field3_1, field3_2, field4_1, field4_2, field4_3, field4_4,
                     field5_1, field5_2, field5_3, field5_4, field6_1, field6_2]

        [crcbyte1, crcbyte2, crc_16] = get_crc16(bytearray(messnoCHK));
        message = messnoCHK.copy()
        message.append(crcbyte1)
        message.append(crcbyte2)
        message_bytearr = bytearray(message)
        self.PMUSocket.send(message_bytearr)

    def read_dataframe_raw(self):
        '''
        Function to read the dataframe from the PMU. This function should be
        used for continuous data monitoring.

        Parameters
        ----------
        sockobj: socket
            Socket stream where the dataframe will come from. The Socket
            should have been opened before, and it should be connected to
            the PMU.

        buffersize: int
            Number of bytes that will be received from the socket stream.

        Returns
        -------
        bytearray
            Dataframe read from the PMU in byte array format
        '''
        # read  measurements
        # this code is not optimal, n frames per second are expected
        # is only for testing purposes, data could be lost or superimposed
        # ask for n dataframes

        # can only recieve buffersize bytes
        # maybe i should use a function that can get me
        # the numbers of bytes before using the recv function
        self.send_command('start')

        self.dataframe_raw = self.PMUSocket.recv(self.buffersize)
        data = self.dataframe_raw
        #print(data[:1].hex())

        if data[:1].hex() == 'aa':
            # get the framesize
            framesizebytes = data[2:4]
            framesize = int.from_bytes(framesizebytes, 'big')
            # the dataframes could be superimposed, so i get the framesize and
            # divide the data into n framesize strings
            # split data in chunks of framsize
            if len(data) > framesize:
                datachunks = [data[i:i + framesize] for i in range(0, len(data), framesize)]
                for d in datachunks:
                    # print('Framesize: {}, length of dataframe: {}'.format(framesize,len(d)))
                    # print(d)
                    #:-2 porque los ultimos bytes son el numero crc
                    [_, _, crccalc] = get_crc16(d[:-2])
                    crcsrc = int.from_bytes(d[-2:], 'big')
                    if crccalc == crcsrc:
                        return d, True

                    else:
                        return data, False

            else:  # no superimposed dataframes
                #:-2 porque los ultimos bytes son el numero crc
                [_, _, crccalc] = get_crc16(data[:-2])
                crcsrc = int.from_bytes(data[-2:], 'big')
                if crccalc == crcsrc:
                    # print('CRC Ok!')
                    return data, True
                else:
                    return data, False

    def decode_dataframe(self, data, verbose=False):
        '''
        Function to decode the dataframe.

        Parameters
        ----------
        data: bytearray
            data frame 2 to decode.

        verbose: bool
            If true, it will print the decoded data.

        Returns
        -------
        dict
            Dictionary with the decoded data.
        '''
        #####################################################
        # 1 field SYNC
        cfg2dict = 0
        field1_1 = data[0]  # it has to be 0xAA
        if field1_1 != 0xAA:
            print('Transmission error: SYNC byte is {}'.format(field1_1.hex()))
        field1_2 = data[1]  # version number
        ACKread = field1_1
        DATAFRAMETYPEread = field1_2 & 0b01110000  # bits 6-4
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

        VERread = field1_2 & 0b00001111
        #######################################################
        # 2 FRAMESIZE
        # it's always 18 because im not using the EXTFRAME data (table 12-command frame configuration)
        [field2_1, field2_2] = data[2:4]
        FRAMESIZEread = int.from_bytes([field2_1, field2_2], 'big')
        #######################################################
        # 3 field IDCODE
        # dividir en dos bytes y hacer un bitshift 8 lugares a la derecha
        [field3_1, field3_2] = data[4:6]
        IDCODEread = int.from_bytes([field3_1, field3_2], 'big')
        #######################################################
        # 4 SOC
        [field4_1, field4_2, field4_3, field4_4] = data[6:10]
        SOCread = int.from_bytes([field4_1, field4_2, field4_3, field4_4], 'big')
        #######################################################
        # 5 FRACSEC
        [field5_1, field5_2, field5_3, field5_4] = data[10:14]
        FRACSECread = int.from_bytes([field5_2, field5_3, field5_4], 'big')

        TIME_QUALITY = field5_1
        TQbit7 = TIME_QUALITY & 128  # reserved
        TQbit6 = TIME_QUALITY & 64  # leap second direction 0 for add, 1 for delete
        # Leap second ocurred. Set in the first second after the leap
        # second occurs and remains set for 24h.
        TQbit5 = TIME_QUALITY & 32
        # Leap second pending. Set before a leap second occurs and cleared
        # in the second anfter the leap second occurs.
        TQbit4 = TIME_QUALITY & 16
        TQbits3_0 = TIME_QUALITY & 15

        TIME_POSIX = SOCread + (FRACSECread / self.timeBase);
        # from unix timestamp to human readable time
        TIMEread = datetime.utcfromtimestamp(TIME_POSIX).strftime('%Y-%m-%d %H:%M:%S.%f')
        ########################################################
        # 6 STAT
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
            # print('STATbit15: {}. Data is valid.'.format(STATbit15))
            STAT_VALID_DATA = True
        elif STATbit15 == 1:
            # print('STATbit15: {}. Data is not valid or PMU is in test mode'.format(
            #    STATbit15))
            STAT_VALID_DATA = False

        if STATbit14 == 0:
            # print('STATbit14: {}. PMU error: No error'.format(STATbit14))
            STAT_PMU_ERROR = False
        elif STATbit14 == 1:
            # print('STATbit14: {}. PMU error: Error'.format(STATbit14))
            STAT_PMU_ERROR = True

        if STATbit13 == 0:
            # print('STATbit13: {}. Time synchronized: Sync'.format(STATbit13))
            STAT_TIME_SYNC = True
        elif STATbit13 == 1:
            STAT_TIME_SYNC = False  # print('STATbit13: {}. Time synchronized: Time synchronization lost'.format(STATbit13))

        if STATbit12 == 0:
            # print('STATbit12: {}. Data sorting: by timestamp'.format(STATbit12))
            STAT_DATA_SORTING = 'timestamp'
        elif STATbit12 == 1:
            # print('STATbit12: {}. Data sorting: by arrival'.format(STATbit12))
            STAT_DATA_SORTING = 'arrival'

        if STATbit11 == 0:
            # print('STATbit11: {}. Trigger detected: No Trigger'.format(STATbit11))
            STAT_TRIGGER_DETECTED = False
        elif STATbit11 == 1:
            # print('STATbit11: {}. Trigger detected: Yes'.format(STATbit11))
            STAT_TRIGGER_DETECTED = True

        if STATbit10 == 0:
            # print('STATbit10: {}. Configuration changed: No'.format(STATbit10))
            STAT_CONFIG_CHANGED = False
        elif STATbit10 == 1:
            # print('STATbit10: {}. Configuration changed: Yes'.format(STATbit10))
            STAT_CONFIG_CHANGED = True

        if STATbit05_04 == 0b00:
            # print('STATbit05_04: {}. sync locked, best quality'.format(STATbit05_04))
            STAT_UNLOCKED_TIME = 'sync_locked'
        elif STATbit05_04 == 0b01:
            # print('STATbit05_04: {}. Unlocked for 10 s'.format(STATbit05_04))
            STAT_UNLOCKED_TIME = 'unlocked_10'
        elif STATbit05_04 == 0b10:
            # print('STATbit05_04: {}. Unlocked for 100 s'.format(STATbit05_04))
            STAT_UNLOCKED_TIME = 'unlocked_100'
        elif STATbit05_04 == 0b11:
            # print('STATbit05_04: {}. Unlocked for over 1000 s'.format(STATbit05_04))
            STAT_UNLOCKED_TIME = 'unlocked_1000'

        if STATbit03_00 == 0b0111:
            STAT_TRIGGER_REASON = 'digital'  # print('STATbit03_00: {}. Trigger reason: Digital'.format(STATbit03_00))
        elif STATbit03_00 == 0b0101:
            # print('STATbit03_00: {}. Trigger reason: df/dt high'.format(STATbit03_00))
            STAT_TRIGGER_REASON = 'dfdt_high'
        elif STATbit03_00 == 0b0011:
            # print('STATbit03_00: {}. Trigger reason: Phase-angle diff'.format(STATbit03_00))
            STAT_TRIGGER_REASON = 'phangle_diff'
        elif STATbit03_00 == 0b0001:
            #    print('STATbit03_00: {}. Trigger reason: Magnitude low'.format(STATbit03_00))
            STAT_TRIGGER_REASON = 'magnitude_low'
        elif STATbit03_00 == 0b0110:
            # print('STATbit03_00: {}. Trigger reason NA: reserved bits'.format(STATbit03_00))
            STAT_TRIGGER_REASON = 'reserved_bits'
        elif STATbit03_00 == 0b100:
            # print('STATbit03_00: {}. Trigger reason: Frequency high/low'.format(STATbit03_00))
            STAT_TRIGGER_REASON = 'freq_high_low'
        elif STATbit03_00 == 0b010:
            # print('STATbit03_00: {}. Trigger reason: Magnitude high'.format(STATbit03_00))
            STAT_TRIGGER_REASON = 'magnitude_high'
        elif STATbit03_00 == 0b000:
            #    print('STATbit03_00: {}. Trigger reason: Manual'.format(STATbit03_00))
            STAT_TRIGGER_REASON = 'manual'
        elif STATbit03_00 > 0b1000 and STATbit03_00 < 0b1111:
            # print('STATbit03_00: {}. Trigger reason: user definition'.format(STATbit03_00))
            STAT_TRIGGER_REASON = 'user'
        ##############################################
        # PHASORS
        # float type: 8 bytes
        if self.formatPhasor == 'float':
            nbytes = 8
            phEndbyte = 16 + (nbytes * self.phasorNumber)
            phasors = data[16:phEndbyte]
            phasorMagnitude = []
            phasorAngle = []
            if self.phasorNotation == 'polar':
                # first 4 bytes are the magnitude, next four bytes are the angle (i+4:i+8)
                for i in range(0, (self.phasorNumber * nbytes), nbytes):
                    # to convert bytestring to 32 bit floating point number
                    phasorMagnitude.append(struct.unpack('>f', phasors[i:i + 4])[0])
                    # conversion to degrees
                    phasorAngle.append(math.degrees(struct.unpack('>f', phasors[i + 4:i + 8])[0]))

            elif self.phasorNotation == 'rectangular':
                print('Rectangular notation not implemented yet')

        elif self.formatPhasor == 'int':
            print('Integer phasor format not implemented yet')
        ######################################################
        # FREQ
        if self.formatFreqDfreq == 'float':
            nbytes = 4
            freqEndbyte = phEndbyte + nbytes
            # to convert bytestring to 32 bit floating point number
            FREQread = struct.unpack('>f', data[phEndbyte:freqEndbyte])[0]

        elif self.formatFreqDfreq == 'int':
            # not tested yet
            nbytes = 2
            freqEndbyte = phEndbyte + nbytes
            # to convert bytestring to 32 bit floating point number
            FREQread = int.from_bytes(data[phEndbyte:freqEndbyte], 'big')
        ###############################################################
        # DFREQ
        if self.formatFreqDfreq == 'float':
            nbytes = 4
            dFreqEndbyte = freqEndbyte + nbytes
            # to convert bytestring to 32 bit floating point number
            DFREQread = struct.unpack('>f', data[freqEndbyte:dFreqEndbyte])[0]

        elif self.formatFreqDfreq == 'int':
            # not tested yet
            nbytes = 2
            dFreqEndbyte = freqEndbyte + nbytes
            # to convert bytestring to 16 bits integer number
            DFREQread = int.from_bytes(data[freqEndbyte:dFreqEndbyte], 'big')
        #################################################################
        # ANALOG
        if self.formatAnalog == 'float':
            nbytes = 4
            analogEndbyte = dFreqEndbyte + (nbytes * self.analogNumber)
            ANALOGSread = data[dFreqEndbyte:analogEndbyte]
            ANALOGvalues = []
            for i in range(0, (self.analogNumber * nbytes), nbytes):
                ANALOGvalues.append(struct.unpack('>f', ANALOGSread[i:i + nbytes])[0])
        elif self.formatAnalog == 'int':
            # not tested yet
            nbytes = 2
            analogEndbyte = dFreqEndbyte + (nbytes * self.analogNumber)
            ANALOGSread = data[dFreqEndbyte:analogEndbyte]
            # to convert bytestring to 16 bits integer number
            ANALOGvalues = int.from_bytes(ANALOGSread[i:i + nbytes], 'big')
        ################################################################
        # DIGITAL
        nbytes = 2
        digitalEndbyte = analogEndbyte + nbytes
        DIGITALread = data[analogEndbyte:digitalEndbyte]
        ###############################################################
        # CREATE DICT WITH DATAFRAME VALUES TO return
        dictDATAread = {'ACK': field1_1, 'frameType': DATAFRAMETYPEread, 'frameTypeStr': strDATAFRAMETYPEread,
                        'protocolVer': VERread, 'FRAMESIZE': FRAMESIZEread, 'IDCODE': IDCODEread, 'SOC': SOCread,
                        'FRACSEC': FRACSECread, 'TIME_QUALITY': TIME_QUALITY, 'TIME_UNIX': TIME_POSIX, 'TIME': TIMEread,
                        'STAT_bits': STATread, 'STAT_VALID_DATA': STAT_VALID_DATA, 'STAT_PMU_ERROR': STAT_PMU_ERROR,
                        'STAT_TIME_SYNC': STAT_TIME_SYNC, 'STAT_DATA_SORTING': STAT_DATA_SORTING,
                        'STAT_TRIGGER_DETECTED': STAT_TRIGGER_DETECTED, 'STAT_CONFIG_CHANGED': STAT_CONFIG_CHANGED,
                        'STAT_UNLOCKED_TIME': STAT_UNLOCKED_TIME, 'STAT_TRIGGER_REASON': STAT_TRIGGER_REASON,
                        'PHASORS_magnitude': phasorMagnitude, 'PHASORS_angle': phasorAngle, 'FREQ': FREQread,
                        'DFREC': DFREQread, 'ANALOG': ANALOGvalues, 'DIGITAL': DIGITALread, }
        ################################################################
        # PRINT VALUES
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
            if TQbit6 == 0:
                print('Leap second direction: False')
            elif TQbit6 == 1:
                print('Leap second direction: True')
            # probar que TQbit6 sea 0 o 1, si no manda un error
            assert TQbit6 <= 1, 'TQbit6 debe ser 0 o 1,no {}'.format(TQbit6)
            if TQbit5 == 0:
                print('Leap second ocurred: False')
            elif TQbit5 == 1:
                print('Leap second ocurred: True')
            # probar que TQbit5 sea 0 o 1, si no manda un error
            assert TQbit5 <= 1, 'TQbit5 debe ser 0 o 1,no {}'.format(TQbit5)
            if TQbit4 == 0:
                print('Leap second pending: False')
            elif TQbit4 == 1:
                print('Leap second pending: True')
            # probar que TQbit4 sea 0 o 1, si no manda un error
            assert TQbit4 <= 1, 'TQbit4 debe ser 0 o 1,no {}'.format(TQbit4)

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
            elif STATbit15 == 1:
                print('STATbit15: {}. Data is not valid or PMU is in test mode'.format(STATbit15))

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
            elif STATbit03_00 > 0b1000 and STATbit03_00 < 0b1111:
                print('STATbit03_00: {}. Trigger reason: user definition'.format(STATbit03_00))
            ###########################################################################
            for i in range(cfg2dict['PHNMR']):
                print(
                    'Phasor #{}: {}, {:0.2f}{} {:0.2f}°'.format(i + 1, cfg2dict['PHASOR_names'][i], phasorMagnitude[i],
                                                                cfg2dict['PHUNIT_str'][i][0], phasorAngle[i]))

            for i, n in enumerate(cfg2dict['ANALOG_names']):
                print('Analog value #{}: {}, {:0.3f}'.format(i + 1, n, round(ANALOGvalues[i], 3)))
        return dictDATAread

    def decode_dataframev2(self, data, verbose=False):
        data = data[0]
        chunks = data[1]
        beginingByte = 0
        # filling dicts with dataframe data
        fldvalue = data[0:2]  # field value
        dictDF_SYNC = {'field': 'SYNC', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue, 'size': 2,
                       'begin': 0, 'end': 2}
        fldvalue = data[2:4]
        dictDF_FRSIZE = {'field': 'FRAME_SIZE', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue,
                         'size': 2, 'begin': 2, 'end': 4}
        fldvalue = data[4:6]
        dictDF_IDCODE = {'field': 'IDCODE', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue, 'size': 2,
                         'begin': 4, 'end': 6}
        fldvalue = data[6:10]
        dictDF_SOC = {'field': 'SOC', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue, 'size': 4,
                      'begin': 6, 'end': 10}
        fldvalue = data[10:14]
        dictDF_FRACSEC = {'field': 'FRACSEC', 'value': int.from_bytes(fldvalue, 'big'), 'hex_val': fldvalue, 'size': 4,
                          'begin': 10, 'end': 14}

        lstdict_DF = [dictDF_SYNC, dictDF_FRSIZE, dictDF_IDCODE, dictDF_SOC, dictDF_FRACSEC, ]
        beginingByte = dictDF_FRACSEC['end']

        # ------------------------------------------------------
        # FOR LOOP
        # --------------------------------------------------------

        num_pmu = 0
        for index, row_pmu in self.dfPMU_info.iterrows():
            # -----------------------------------------
            # filing STAT
            # ----------------------------------------------

            endingByte = beginingByte + 2
            fldvalue = data[beginingByte:endingByte]
            dict_DF_STAT = {'field': 'PMU{}_STAT'.format(index + 1), 'value': '{}'.format(fldvalue.hex()),
                            'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                            'end': endingByte}
            lstdict_DF.append(dict_DF_STAT)
            beginingByte = endingByte

            # --------------------------------------------------------
            # filing phasors measurements
            # ---------------------------------------------------------
            if row_pmu['PHASOR_FORMAT'] == 'int':
                bytes_offset = 4  # 4 bytes for integer measurementes
            elif row_pmu['PHASOR_FORMAT'] == 'float':
                bytes_offset = 8  # 8 bytes for float measurementes

            lst_ph = []
            beginingByte = dict_DF_STAT['end']

            for pn in range(1, row_pmu['PHNMR'] + 1):
                endingByte = beginingByte + bytes_offset
                fldvalue = data[beginingByte:endingByte]
                lst_ph.append({'field': 'PMU{}_PHASOR_{}'.format(index + 1, pn), 'value': '{}'.format(fldvalue.hex()),
                               'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                               'end': endingByte})
                beginingByte = endingByte
            # --------------------------------------------------------
            # filing FREQ measurements
            # ---------------------------------------------------------
            if row_pmu['FORMAT_FREQ_DFREQ'] == 'int':
                bytes_offset_freq = 2
            elif row_pmu['FORMAT_FREQ_DFREQ'] == 'float':
                bytes_offset_freq = 4

            lst_freq = []
            beginingByte = lst_ph[-1]['end']
            endingByte = beginingByte + bytes_offset_freq
            fldvalue = data[beginingByte:endingByte]
            if row_pmu['FORMAT_FREQ_DFREQ'] == 'int':
                value = int.from_bytes(fldvalue)
            elif row_pmu['FORMAT_FREQ_DFREQ'] == 'float':
                value = struct.unpack('>f', fldvalue)[0]

            lst_freq.append({'field': 'PMU{}_FREQ'.format(index + 1), 'value': value, 'hex_val': fldvalue,
                             'size': endingByte - beginingByte, 'begin': beginingByte, 'end': endingByte})
            beginingByte = endingByte
            # --------------------------------------------------------
            # filing DFREQ measurements
            # ---------------------------------------------------------
            lst_dfreq = []
            beginingByte = lst_freq[-1]['end']
            endingByte = beginingByte + bytes_offset_freq
            fldvalue = data[beginingByte:endingByte]
            if row_pmu['FORMAT_FREQ_DFREQ'] == 'int':
                value = int.from_bytes(fldvalue)
            elif row_pmu['FORMAT_FREQ_DFREQ'] == 'float':
                value = struct.unpack('>f', fldvalue)[0]

            lst_dfreq.append({'field': 'PMU{}_DFREQ'.format(index + 1), 'value': value, 'hex_val': fldvalue,
                              'size': endingByte - beginingByte, 'begin': beginingByte, 'end': endingByte})
            beginingByte = endingByte
            # --------------------------------------------------------
            # filing analog measurements
            # ---------------------------------------------------------
            number_of_analogs = row_pmu['ANNMR']
            if number_of_analogs > 0:
                if row_pmu['ANALOGS_FORMAT'] == 'int':
                    bytes_offset = 2  # bytes for integer measurementes
                elif row_pmu['ANALOGS_FORMAT'] == 'float':
                    bytes_offset = 4  # bytes for float measurementes
                lst_an = []
                beginingByte = lst_dfreq[-1]['end']
                for pn in range(1, row_pmu['ANNMR'] + 1):
                    endingByte = beginingByte + bytes_offset
                    fldvalue = data[beginingByte:endingByte]
                    lst_an.append(
                        {'field': 'PMU{}_ANNMR_{}'.format(index + 1, pn), 'value': '{}'.format(fldvalue.hex()),
                         'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                         'end': endingByte})
                    beginingByte = endingByte
            # --------------------------------------------------------
            # filing digital data
            # ---------------------------------------------------------
            number_of_digitals = row_pmu['DGNMR']
            if number_of_digitals > 0:
                lst_dig = []
                bytes_offset = 2
                beginingByte = lst_an[-1]['end']

                for pn in range(1, row_pmu['DGNMR'] + 1):
                    endingByte = beginingByte + bytes_offset
                    fldvalue = data[beginingByte:endingByte]
                    lst_dig.append(
                        {'field': 'PMU{}_DGNMR_{}'.format(index + 1, pn), 'value': '{}'.format(fldvalue.hex()),
                         'hex_val': fldvalue, 'size': endingByte - beginingByte, 'begin': beginingByte,
                         'end': endingByte})
                    beginingByte = endingByte
            lstdict_DF.extend(lst_ph)
            lstdict_DF.extend(lst_freq)
            lstdict_DF.extend(lst_dfreq)
            if number_of_analogs > 0:
                lstdict_DF.extend(lst_an)
            if number_of_digitals > 0:
                lstdict_DF.extend(lst_dig)
        endingByte = beginingByte + 2
        fldvalue = data[beginingByte:endingByte]
        dictDF_CHK = {'field': 'CHK', 'value': '{}'.format(fldvalue.hex()), 'hex_val': fldvalue,
                      'size': endingByte - beginingByte, 'begin': beginingByte, 'end': endingByte}

        lstdict_DF.append(dictDF_CHK)
        dfPMU_Dataframe_raw = pd.DataFrame.from_records(lstdict_DF)

        # ****************************************************************
        lstPMU_Meas = []
        # index starts at 0 but PMU numbers at 1. Add 1 to index.
        for index, row_pmu in self.dfPMU_info.iterrows():
            dictDF_Decoded = {}
            decSOC = int.from_bytes(dfPMU_Dataframe_raw[dfPMU_Dataframe_raw['field'] == 'SOC']['hex_val'].values[0],
                                    'big')
            decFRACSEC = int.from_bytes(
                dfPMU_Dataframe_raw[dfPMU_Dataframe_raw['field'] == 'FRACSEC']['hex_val'].values[0][1:], 'big')
            timebase = self.dfCFG2[self.dfCFG2['field'] == 'TIME_BASE']['value'].values[0]
            epoch_time = decSOC + (decFRACSEC / timebase)
            dictDF_Decoded['EPOCH_TIME'] = epoch_time
            dictDF_Decoded['TIME'] = datetime.utcfromtimestamp(epoch_time).strftime('%Y-%m-%d %H:%M:%S')
            dictDF_Decoded['FRACSEC'] = decFRACSEC / timebase
            # dictDF_Decoded['FRACSEC_RAW'] = decFRACSEC
            dictDF_Decoded['STN'] = row_pmu['STN']
            dictDF_Decoded['IDCODE'] = row_pmu['IDCODE']
            # -----------------------------------------------------------------
            # STAT
            # -------------------------------------------------------------------
            STATread = \
                dfPMU_Dataframe_raw[dfPMU_Dataframe_raw['field'] == 'PMU{}_STAT'.format(index + 1)]['hex_val'].values[0]
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
                dictDF_Decoded['DATA_VALID'] = True
            elif STATbit15 == 1:
                dictDF_Decoded['DATA_VALID'] = False

            if STATbit14 == 0:
                dictDF_Decoded['PMU_ERROR'] = False
            elif STATbit14 == 1:
                dictDF_Decoded['PMU_ERROR'] = False

            if STATbit13 == 0:
                dictDF_Decoded['PMU_SYNC'] = True
            elif STATbit13 == 1:
                dictDF_Decoded['PMU_SYNC'] = False

            if STATbit12 == 0:
                dictDF_Decoded['DATA_SORTING'] = 'timestamp'
            elif STATbit12 == 1:
                dictDF_Decoded['DATA_SORTING'] = 'arrival'

            if STATbit11 == 0:
                dictDF_Decoded['TRIGGER_DETECTED'] = False
            elif STATbit11 == 1:
                dictDF_Decoded['TRIGGER_DETECTED'] = True

            if STATbit10 == 0:
                dictDF_Decoded['CONFIG_CHANGED'] = False
            elif STATbit10 == 1:
                dictDF_Decoded['CONFIG_CHANGED'] = True

            if STATbit05_04 == 0b00:
                dictDF_Decoded['UNLOCKED_TIME'] = 0

            elif STATbit05_04 == 0b01:
                dictDF_Decoded['UNLOCKED_TIME'] = 10
            elif STATbit05_04 == 0b10:
                dictDF_Decoded['UNLOCKED_TIME'] = 100
            elif STATbit05_04 == 0b11:
                dictDF_Decoded['UNLOCKED_TIME'] = 1000

            if STATbit03_00 == 0b0111:
                dictDF_Decoded['TRIGGER_REASON'] = 'digital'

            elif STATbit03_00 == 0b0101:
                dictDF_Decoded['TRIGGER_REASON'] = 'df/dt high'
            elif STATbit03_00 == 0b0011:
                dictDF_Decoded['TRIGGER_REASON'] = 'phase-angle diff'
            elif STATbit03_00 == 0b0001:
                dictDF_Decoded['TRIGGER_REASON'] = 'magnitud low'
            elif STATbit03_00 == 0b0110:
                dictDF_Decoded['TRIGGER_REASON'] = 'reserved'
            elif STATbit03_00 == 0b100:
                dictDF_Decoded['TRIGGER_REASON'] = 'frequency high/low'
            elif STATbit03_00 == 0b010:
                dictDF_Decoded['TRIGGER_REASON'] = 'magnitud high'
            elif STATbit03_00 == 0b000:
                dictDF_Decoded['TRIGGER_REASON'] = 'manual'
            elif STATbit03_00 > 0b1000 and STATbit03_00 < 0b1111:
                dictDF_Decoded['TRIGGER_REASON'] = 'user defined'

            # ---------------------------------------------------------------------------------------------
            # PHASORS
            # --------------------------------------------------------------------------------------------
            number_of_phasors = self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_PHNMR'.format(index + 1)]['value'].values[0]
            phasor_names = self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_CHNAM_PHASORS'.format(index + 1)]['value'].values[
                0]
            lst_phasor_names = [phasor_names[i:i + 16] for i in range(0, len(phasor_names), 16)]
            if row_pmu['PHASOR_FORMAT'] == 'float':
                if row_pmu['PHASOR_NOTATION'] == 'polar':
                    for pn in range(1, number_of_phasors + 1):
                        dictDF_Decoded['PHASOR{}_CHNAM'.format(pn)] = lst_phasor_names[pn - 1]
                        dictDF_Decoded['PHASOR{}_UNIT'.format(pn)] = \
                            self.dfCFG2[self.dfCFG2['field'] == 'PMU{}_PHASOR{}_UNIT'.format(index + 1, pn)][
                                'value'].values[0]
                        # phasor data to be decoded
                        ph_data = dfPMU_Dataframe_raw[
                            dfPMU_Dataframe_raw['field'] == 'PMU{}_PHASOR_{}'.format(index + 1, pn)]['hex_val'].values[
                            0]
                        # to convert bytestring to 32 bit floating point number
                        dictDF_Decoded['PHASOR{}_MAG'.format(pn)] = struct.unpack('>f', ph_data[:4])[0]
                        # conversion to degrees
                        dictDF_Decoded['PHASOR{}_ANG'.format(pn)] = math.degrees(struct.unpack('>f', ph_data[4:])[0])
                elif row_pmu['PHASOR_NOTATION'] == 'rectangular':
                    for pn in range(1, number_of_phasors + 1):
                        dictDF_Decoded['PHASOR{}_CHNAM'.format(pn)] = lst_phasor_names[pn - 1]
                        ph_data = dfPMU_Dataframe_raw[
                            dfPMU_Dataframe_raw['field'] == 'PMU{}_PHASOR_{}'.format(index + 1, pn)]['hex_val'].values[
                            0]
                        # Test: float format and rectangular notation
                        dictDF_Decoded['PHASOR{}_REAL'.format(pn)] = struct.unpack('>f', ph_data[:4])[0]
                        dictDF_Decoded['PHASOR{}_IMAG'.format(pn)] = struct.unpack('>f', ph_data[4:])[0]
                else:
                    print('Error in phasor notation.')
            elif row_pmu['PHASOR_FORMAT'] == 'int':
                # Test: int format and polar notation
                if row_pmu['PHASOR_NOTATION'] == 'polar':
                    for pn in range(1, number_of_phasors + 1):
                        dictDF_Decoded['PHASOR{}_CHNAM'.format(pn)] = phasor_names[pn]
                        # phasor data to be decoded
                        ph_data = dfPMU_Dataframe_raw[
                            dfPMU_Dataframe_raw['field'] == 'PMU{}_PHASOR_{}'.format(index + 1, pn)]['hex_val'].values[
                            0]
                        # to convert bytestring to 32 bit floating point number
                        dictDF_Decoded['MAG_PHASOR_{}'.format(pn)] = struct.unpack('>H', ph_data[:2])[0]
                        # conversion to degrees
                        dictDF_Decoded['ANG_PHASOR_{}'.format(pn)] = math.degrees(struct.unpack('>h', ph_data[2:])[0])
                elif row_pmu['PHASOR_NOTATION'] == 'rectangular':
                    # Test: int format and rectangular notation
                    for pn in range(1, number_of_phasors + 1):
                        dictDF_Decoded['PHASOR{}_CHNAM'.format(pn)] = phasor_names[pn]
                        ph_data = dfPMU_Dataframe_raw[
                            dfPMU_Dataframe_raw['field'] == 'PMU{}_PHASOR_{}'.format(index + 1, pn)]['hex_val'].values[
                            0]
                        dictDF_Decoded['REAL_PHASOR_{}'.format(pn)] = struct.unpack('>h', ph_data[:2])[0]
                        dictDF_Decoded['IMAG_PHASOR_{}'.format(pn)] = struct.unpack('>h', ph_data[2:])[0]
                else:
                    print('Error in phasor notation.')
            else:
                print('Error in phasor format.')

            # -------------------------------------------------------------------------
            # FREQ
            # -------------------------------------------------------------------------
            freq_data = \
                dfPMU_Dataframe_raw[dfPMU_Dataframe_raw['field'] == 'PMU{}_FREQ'.format(index + 1)]['hex_val'].values[0]
            if row_pmu['FORMAT_FREQ_DFREQ'] == 'float':
                # to convert bytestring to 32 bit floating point number
                dictDF_Decoded['FREQ'] = struct.unpack('>f', freq_data)[0]

            elif row_pmu['FORMAT_FREQ_DFREQ'] == 'int':
                dictDF_Decoded['FREQ'] = int.from_bytes(freq_data, 'big')
            # -------------------------------------------------------------------------
            # DFREQ
            # -------------------------------------------------------------------------
            dfreq_data = \
                dfPMU_Dataframe_raw[dfPMU_Dataframe_raw['field'] == 'PMU{}_DFREQ'.format(index + 1)]['hex_val'].values[
                    0]
            if row_pmu['FORMAT_FREQ_DFREQ'] == 'float':
                # to convert bytestring to 32 bit floating point number
                dictDF_Decoded['DFREQ'] = struct.unpack('>f', dfreq_data)[0]

            elif row_pmu['FORMAT_FREQ_DFREQ'] == 'int':
                dictDF_Decoded['DFREQ'] = int.from_bytes(dfreq_data, 'big')

            # -------------------------------------------------------------------------
            # ANALOGS
            # -------------------------------------------------------------------------
            # Test: analogs
            if row_pmu['ANNMR'] > 0:

                for pn in range(number_of_phasors):
                    analog_data = \
                        dfPMU_Dataframe_raw[dfPMU_Dataframe_raw['field'] == 'PMU{}_ANNMR_{}'.format(index + 1, pn)][
                            'hex_val'].values[0]
                if row_pmu['ANALOG_FORMAT'] == 'float':
                    for an in range(row_pmu['ANNMR']):
                        dictDF_Decoded['ANALOG_VALUE_{}'.format(pn)] = struct.unpack('>f', analog_data)[0]
                elif row_pmu['ANALOG_FORMAT'] == 'int':
                    for an in range(row_pmu['ANNMR']):
                        dictDF_Decoded['ANALOG_VALUE_{}'.format(pn)] = int.from_bytes(analog_data, 'big')

            # -------------------------------------------------------------------------
            # DIGITALS
            # -------------------------------------------------------------------------
            # Test: digitals
            if row_pmu['DGNMR'] > 0:
                digital_data = \
                    dfPMU_Dataframe_raw[dfPMU_Dataframe_raw['field'] == 'PMU{}_DGNMR_{}'.format(index + 1, pn)][
                        'hex_val'].values[0]
                for pn in range(number_of_phasors):
                    dictDF_Decoded['DIGITAL_VALUE_{}'.format(pn)] = digital_data

            lstPMU_Meas.append(dictDF_Decoded)
        self.dataFrame = pd.DataFrame.from_records(lstPMU_Meas, index='EPOCH_TIME')
        # dataframe of dataframes read
        self.dataframes_read = pd.concat([self.dataframes_read, self.dataFrame])

        return self.dataFrame

    def read_dataframe(self):
        data = self.read_dataframe_raw()
        return self.decode_dataframev2(data)

    def read_dataframe_dict(self):
        [data, crc] = self.read_dataframe()
        return self.decode_dataframe(data)

    def start_reading(self, max_rows=None):
        self.event_stop_reading.clear()
        self.isReading=True
        # self.thread = Thread(target=self.__read_dataframes_continuously, args=(self.event_stop_reading, max_rows),
        #                      daemon=True)
        # # run the thread
        # self.thread.start()
        self.thread_pool_exec.submit(self.__read_dataframes_continuously, self.event_stop_reading, max_rows)

    def stop_reading(self):
        self.event_stop_reading.set()
        self.isReading=False
        

    def __read_dataframes_continuously(self, event, max_rows):
        while True:
            print(event.is_set())
            self.read_dataframe()
            if not max_rows is None:
                # pop first registers
                if len(self.dataframes_read) > max_rows:
                    mask_epocht = 'EPOCH_TIME == {}'.format(self.dataframes_read.index[0])
                    mask_fracsec = 'FRACSEC == {}'.format(self.dataframes_read.iloc[0]['FRACSEC'])
                    indexes_to_drop = self.dataframes_read.query('{} & {}'.format(mask_epocht, mask_fracsec)).index
                    self.dataframes_read.drop(indexes_to_drop, inplace=True)

            if event.is_set():
                #break
                pass
            #to allow threads to switch
            time.sleep(0.01)

    def __stream_dataframe(self, connection):
        while True:
            dataframe_to_stream = self.dataframe_raw
            while dataframe_to_stream == self.dataframe_raw:
                # because im using threads and not processes
                # sleep this thread to be able to change to another thread
                time.sleep(0.01)
            connection.sendall(dataframe_to_stream)

    def __create_streaming_server(self, port=5000):
        # Create a TCP/IP socket
        stream_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Bind the socket to the port
        server_address = ('localhost', port)
        print('starting up on {} port {}'.format(*server_address))
        stream_server_socket.bind(server_address)

        # Listen for incoming connections
        stream_server_socket.listen(5)
        return stream_server_socket

    def __wait_for_connections2(self, socket_server,cfg2_bytes):
        lst_connections = []
        while True:
            # because im using threads and not processes
            # sleep this thread to be able to change to another thread
            time.sleep(0.01)
            # Wait for a connection
            print('waiting for a connection')
            # connection, client_address = sock.accept()
            lst_connections.append(socket_server.accept())
            client_address = lst_connections[-1][1]

            try:
                print('connection from', client_address)
                lst_connections[-1][0].sendall(cfg2_bytes)
                time.sleep(1)


                self.thread_pool_exec.submit(self.__stream_dataframe,lst_connections[-1][0])

            finally:
                # Clean up the connection
                # connection.close()#%%
                pass

    def __wait_for_connections(self,socket_server,cfg2_bytes):
        lst_connections =[]
        while True:
            # Wait for a connection
            print('waiting for a connection')
            lst_connections.append(socket_server.accept())

            try:
                print('connection from', client_address)
                connection.sendall(cfg2_bytes)
                time.sleep(1)
                #self.process_pool_exec.submit(self.__stream_dataframe, connection)
            finally:
                # Clean up the connection
                # connection.close()#%%
                pass

    def start_streaming_server(self, port=5000):
        socket_server = self.__create_streaming_server(port)
        try:
            self.thread_pool_exec.submit(self.__wait_for_connections2,socket_server,self.cfg2_raw)
        except:
            print('error')
        #a.result()

    def stop_streaming_server(self):
        self.thread_pool_exec.shutdown(wait=False)

