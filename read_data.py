from get_crc16 import get_crc16 #own function

def read_data(sockobj,buffersize=2048):
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
    data = sockobj.recv(buffersize)
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
                    #print('CRC Ok!')
                    #print('Dataframe read:')
                    #print(d)
                    return d, True

                else:
#                     print('Error CRC')
#                     print('data len: {} framesize:{}'.format(len(data),framesize))
#                     print(data.hex())
                    return data, False

        else: #no superimposed dataframes
            #print('Framesize: {}, length of dataframe: {}'.format(framesize,len(data)))
            #print(data)
            #:-2 porque los ultimos bytes son el numero crc
            [_,_,crccalc] =get_crc16(data[:-2])
            crcsrc=int.from_bytes(data[-2:],'big')
            if crccalc==crcsrc:
                #print('CRC Ok!')
                return data, True
            else:
                #print('Error CRC')
                #print(data)
                return data, False
        #print('Dataframe number: {}'.format(dataframenumber))
        #print('------------------------------------------------------------')
#     print(len(data))
#     print('-----------------------------------------------------------------')
#     print(data.hex().upper())
