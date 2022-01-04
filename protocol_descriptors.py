from crc import CrcCalculator, Crc64
import hashlib
import numpy as np
import socket

MESSAGE_TYPES = {'file_request': 1,
                 'file_request_successful': 2, 
                 'file_request_unsuccessful': 3,
                 'file_start_transfer': 4,
                 'file_data_sent': 5,
                 'file_data_acknowledge': 6,
                 'file_hash': 7}
                 # THERE IS CURRENLY LIMIT FOR 9 MESSAGE TYPES

PARSE_RETURNS = {"request_successful": 0, "request_unsuccessful": 1, "wrong_message_type": 2, "wrong_crc": 3}


HEADER_SIZE = 16
BODY_END_CRC_LENGTH = 16
HASH_LENGTH = 16
FILE_REQUEST_BODY_SIZE_FILENAME_LEN = 256
FILE_REQUEST_BODY_SIZE = FILE_REQUEST_BODY_SIZE_FILENAME_LEN+BODY_END_CRC_LENGTH
FILE_REQUEST_SUCCESSFUL_BODY_SIZE = 64+BODY_END_CRC_LENGTH
FILE_REQUEST_UNSUCCESSFUL_BODY_SIZE = 8+BODY_END_CRC_LENGTH
FILE_START_TRANSFER_BODY_SIZE = 8+BODY_END_CRC_LENGTH
FILE_DATA_MAX_TRANSFER_SIZE = 1024-BODY_END_CRC_LENGTH
FILE_DATA_MAX_BODY_SIZE = FILE_DATA_MAX_TRANSFER_SIZE+BODY_END_CRC_LENGTH
FILE_DATA_TRANSFER_ACKNOWLEDGE = 8+BODY_END_CRC_LENGTH
FILE_DATA_HASH_MESSAGE_BODY_SIZE = HASH_LENGTH+BODY_END_CRC_LENGTH
FILE_DATA_HEADER_TRANSFER_WINDOW_START_IDX = 2
FILE_DATA_HEADER_TRANSFER_WINDOW_MAX_LEN = 6
FILE_DATA_HEADER_BODY_LEN_START_IDX = 8
FILE_DATA_HEADER_MAX_BODY_LEN = 8

FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_MAX_NUM_SIZE = 6
FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_HEADER_START_IDX = 2
MAX_BUFFER_SIZE = 2*(HEADER_SIZE+FILE_DATA_MAX_BODY_SIZE)

#
SOCKET_TIMEOUT = 5 # START/DEBUG
SOCKET_FAST_TIMEOUT = 0.1

def pop_zeros(items):
    #print(f"items: {items}")
    while items[-1] == 0:
        if len(items) == 1:
            if items[0] == 0:
                return
        items.pop()

def parse_data_one(data, int_format=True):
    ''' Parse data to int array and return it. '''
    data_array = []
    for byte_idx, byte in enumerate(data):
        if int_format: 
            data_array.append(int(byte))
        else:
            data_array.append(byte)

    return data_array

def get_hash(bytes_data):
    ''' Calculated MD5 hash and returns it '''
    return hashlib.md5(bytes_data).digest()

def get_crc(bytes_data):
    ''' Calculates Crc64 and returns int crc value
        most likely of limit python int16 ~10 digits '''
    crc_calculator = CrcCalculator(Crc64.CRC64, True)
    #print(f"crc calculated from: {bytes_data}")
    return crc_calculator.calculate_checksum(bytes_data) 

def append_crc_to_message(message):
    ''' This function takes message as argument and append a 
        crc value at the designated spot at the end.
        Crc is calculated from the whole message up to the
        mentioned designated spot for crc '''
    crc_value = get_crc(bytes(message[:-BODY_END_CRC_LENGTH]))
    
    print(f"message len at the beginning: {len(message)}")
    # write filename
    crc_byte_value = crc_value.to_bytes(BODY_END_CRC_LENGTH,'big')

    start_idx_crc = len(message) - BODY_END_CRC_LENGTH
    for crc_byte_idx in range(BODY_END_CRC_LENGTH):
        message[start_idx_crc+crc_byte_idx] = crc_byte_value[crc_byte_idx]

    return message

def check_crc_received_message(message):
    ''' This function takes as an argument whole received message
    with included crc. Calculated crc from stripped message (without crc)
    and compares it to the crc in the message. '''
    # Crc value from stripped message
    crc_value = get_crc(bytes(message[:-BODY_END_CRC_LENGTH]))
    crc_byte_value = crc_value.to_bytes(BODY_END_CRC_LENGTH,'big')

    # Read crc byte data from message
    crc_start_idx = len(message) - BODY_END_CRC_LENGTH
    crc_body_body_byte_value = message[crc_start_idx:] #

    if  isinstance(crc_body_body_byte_value, bytes):
        pass
    elif isinstance(crc_body_body_byte_value, np.ndarray):
        print(f"arr.dtype: {crc_body_body_byte_value.dtype}")
        print(f"crc_body_body_byte_value len: {len(crc_body_body_byte_value)}")
        crc_body_body_byte_value = (crc_body_body_byte_value.astype('int8')).tobytes()
        print(f"** crc_body_body_byte_value len: {len(crc_body_body_byte_value)}")
    else:
        print("ERROR: BAD TYPE OF CRC IN check_crc_received_message()")
        exit() 

    print(f"crc_body_body_byte_value: {crc_body_body_byte_value}")
    print(f"crc_body_body_byte_value type: {type(crc_body_body_byte_value)}")
    # print(f"crc_body_body_byte_value type: {type(crc_body_body_byte_value.tobytes())}")
    print(f"crc_byte_value type: {type(crc_byte_value)}")

    print(f"crc_value == parsed_crc_value: {crc_byte_value} == {crc_body_body_byte_value}")
    if crc_byte_value == crc_body_body_byte_value:
        print("Crc is matching")
        return True
    else:
        print("Crc is not matching")
        return False
    

# Wait for response and return data
def wait_for_response(sock, timeout=SOCKET_TIMEOUT):
    sock.settimeout(timeout)
    while True:
        try:
            data, addr = sock.recvfrom(MAX_BUFFER_SIZE) # Buffer 1024 bytes
            if not data: break
        except socket.timeout as e:
            return False, []

        # Return received data
        return True, data