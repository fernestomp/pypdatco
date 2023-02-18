# -*- coding: utf-8 -*-
#useful with raspberry pi

def decode_cfg2(cgf2frame,verbose = False):
    '''
        Function to decode the configuration frame 2.

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
    # va en orden, segun la tabla 9 del protocolo c37.118 (configuration frame organization)
    # decodificar CFG2
    #####################################
    #         1 SYNC (2 bytes)
    ####################################
    SYNCread = cgf2frame[0:2]
    leadingbyteSYNC = SYNCread[0]#it should be 0xAA
    secondbyteSYNC = SYNCread[1]
    #print('Leading byte SYNC: {}'.format(leadingbyteSYNC.hex()))
    #print('Second byte SYNC: {}'.format(secondbyteSYNC.hex()))

    ###########################################################
    #           OBTENER EL TIPO DE DATAFRAME (2 bytes)        #
    ###########################################################
    # Frame synchronization word.                             #
    # Leading byte: AA hex                                    #
    # Second byte: Frame type and Version, divided as follows:#
    # Bit 7: Reserved for future definition                   #
    # Bits 6–4: 000: Data Frame                               #
    # 001: Header Frame                                       #
    # 010: Configuration Frame 1                              #
    # 011: Configuration Frame 2                              #
    # 100: Command Frame (received message)                   #
    # Bits 3–0: Version number, in binary (1–15),             #
    # version 1 for this initial publication.                 #
    ###########################################################
    #tomar los bytes 7,6,5 que indican el tipo de frame (empieza en 1 y no cero)
    #y desplazar 4 bytes a la derecha para que queden al inicio de la palabra
    #no en medio y poder tomar el numero decimal directo
    frametypebits = (secondbyteSYNC & 112) >> 4 #112 = 01110000b
    # frameType=  bin2dec([num2str(bitget(rdSYNC(2),7))...
    #         num2str(bitget(rdSYNC(2),6))...
    #         num2str(bitget(rdSYNC(2),5))]);

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

    #version del protocolo
    #Bits 3–0: Version number, in binary (1–15), version 1 for this initial
    #publication.

    #Primeros 4 bits del secondbyteSYNC
    protocolversion = secondbyteSYNC & 15 #00001111b = 15

    #print('Dataframe type: {} '.format(strframetype))
    #print('Protocol version: {}'.format(protocolversion))

    ###############################################################
    #                    2 FRAMESIZE 2 bytes                      #
    ###############################################################
    #       Total number of bytes in the frame, including CHK.    #
    #          16-bit unsigned number. Range = maximum 65535.     #
    #                                                             #
    ###############################################################
    FRAMESIZEread = cgf2frame[2:4]
    #Este el número de bytes recibidos en formato decimal
    #lee dos bytes, y lo convierte de word a decimal con formato "big endian"
    decFRAMESIZE = int.from_bytes(FRAMESIZEread,'big')
    #print('Framesize: {}'.format( decFRAMESIZE))

    ###############################################################
    #                    3 IDCODE (2 bytes)                       #
    ###############################################################
    # PMU/DC ID number, 16-bit integer, assigned by user,         #
    # 1 to 65 534 (0 and# 65 535 are reserved).                   #
    # Identifies device sending and receiving messages.           #
    ###############################################################
    IDCODEread = cgf2frame[4:6]
    #convertir de word (2 bytes) a entero, big endian
    decIDCODE = int.from_bytes(IDCODEread,'big')
    #print('IDCODE: {}'.format(decIDCODE))

    ################################################################################
    #                               4 SOC (4 bytes)                              #
    ################################################################################
    # Time stamp, 32-bit unsigned number, SOC count starting at midnight           #
    # 01-Jan-1970 (UNIX time base).                                                #
    # Ranges 136 yr, rolls over 2106 AD.                                           #
    # Leap seconds are not included in count, so each year has the same number of  #
    # seconds except leap years, which have an extra day (86 400 s).               #
    ################################################################################
    SOCread = cgf2frame[6:10]
    #SOC en formato decimal, convertir 4 bytes a entero, big endian
    decSOC = int.from_bytes(SOCread,'big')
    #print('SOC: {}'.format(decSOC))

    #################################################################################
    #                              5  FRACSEC (4 bytes)                              #
    #################################################################################
    # Fraction of Second and Time Quality, time of measurement for data frames      #
    # or time of frame transmission for non-data frames.                            #
    # Bits 31–24: Time Quality as defined in 6.2.2.                                 #
    # Bits 23–00: Fraction-of-second, 24-bit integer number. When divided by        #
    # TIME_BASE yields the actual fractional second. FRACSEC used in all            #
    # messages to and from a given PMU shall use the same TIME_BASE that is         #
    # provided in the configuration message from that PMU.                          #
    #################################################################################
    #falta probar el orden de los bits
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


    #print('FRACSEC: {}'.format(decFRACSEC))

    ##########################################################################
    #                         6 TIME_BASE (4 bytes)                                   #
    ##########################################################################
    # Resolution of fraction-of-second time stamp.                           #
    ##########################################################################
    TIME_BASEread = cgf2frame[14:18]
    #TIME_BASE en formato decimal, convertir 4 bytes a entero, big endian
    decTIME_BASE = int.from_bytes(TIME_BASEread,'big')
    #print('TIME_BASE: {}'.format(decTIME_BASE))

    #############################################################
    #                     7 NUM_PMU (2 bytes)                   #
    #############################################################
    # The number of PMUs included in the data frame.            #
    #############################################################
    NUM_PMUread = cgf2frame[18:20]
    decNUM_PMU = int.from_bytes(NUM_PMUread,'big')
    #print('Numero de PMUs incluidos en el dataframe: {}'.format(decNUM_PMU))

    ########################################################
    #                     8 STN (16 bytes)                 #
    ########################################################
    # Station Name—16 bytes in ASCII format.               #
    ########################################################
    STNread = cgf2frame[20:36]
    #print('Station name: {}'.format(STNread))

    ##################################################################
    #                      9 IDCODE (2 bytes)                        #
    ##################################################################
    # PMU ID number as above, identifies source of each data block.  #
    ##################################################################
    #idcode de donde vienen los datos
    IDCODESRCread = cgf2frame[36:38]
    decIDCODESRC = int.from_bytes(IDCODESRCread,'big')
    #print('IDCODE de la fuente: {}'.format(decIDCODESRC))

    ###################################################################
    #                      10 FORMAT (2 bytes)                        #
    ###################################################################
    # Data format within the data frame.                              #
    # Data format in data frames, 16-bit flag.                        #
    # Bits 15–4: Unused                                               #
    # Bit 3: 0 = FREQ/DFREQ 16-bit integer, 1 = floating point        #
    # Bit 2: 0 = analogs 16-bit integer, 1= floating point            #
    # Bit 1: 0 = phasors 16-bit integer, 1 = floating point           #
    # Bit 0: 0 = phasor real and imaginary (rectangular),             #
    # 1 = magnitude and angle (polar)                                 #
    ###################################################################
    FORMATread = cgf2frame[38:40]

    FRMTbit3 = (FORMATread[1] & 8) >> 3
    FRMTbit2 = (FORMATread[1] & 4) >> 2
    FRMTbit1 = (FORMATread[1] & 2) >> 1
    FRMTbit0 = (FORMATread[1] & 1)

    if FRMTbit3== 0:
        FORMAT_FREQ_DFREQ = 'int'
        #print('FREQ/DFREQ format: integer')

    elif FRMTbit3 ==1:
        FORMAT_FREQ_DFREQ = 'float'
        #print('FREQ/DFREQ format: floating point')

    if FRMTbit2 ==0:
        FORMAT_ANALOG = 'int'
        #print('Analog values format: integer')

    elif FRMTbit2 ==1:
        FORMAT_ANALOG = 'float'
        #print('Analog values format: floating point')

    if FRMTbit1 ==0:
        FORMAT_PHASOR = 'int'
        #print('Phasor format: integer')

    elif FRMTbit1 ==1:
        FORMAT_PHASOR = 'float'
        #print('Phasor format: floating point')

    if FRMTbit2 ==0:
        PHASOR_NOTATION = 'rectangular'
        #print('Phasor notation: rectangular')

    elif FRMTbit2 ==1:
        PHASOR_NOTATION = 'polar'
        #print('Phasor notation: polar')

        ####################################################################
    #                   11 PHNMR (2 bytes)                             #
    ####################################################################
    # Number of phasors—2-byte integer (0 to 32 767).                  #
    ####################################################################
    PHNMRread = cgf2frame[40:42]
    decPHNMR = int.from_bytes(PHNMRread,'big')
    #print('Number of phasors: {}'.format(decPHNMR))

    #####################################################################
    #                        12 ANNMR (2 bytes)                          #
    #####################################################################
    # Number of analog values—2-byte integer.                           #
    #####################################################################
    ANNMRread = cgf2frame[42:44]
    decANNMR = int.from_bytes(ANNMRread,'big')
    #print('Number of analog values: {}'.format(decANNMR))

    #########################################################
    #                 13 DGNMR (2 bytes)                    #
    #########################################################
    # Number of digital status words—2-byte integer.        #
    #########################################################
    DGNMRread = cgf2frame[44:46]
    decDGNMR = int.from_bytes(DGNMRread,'big')
    #print('Number of digital status words: {}'.format(decDGNMR))

    ###############################################################################
    #       14 CHNAM (16 × (PHNMR+ ANNMR +16 ×DGNMR))                             #
    ###############################################################################
    # Phasor and channel names—16 bytes for each phasor, analog, and              #
    # each digital channel (16 channels in each digital word) in ASCII            #
    # format in the same order as they are transmitted. For digital channels,     #
    # the channel name order will be from the least significant to the most       #
    # significant. (The first name is for Bit 0 of the first 16-bit status word,  #
    # the second is for Bit 1, etc., up to Bit 15. If there is more than 1 digital#
    # status, the next name will apply to Bit 0 of the 2nd word and so on).       #
    ###############################################################################
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
    #DIGITALLABELS = [x.decode('utf-8') for x in listCHNAM[decPHNMR+decANNMR:decPHNMR+decANNMR + decDGNMR*16] ]

    #imprimir nombres
    #print('Phasor names:')
    #for i in PHASORNAMES:
    #    print(i)
    #print('Analog values:')
    #for i in ANALOGNAMES:
    #    print(i)
    #print ('Digital status labels')
    #for i in DIGITALLABELS:
    #    print(i)

    ##############################################################################################
    #               15 PHUNIT (4 × PHNMR)                                                        #
    ##############################################################################################
    # Conversion factor for phasor channels. Four bytes for each phasor.                         #
    # Most significant byte: 0 = voltage; 1 = current.                                           #
    # Least significant bytes: An unsigned 24-bit word in 10 –5 V or amperes per bit to          #
    # scale 16-bit integer data. (If transmitted data is in floating-point format, this 24-bit   #
    # value should be ignored.)                                                                  #
    #############################################################################################
    #para no estar haciendo la suma, creo la variable PHUNITinitbyte
    #es el numero de byte del cgf2frame donde empieza el PHUNIT
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
        #factor = int.from_bytes(listPHUNIT[i][1:4],'big')
        #print('#{} factor: {} * 10^-5, unit: {}'.format(i+1,factor,unit))

    #####################################################################################
    #                                     16 ANUNIT (4XANNMR)                           #
    #####################################################################################
    # Conversion factor for analog channels. Four bytes for each analog value.          #
    # Most significant byte: 0 = single point-on-wave, 1 = rms of analog input,         #
    # 2 = peak of analog input, 5–64 = reserved for future definition; 65–255 = user    #
    # definable.                                                                        #
    # Least significant bytes: A signed 24-bit word, user-defined scaling.              #
    #####################################################################################
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
        #value = int.from_bytes(listANUNIT[i][1:4],'big')
        #print('Factor for analog value #{}: {}, value: {}'.format(i+1,factor,value))

    ############################################################################################
    #                                   17 DIGUNIT (4 X DGNMR)                                 #
    ############################################################################################
    # Mask words for digital status words. Two 16-bit words are provided for each              #
    # digital word. The first will be used to indicate the normal status of the digital in-    #
    # puts by returning a 0 when exclusive ORed (XOR) with the status word. The                #
    # second will indicate the current valid inputs to the PMU by having a bit set in          #
    # the binary position corresponding to the digital input and all other bits set to 0.      #
    ############################################################################################

    numbytesDIGUNIT = 4*decDGNMR
    DIGUNITendbyte = ANUNITendbyte + numbytesDIGUNIT
    DIGUNITread = cgf2frame[ANUNITendbyte:DIGUNITendbyte]
    listslice = list(range(0, int(numbytesDIGUNIT+4),4) )#4 bytes en pasos de 4 bytes
    listDIGUNIT = []
    for i in range(len(listslice)-1):
        #lista completa los factores de conversion
        listDIGUNIT.append(DIGUNITread[listslice[i]:listslice[i+1]])

    #########################################################
    #                18 FNOM (2 bytes)
    #########################################################
    # Nominal line frequency code (16-bit unsigned integer)
    # Bits 15–1: Reserved
    # Bit 0: 1: Fundamental frequency = 50 Hz
    # 0: Fundamental frequency = 60 Hz
    #########################################################
    FNOMendbyte = DIGUNITendbyte +2
    FNOMread = cgf2frame[DIGUNITendbyte:FNOMendbyte]

    FNOMbit0 = FNOMread[0]  & 1
    if FNOMbit0 == 1:
        decFNOM = 50
    elif FNOMbit0==0:
        decFNOM = 60
    #print('Nominal line frequency: {}'.format(decFNOM))

    ##########################################
    # 19 CFGCNT (2 bytes)
    ################################################
    # Configuration change count is incremented each time a change is made in the
    # PMU configuration. 0 is the factory default and the initial value.
    ######################################################################
    CFGCNTendbyte = FNOMendbyte +2
    CFGCNTread = cgf2frame[FNOMendbyte:CFGCNTendbyte]
    decCFGCNT = int.from_bytes(CFGCNTread,'big')

    #print('Configuration change count: {}'.format(decCFGCNT))

    #como es un solo pmu me salto la parte de
    #Fields 8–18, repeated for as many PMUs as in field 7 (NUM_PMU)."repeat 8-19"
    #######################################################
    # 20+ DATA_RATE (2 bytes)
    ####################################################
    # Rate of phasor data transmissions—2-byte integer word (–32 767 to +32 767)
    # If DATA_RATE > 0, rate is number of frames per second.
    # If DATA_RATE < 0, rate is negative of seconds per frame.
    # For example: DATA_RATE = 15 is 15 frames per second and DATA_RATE =
    # –5 is 1 frame per 5 s.
    ####################################################################################
    DATA_RATEendbyte = CFGCNTendbyte + 2
    DATA_RATEread = cgf2frame[CFGCNTendbyte:DATA_RATEendbyte]
    decDATA_RATE = int.from_bytes(DATA_RATEread,'big')
    #if decDATA_RATE  > 0:
    #    print('{} frame(s) per second'.format(decDATA_RATE))
    #elif decDATA_RATE < 0:
    #    print('1 frame per {} seconds'.format(decDATA_RATE))
    assert decDATA_RATE !=0, 'DATA_RATE cannot be zero'

    ######################################################
    #                  21+ CHK (2 bytes)                 #
    #####################################################
    # CRC-CCITTT
    #####################################################
    CHKendbyte = DATA_RATEendbyte + 2
    CHKread = cgf2frame[DATA_RATEendbyte:CHKendbyte]
    decCHK = int.from_bytes(CHKread,'big')
    #print('CRC: {}'.format(hex(decCHK)))

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
