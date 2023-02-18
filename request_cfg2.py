# -*- coding: utf-8 -*-
#useful with raspberry pi
import time
import math
from get_crc16 import get_crc16 #own function

def request_cfg2(sockobj,idcode,buffersize=2048):
    '''
        Request the configuration frame 2 to the PMU. Needs the get_crc16
        function that i wrote.

        Parameters
        ----------
        sockobj: socket
            Socket stream where the cfg2 dataframe will come from. The Socket
            should have been opened before, and it should be connected to
            the PMU.

        idcode: int
            IDCODE of the PMU.

        buffersize: int
            Number of bytes that will be received from the socket stream.

        Returns
        -------
            bytearray
            Returns the configuration frame 2 data in form of bytearray.
    '''

    #if you use wireshark, you need to ask first for the cfg2 frame
    #and mantain the socket connection open. wireshark uses this information
    # to decode the dataframes
    #send get cfg2 command
    # 1 field SYNC
    field1_1 = 170#AA.
    field1_2 = 65 #0-reservado100-data frame comando0001-2005
    #2 FRAMESIZE
    field2_1 =0  #el tamaño siempre es 18 incluyendo los dos bits del CHK
    field2_2=18
    # 3 field IDCODE
    #dividir en dos bytes y hacer un bitshift 8 lugares a la derecha
    #field3_1 = idcode >> 8
    #field3_2 = idcode & 255 #quedaria 00000001 para un idcode=1
    [field3_1, field3_2] = int(idcode).to_bytes(2,'big')
    #4 SOC
    #send unix time
    PCtime = time.time()
    t =int(PCtime).to_bytes(4,'big')
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
    field6_1 = 0 #primer byte es cero
    field6_2= 5 #00000101- comandoget CFG2
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
    #mensaje con los datos del CFG2 que seran enviados
    message = messnoCHK.copy()
    message.append(crcbyte1)
    message.append(crcbyte2)
    message_bytearr = bytearray(message)

    sockobj.send(message_bytearr)
    #data received
    return sockobj.recv(buffersize)
