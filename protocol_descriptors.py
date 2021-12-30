from crc import CrcCalculator, Crc16
import socket

MESSAGE_TYPES = {'file_request': 1,
                 'file_request_successful': 2, 
                 'file_request_unsuccessful': 3,
                 'file_start_transfer': 4,
                 'file_data_sent': 5,
                 'file_data_acknowledge': 6}
                 # THERE IS CURRENLY LIMIT FOR 9 MESSAGE TYPES

HEADER_SIZE = 16
BODY_END_CRC_LENGTH = 16
FILE_REQUEST_BODY_SIZE_FILENAME_LEN = 256
FILE_REQUEST_BODY_SIZE = FILE_REQUEST_BODY_SIZE_FILENAME_LEN+BODY_END_CRC_LENGTH
FILE_REQUEST_SUCCESSFUL_BODY_SIZE = 64+BODY_END_CRC_LENGTH
FILE_REQUEST_UNSUCCESSFUL_BODY_SIZE = 8+BODY_END_CRC_LENGTH
FILE_START_TRANSFER_BODY_SIZE = 8+BODY_END_CRC_LENGTH
FILE_DATA_MAX_TRANSFER_SIZE = 1008
FILE_DATA_MAX_BODY_SIZE = FILE_DATA_MAX_TRANSFER_SIZE+BODY_END_CRC_LENGTH
FILE_DATA_TRANSFER_ACKNOWLEDGE = 8+BODY_END_CRC_LENGTH
FILE_DATA_HEADER_TRANSFER_WINDOW_START_IDX = 2
FILE_DATA_HEADER_TRANSFER_WINDOW_MAX_LEN = 6
FILE_DATA_HEADER_BODY_LEN_START_IDX = 8
FILE_DATA_HEADER_MAX_BODY_LEN = 8
FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_MAX_NUM_SIZE = 6
FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_HEADER_START_IDX = 2
MAX_BUFFER_SIZE = 2*(HEADER_SIZE+FILE_DATA_MAX_BODY_SIZE)

#
SOCKET_TIMEOUT = 10

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
    
def get_crc(bytes_data):
    ''' Calculates crc16 and returns int crc value
        most likely of limit python int16 ~10 digits '''
    crc_calculator = CrcCalculator(Crc16.CCITT, True)
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
    crc_str_value = str(crc_value)
    print(f"SENDING CRC: {crc_str_value}")
    if not len(crc_str_value) <= BODY_END_CRC_LENGTH: 
        print(f"ERROR: ERROR in append_crc_to_message(), name {crc_str_value} len: {len(crc_str_value)} too long for body")
        return False
    start_idx_crc = len(message) - BODY_END_CRC_LENGTH
    for crc_char_idx, crc_char in enumerate(crc_str_value):
        message[start_idx_crc+crc_char_idx] = ord(crc_char)
    # write crc at the end of the body
    #print(f"message len at the end {len(message)}")
    return message

def check_crc_received_message(message):
    ''' This function takes as an argument whole received message
    with included crc. Calculated crc from stripped message (without crc)
    and compares it to the crc in the message. '''
    # Crc value from stripped message
    crc_value = get_crc(bytes(message[:-BODY_END_CRC_LENGTH]))
    #print(f"calculated crc: {crc_value}")
    # Get parsed crc value 
    parsed_crc_value = '0'
    crc_start_idx = len(message) - BODY_END_CRC_LENGTH
    crc_body_info = message[crc_start_idx:]
    #print(f"crc_body_info len: {len(crc_body_info)}")
    crc_body_info = parse_data_one(data=crc_body_info)
    for crc_int_char in crc_body_info:
        if crc_int_char == 0:
            break
        #print(f"crc_int_char: {crc_int_char}")
        parsed_crc_value = parsed_crc_value + str(chr(crc_int_char))
    #print(f"parsed_crc_value: {parsed_crc_value}")
    parsed_crc_value = int(parsed_crc_value)

    print(f"crc_value == parsed_crc_value: {crc_value} == {parsed_crc_value}")
    if crc_value == parsed_crc_value:
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