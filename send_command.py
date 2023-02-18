# -*- coding: utf-8 -*-
#useful with raspberry pi

import time
import math
from get_crc16 import get_crc16

def send_command(sockobj,idcode,cmd):
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
    field3_1 = idcode >> 8
    field3_2 = idcode & 255 #quedaria 00000001 para un idcode=1
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
    #mensaje con los datos del CFG2 que seran enviados
    message = messnoCHK.copy()
    message.append(crcbyte1)
    message.append(crcbyte2)
    message_bytearr = bytearray(message)
    sockobj.send(message_bytearr)
