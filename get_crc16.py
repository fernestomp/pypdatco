import crcmod
def get_crc16(mess):
    '''
        Function used to calculate the CRC16 used to check the itegrity of
        the C37.118 dataframes. It uses the crcmod with the following poly
        function: g(x)=x^16+x^12+x^5+1 -- > 0x11021--> 10001000000100001b

        Parameters
        ----------
        mess: bytearray
            Message used to calculate the CRC16 number.

        Returns
        -------
        int
            Returns thre numbers, the first number is the first byte of the
            CRC16 number, the second number is the second byte of the
            CRC16 number and the third number is the CRC16 number
    '''
    #future implementations should use an own crc16 algorithm to avoid
    #the instalation of the crcmod module
    #this arguments are taken from the crcmod documentation table (0x11021)
    crc16_func = crcmod.mkCrcFun(0x11021, initCrc=0xFFFF, xorOut=0x0000,rev=False)
    crc16val = crc16_func(mess)#valor de crc16
    crcbyte1 = (crc16val & 65280) >>8
    crcbyte2 = crc16val & 255
    return crcbyte1,crcbyte2,crc16val
