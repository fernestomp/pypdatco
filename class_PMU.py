# -*- coding: utf-8 -*-
import time
import math
import socket
from datetime import datetime
import struct

from get_crc16 import get_crc16 #own function

class PMU:
    def __init__(self, ip, port = 4712, idcode = 1):
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

    def __open_socket(self):
        self.PMUSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.PMUSocket.settimeout(5)
        self.PMUSocket.connect((self.ip, self.port))

    def __close_socket(self):
         self.PMUSocket.close()

    def connect(self):
        self.__open_socket()
        cfg2 = self.request_cfg2()
        self.decode_cfg2(cfg2) #to populate the pmu configuration data

    def disconnect(self):
        self.__close_socket()

    def request_cfg2(self):
        SYNC_1 = 0xAA #ACK
        SYNC_2 = 0x41
        FRAMESIZE_1= 0x0
        FRAMESIZE_2 = 0x12
        [IDCODE_1, IDCODE_2] = int(self.idcode).to_bytes(2,'big')
        PCtime = time.time() #unix time
        [SOC_1, SOC_2, SOC_3, SOC_4] = int(PCtime).to_bytes(4,'big')
        FRACSEC_1 = 0x00
        CMD_1 = 0X00
        CMD_2 = 0X05
        [FRACSEC_2, FRACSEC_3, FRACSEC_4] = int(str(round(math.fmod(PCtime,1),7))[2:]).to_bytes(3,'big')
        msgNoCHK = [SYNC_1, SYNC_2, FRAMESIZE_1, FRAMESIZE_2, IDCODE_1, IDCODE_2,
        SOC_1, SOC_2, SOC_3, SOC_4, FRACSEC_1, FRACSEC_2, FRACSEC_3,FRACSEC_4,
        CMD_1, CMD_2]
        [crcbyte1,crcbyte2,crc_16] = get_crc16(bytearray(msgNoCHK))
        message = msgNoCHK.copy()
        message.append(crcbyte1)
        message.append(crcbyte2)
        try:
            self.PMUSocket.sendall(bytearray(message))
        except Exception as e: # work on python 3.x
            print(e)
            return
        return self.PMUSocket.recv(self.buffersize) #cfg2 received

    def decode_cfg2(self,cgf2frame,verbose = False):
        SYNCread = cgf2frame[0:2]
        leadingbyteSYNC = SYNCread[0]#it should be 0xAA
        secondbyteSYNC = SYNCread[1]

        frametypebits = (secondbyteSYNC & 112) >> 4 #112 = 01110000b

        if  frametypebits == 0:
                strframetype ='Data Frame'

        elif frametypebits == 1:
                strframetype ='Header Frame'

        elif frametypebits == 2:
                strframetype ='Configuration frame 1'

        elif frametypebits == 3:
                strframetype ='Configuration frame 2'

        elif frametypebits == 4:
                strframetype ='Command frame'
        protocolversion = secondbyteSYNC & 15 #00001111b = 15

        FRAMESIZEread = cgf2frame[2:4]

        decFRAMESIZE = int.from_bytes(FRAMESIZEread,'big')

        IDCODEread = cgf2frame[4:6]
        decIDCODE = int.from_bytes(IDCODEread,'big')

        SOCread = cgf2frame[6:10]
        #SOC en formato decimal, convertir 4 bytes a entero, big endian
        decSOC = int.from_bytes(SOCread,'big')

        FRACSECread = cgf2frame[10:14]
        decFRACSEC = int.from_bytes( FRACSECread[1:4],'big')
        #FRACSEC en formato decimal, convertir 4 bytes a entero, big endian
        TIME_QUALITY = FRACSECread[0]
        TQbit7 = TIME_QUALITY & 128 #reserved
        TQbit6 = TIME_QUALITY & 64 #leap second direction 0 for add, 1 for delete
        #Leap second ocurred. Set in the first second after the leap
        #second occurs and remains set for 24h.
        TQbit5 = TIME_QUALITY & 32
        #Leap second pending. Set before a leap second occurs and cleared
        #in the second anfter the leap second occurs.
        TQbit4 = TIME_QUALITY & 16
        TQbits3_0 = TIME_QUALITY & 15

        TIME_BASEread = cgf2frame[14:18]
        #TIME_BASE en formato decimal, convertir 4 bytes a entero, big endian
        decTIME_BASE = int.from_bytes(TIME_BASEread,'big')

        NUM_PMUread = cgf2frame[18:20]
        decNUM_PMU = int.from_bytes(NUM_PMUread,'big')

        STNread = cgf2frame[20:36]

        #idcode de donde vienen los datos
        IDCODESRCread = cgf2frame[36:38]
        decIDCODESRC = int.from_bytes(IDCODESRCread,'big')

        FORMATread = cgf2frame[38:40]

        FRMTbit3 = (FORMATread[1] & 8) >> 3
        FRMTbit2 = (FORMATread[1] & 4) >> 2
        FRMTbit1 = (FORMATread[1] & 2) >> 1
        FRMTbit0 = (FORMATread[1] & 1)

        if FRMTbit3== 0:
            FORMAT_FREQ_DFREQ = 'int'
        elif FRMTbit3 ==1:
            FORMAT_FREQ_DFREQ = 'float'

        if FRMTbit2 ==0:
            FORMAT_ANALOG = 'int'
        elif FRMTbit2 ==1:
            FORMAT_ANALOG = 'float'

        if FRMTbit1 ==0:
            FORMAT_PHASOR = 'int'
        elif FRMTbit1 ==1:
            FORMAT_PHASOR = 'float'

        if FRMTbit0 ==0:
            PHASOR_NOTATION = 'rectangular'
        elif FRMTbit0 ==1:
            PHASOR_NOTATION = 'polar'

        PHNMRread = cgf2frame[40:42]
        decPHNMR = int.from_bytes(PHNMRread,'big')

        ANNMRread = cgf2frame[42:44]
        decANNMR = int.from_bytes(ANNMRread,'big')

        DGNMRread = cgf2frame[44:46]
        decDGNMR = int.from_bytes(DGNMRread,'big')

        nbytes_CHNAM = 16*(decPHNMR + decANNMR + (16*decDGNMR))
        CHNAMread = cgf2frame[46:46+nbytes_CHNAM]
        #lista para hacer un slice de los nombres cada 16 bytes
        listslice = list(range(0, int(nbytes_CHNAM+16),16) )
        listCHNAM =[]
        for i in range(len(listslice)-1):
            #lista completa de los nombres de los canales
            listCHNAM.append(CHNAMread[listslice[i]:listslice[i+1]])
        #nombres de fasores
        #PHASORNAMES = [x.decode('utf-8') for x in listCHNAM[0:decPHNMR] ]
        PHASORNAMES = listCHNAM[0:decPHNMR]
        #nombre de valores analogicos
        ANALOGNAMES = listCHNAM[decPHNMR:decPHNMR+decANNMR]
        #ANALOGNAMES = [x.decode('utf-8') for x in listCHNAM[decPHNMR:decPHNMR+decANNMR] ]
        # digital status labels
        DIGITALLABELS = listCHNAM[decPHNMR+decANNMR:decPHNMR+decANNMR + decDGNMR*16]

        numbytesPHUNIT = 4*decPHNMR
        PHUNITbegintbyte = 46+nbytes_CHNAM
        PHUNITendbyte = PHUNITbegintbyte + numbytesPHUNIT
        PHUNITread = cgf2frame[PHUNITbegintbyte:PHUNITendbyte]
        listslice = list(range(0, int(numbytesPHUNIT+4),4) )#4 bytes en pasos de 4 bytes
        listPHUNIT = []
        for i in range(len(listslice)-1):
            #lista completa los factores de conversion
            listPHUNIT.append(PHUNITread[listslice[i]:listslice[i+1]])
        PHUNIT_str = []  #list of strings for PHUNIT (volt or ampere)
        PHUNIT_factor = [] #list of factors for PHUNIT
        # convirtiendo los valores a texto
        for i in range(len(listPHUNIT)):
            if listPHUNIT[i][0] == 0:
                PHUNIT_str.append('Volt')
                #unit = 'Volt'
            elif listPHUNIT[i][0] == 1:
                PHUNIT_str.append('Ampere')
                #unit = 'Ampere'
            PHUNIT_factor.append(int.from_bytes(listPHUNIT[i][1:4],'big'))

        numbytesANUNIT = 4*decANNMR
        ANUNITendbyte = PHUNITendbyte + numbytesPHUNIT
        ANUNITread = cgf2frame[PHUNITendbyte:ANUNITendbyte]
        listslice = list(range(0, int(numbytesANUNIT+4),4) )#4 bytes en pasos de 4 bytes
        listANUNIT = []
        for i in range(len(listslice)-1):
            #lista completa los factores de conversion
            listANUNIT.append(ANUNITread[listslice[i]:listslice[i+1]])
        ANUNIT_factor = [] #list of factors decoded for ANUNIT
        ANUNIT_value = [] #list of values decoded for ANUNIT
        #convertir a texto
        for i in range(len(listANUNIT)):
            if listANUNIT[i][0] == 0:
                ANUNIT_factor.append('single point-on-wave')
                #factor = 'single point-on-wave'
            elif listANUNIT[i][0] == 1:
                ANUNIT_factor.append('rms of analog input')
                #factor = 'rms of analog input'
            elif listANUNIT[i][0] == 2:
                ANUNIT_factor.append('peak of analog input')
                #factor = 'peak of analog input'
            ANUNIT_value.append( int.from_bytes(listANUNIT[i][1:4],'big'))


        numbytesDIGUNIT = 4*decDGNMR
        DIGUNITendbyte = ANUNITendbyte + numbytesDIGUNIT
        DIGUNITread = cgf2frame[ANUNITendbyte:DIGUNITendbyte]
        listslice = list(range(0, int(numbytesDIGUNIT+4),4) )#4 bytes en pasos de 4 bytes
        listDIGUNIT = []
        for i in range(len(listslice)-1):
            #lista completa los factores de conversion
            listDIGUNIT.append(DIGUNITread[listslice[i]:listslice[i+1]])

        FNOMendbyte = DIGUNITendbyte +2
        FNOMread = cgf2frame[DIGUNITendbyte:FNOMendbyte]

        FNOMbit0 = FNOMread[0]  & 1
        if FNOMbit0 == 1:
            decFNOM = 50
        elif FNOMbit0==0:
            decFNOM = 60

        CFGCNTendbyte = FNOMendbyte +2
        CFGCNTread = cgf2frame[FNOMendbyte:CFGCNTendbyte]
        decCFGCNT = int.from_bytes(CFGCNTread,'big')

        DATA_RATEendbyte = CFGCNTendbyte + 2
        DATA_RATEread = cgf2frame[CFGCNTendbyte:DATA_RATEendbyte]
        decDATA_RATE = int.from_bytes(DATA_RATEread,'big')
        assert decDATA_RATE !=0, 'DATA_RATE cannot be zero'

        CHKendbyte = DATA_RATEendbyte + 2
        CHKread = cgf2frame[DATA_RATEendbyte:CHKendbyte]
        decCHK = int.from_bytes(CHKread,'big')

        #create a dict with all values
        dictDATAread = {
            'ACK': leadingbyteSYNC,
            'frameType': frametypebits,
            'frameTypeStr': strframetype,
            'protocolVer': protocolversion,
            'FRAMESIZE': decFRAMESIZE,
            'IDCODE': decIDCODE,
            'SOC': decSOC,
            'FRACSEC': decFRACSEC,
            'TIME_QUALITY': TIME_QUALITY,
            'TIME_BASE': decTIME_BASE,
            'NUM_PMU': decNUM_PMU,
            'STN': STNread,
            'IDCODEsrc': decIDCODESRC,
            'FORMAT': FORMATread,
            'FORMAT_freq_dfreq': FORMAT_FREQ_DFREQ,
            'FORMAT_analog': FORMAT_ANALOG,
            'FORMAT_phasor': FORMAT_PHASOR,
            'PHASOR_notation': PHASOR_NOTATION,
            'PHNMR': decPHNMR,
            'ANNMR': decANNMR,
            'DGNMR': decDGNMR,
            'PHASOR_names': PHASORNAMES,
            'ANALOG_names': ANALOGNAMES,
            'DIGITAL_labels': DIGITALLABELS,
            'PHUNIT': listPHUNIT,
            'PHUNIT_str': PHUNIT_str,
            'PHUNIT_factor': PHUNIT_factor,
            'ANUNIT': listANUNIT,
            'ANUNIT_factor': ANUNIT_factor,
            'ANUNIT_value': ANUNIT_value,
            'DIGUNIT': listDIGUNIT,
            'FNOM': decFNOM,
            'CFGNT': decCFGCNT,
            'DATA_RATE': decDATA_RATE,
            'CHK': decCHK
        }
        #class values
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

        #print values (verbose=True)
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
            print ('Digital status labels')
            for i in dictDATAread['DIGITAL_labels']:
                print(i)
            for i in range(len(dictDATAread['PHUNIT_str'])):
                print('#{} factor: {} * 10^-5, unit: {}'.format(
                    i+1,dictDATAread['PHUNIT_factor'][i],dictDATAread['PHUNIT_str'][i]))
            for i in range(len(dictDATAread['ANUNIT_factor'])):
                print('Factor for analog value #{}: {}, value: {}'.format(
                    i+1,dictDATAread['ANUNIT_factor'][i],dictDATAread['ANUNIT_value'][i]))
            for i, w in enumerate(range(len(dictDATAread['DIGUNIT']))):
                print('Digital status word #{}: {}'.format(
                    i+1,dictDATAread['DIGUNIT'][i]))
            print('Nominal line frequency: {}'.format(dictDATAread['FNOM']))
            print('Configuration change count: {}'.format(dictDATAread['CFGNT']))
            if dictDATAread['DATA_RATE']  > 0:
                print('{} frame(s) per second'.format(dictDATAread['DATA_RATE']))
            elif dictDATAread['DATA_RATE'] < 0:
                print('1 frame per {} seconds'.format(dictDATAread['DATA_RATE']))
            print('CRC: {}'.format(hex(dictDATAread['CHK'])))
        return dictDATAread

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
        field1_1 = 170#AA.
        field1_2 = 65 #0-reservado100-data frame comando0001-2005
        #2 FRAMESIZE
        #it's always 18 because im not using the EXTFRAME data (table 12-command frame configuration)
        field2_1 =0
        field2_2=18
        # 3 field IDCODE
        #dividir en dos bytes y hacer un bitshift 8 lugares a la derecha
        [field3_1, field3_2] = int(self.idcode).to_bytes(2,'big')
        #4 SOC
        #send unix time
        PCtime = time.time()
        t = int(PCtime).to_bytes(4,'big')
        field4_1 =t[0]
        field4_2 =t[1]
        field4_3 =t[2]
        field4_4 =t[3]
        #5 FRACSEC
        #fmod:get fractional part,
        #round: to convert fractional part to 3 bytes (precision is lost)
        #str:to do slicing and remove "0." part
        #int to_bytes: list of 3 bytes of the fractional part
        fsec = int(str(round(math.fmod(PCtime,1),7))[2:]).to_bytes(3,'big')
        field5_1 =0 #time quality flags, ignore leap seconds
        field5_2 =fsec[0]
        field5_3 =fsec[1]
        field5_4 =fsec[2]
        #6 CMD
        field6_1 = 0 #first byte is zero
        #check if the command is the number representation
        #or a string Command
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
        #7 EXTFRAME no se usa
        #8 CHK
        #mensajae sin CHK
        messnoCHK = [field1_1 , field1_2,
            field2_1,field2_2,
            field3_1, field3_2,
            field4_1, field4_2, field4_3, field4_4,
            field5_1, field5_2, field5_3, field5_4,
            field6_1, field6_2]

        [crcbyte1,crcbyte2,crc_16] = get_crc16(bytearray(messnoCHK));
        message = messnoCHK.copy()
        message.append(crcbyte1)
        message.append(crcbyte2)
        message_bytearr = bytearray(message)
        self.PMUSocket.send(message_bytearr)

    def read_dataframe(self):
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
        #read  measurements
        #this code is not optimal, n frames per second are expected
        #is only for testing purposes, data could be lost or superimposed
        #ask for n dataframes

        #can only recieve buffersize bytes
        #maybe i should use a function that can get me
        #the numbers of bytes before using the recv function
        self.send_command('start')
        data = self.PMUSocket.recv(self.buffersize)
        #check if first byte is AA (begining of the dataframe)
        if data[:1].hex() =='aa':
            #get the framesize
            framesizebytes  = data[2:4]
            framesize = int.from_bytes(framesizebytes,'big')
            #the dataframes could be superimposed, so i get the framesize and
            #divide the data into n framesize strings
            #split data in chunks of framsize
            if len(data) > framesize:
                datachunks = [data[i:i+framesize] for i in range(0, len(data), framesize)]
                for d in datachunks:
                    #print('Framesize: {}, length of dataframe: {}'.format(framesize,len(d)))
                    #print(d)
                    #:-2 porque los ultimos bytes son el numero crc
                    [_,_,crccalc] =get_crc16(d[:-2])
                    crcsrc=int.from_bytes(d[-2:],'big')
                    if crccalc==crcsrc:
                        return d, True

                    else:
                        return data, False

            else: #no superimposed dataframes
                #:-2 porque los ultimos bytes son el numero crc
                [_,_,crccalc] =get_crc16(data[:-2])
                crcsrc=int.from_bytes(data[-2:],'big')
                if crccalc==crcsrc:
                    #print('CRC Ok!')
                    return data, True
                else:
                    return data, False
    def decode_dataframe(self,data,verbose = False):
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

        TIME_POSIX = SOCread + (FRACSECread/self.timeBase);
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
        if self.formatPhasor == 'float':
            nbytes= 8
            phEndbyte = 16 + (nbytes* self.phasorNumber)
            phasors = data[16:phEndbyte]
            phasorMagnitude = []
            phasorAngle =[]
            if self.phasorNotation == 'polar':
                #first 4 bytes are the magnitude, next four bytes are the angle (i+4:i+8)
                for i in range(0,(self.phasorNumber*nbytes),nbytes):
                    #to convert bytestring to 32 bit floating point number
                    phasorMagnitude.append(struct.unpack('>f', phasors[i:i+4])[0])
                    #conversion to degrees
                    phasorAngle.append(math.degrees( struct.unpack('>f', phasors[i+4:i+8])[0]))

            elif self.phasorNotation  == 'rectangular':
                print('Rectangular notation not implemented yet')

        elif self.formatPhasor  == 'int':
            print('Integer phasor format not implemented yet')
        ######################################################
        #FREQ
        if self.formatFreqDfreq  == 'float':
            nbytes= 4
            freqEndbyte = phEndbyte + nbytes
            #to convert bytestring to 32 bit floating point number
            FREQread = struct.unpack('>f', data[phEndbyte:freqEndbyte])[0]

        elif self.formatFreqDfreq  =='int':
            #not tested yet
            nbytes= 2
            freqEndbyte = phEndbyte + nbytes
            #to convert bytestring to 32 bit floating point number
            FREQread = int.from_bytes(data[phEndbyte:freqEndbyte],'big')
        ###############################################################
        #DFREQ
        if self.formatFreqDfreq  == 'float':
            nbytes= 4
            dFreqEndbyte = freqEndbyte + nbytes
            #to convert bytestring to 32 bit floating point number
            DFREQread = struct.unpack('>f', data[freqEndbyte:dFreqEndbyte])[0]

        elif self.formatFreqDfreq  == 'int':
            #not tested yet
            nbytes= 2
            dFreqEndbyte = freqEndbyte + nbytes
            #to convert bytestring to 16 bits integer number
            DFREQread = int.from_bytes(data[freqEndbyte:dFreqEndbyte],'big')
        #################################################################
        #ANALOG
        if self. formatAnalog == 'float':
            nbytes = 4
            analogEndbyte = dFreqEndbyte + (nbytes * self.analogNumber)
            ANALOGSread = data[dFreqEndbyte:analogEndbyte]
            ANALOGvalues = []
            for i in range(0,(self.analogNumber*nbytes),nbytes):
                ANALOGvalues.append(struct.unpack('>f', ANALOGSread[i:i+nbytes])[0])
        elif self.formatAnalog  == 'int':
            #not tested yet
            nbytes= 2
            analogEndbyte = dFreqEndbyte + (nbytes * self.analogNumber)
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

    def read_dataframe_dict(self):
        [data,crc] = self.read_dataframe()
        return self.decode_dataframe(data)
