import socket
import os
import numpy as np
from protocol_descriptors import HEADER_SIZE,FILE_REQUEST_BODY_SIZE,SOCKET_FAST_TIMEOUT ,SOCKET_TIMEOUT, MAX_BUFFER_SIZE, FILE_DATA_MAX_TRANSFER_SIZE, FILE_DATA_MAX_BODY_SIZE
from protocol_descriptors import wait_for_response, get_hash
from protocol_descriptors import PARSE_RETURNS
from UDPFile_sender import UDPFile_sender
import sys

path_to_send_directory = 'sender_server_filesystem/' # *** PATH TO FILE SOURCE DIRECTORY ***
DEBUG = False

# Client IP and connection constants
UDP_SEND_IP = "127.0.0.1"  # *** IP ADDRESS TO SEND DATA TO ***
UDP_RECEIVE_IP = "127.0.0.1"  # *** IP ADDRESS TO RECEIVE DATA FROM ***
UDP_RECEIVE_PORT = 5009 # *** PORT TO RECEIVE DATA FROM ***
UDP_SEND_PORT = 5040 # *** PORT TO SEND DATA TO ***
MAX_HASH_SENDS_COUNTER = 50

# Establish a connection
print(f"UDP target IP: {UDP_SEND_IP}")
print(f"UDP send port: {UDP_SEND_PORT}, UDP receive port: {UDP_RECEIVE_PORT}" )
sock_receive = socket.socket(socket.AF_INET, 
                     socket.SOCK_DGRAM)
sock_receive.bind((UDP_RECEIVE_IP, UDP_RECEIVE_PORT))
sock_receive.settimeout(SOCKET_TIMEOUT)
sock_send = socket.socket(socket.AF_INET, 
                     socket.SOCK_DGRAM)
sock_send.settimeout(SOCKET_TIMEOUT)

# Create sender application object
UDPFile = UDPFile_sender()

# States
sender_states = {"file_request_wait": 0, \
                "file_exist_send": 1, \
                "file_start_transfer_wait": 2, \
                "sending_file_data": 3, \
                "wait_for_acknowledge": 4, \
                "calculate_and_send_hash": 5, \
                "end_sender": 6}

CURRENT_STATE = sender_states["file_request_wait"]


# Main while loop
transfering = True
transfer_window_idx = 0
last_transfer_window_idx = -1
last_transfer_successul = True
while True:
    print(f"CURRENT STATE: {CURRENT_STATE}")
    if CURRENT_STATE == sender_states["file_request_wait"]:
        # Wait for response
        print(f"Waiting for response, timeout: {SOCKET_TIMEOUT}...")
        success, data = wait_for_response(sock_receive, timeout=SOCKET_FAST_TIMEOUT)
        
        if not success:
            print("WARNING: file_request_wait: Receiver timed-out...")
            CURRENT_STATE = sender_states["file_request_wait"]
            continue
        else:
            # Parse received file request
            print(f'Received data of len: {len(data)}')
            print(f"Parsing data...")
            ret_dict = UDPFile.parse_file_request(data=data)

            # Parsing ret logic
            if ret_dict["return"] == PARSE_RETURNS["wrong_message_type"] or \
                    ret_dict["return"] == PARSE_RETURNS["wrong_crc"]:
                print(f"WARNING: file_request_wait: ret_dict: wrong_message_type, wrong_crc")
                CURRENT_STATE = sender_states["file_request_wait"]
                continue
            elif ret_dict["return"] == PARSE_RETURNS["request_successful"]:
                CURRENT_STATE = sender_states["file_exist_send"]
                UDPFile.path_to_file = ret_dict["file_path"] 
                continue

    elif CURRENT_STATE == sender_states["file_exist_send"]:

        exists = UDPFile.check_file_existence(path_to_file=UDPFile.path_to_file)
        if exists:
            message = UDPFile.MESSAGE_file_exists()
            CURRENT_STATE = sender_states["file_start_transfer_wait"]
            print(f"File exists...")
        else:
            message = UDPFile.MESSAGE_file_doesnt_exists()
            CURRENT_STATE = sender_states["file_request_wait"]
            print(f"File doesn't exists...")
        
        # Send message
        print(f'Sent data of size: {len(message)} bytes')
        sock_send.sendto(message, (UDP_SEND_IP, UDP_SEND_PORT))

    elif CURRENT_STATE == sender_states["file_start_transfer_wait"]:
        # Wait for response
        print(f"Waiting for response, timeout: {SOCKET_TIMEOUT}...")
        success, data = wait_for_response(sock_receive, timeout=SOCKET_FAST_TIMEOUT)
        
        if not success:
            print("WARNING: file_start_transfer_wait: Receiver timed-out...")
            CURRENT_STATE = sender_states["file_exist_send"]
            continue
        else:
            # Parse received file request
            print(f'Received data of len: {len(data)}')
            print(f"Parsing data...")
            ret_dict = UDPFile.parse_start_transfer(data=data)

            # Parsing ret logic
            if ret_dict["return"] == PARSE_RETURNS["wrong_message_type"] or \
                    ret_dict["return"] == PARSE_RETURNS["wrong_crc"]:
                print(f"WARNING: file_request_wait: ret_dict: wrong_message_type, wrong_crc")
                CURRENT_STATE = sender_states["file_exist_send"]
                continue
            elif ret_dict["return"] == PARSE_RETURNS["request_successful"]:
                CURRENT_STATE = sender_states["sending_file_data"]
                # Read file data into memory
                UDPFile.load_file_data()
                continue

    elif CURRENT_STATE == sender_states["sending_file_data"]:
        iter_start = 0
        iter_end = 0
        
        print(f"transfer_window_idx: {transfer_window_idx}")

        if not (transfering or not last_transfer_successul):
            CURRENT_STATE = sender_states["calculate_and_send_hash"]
            continue

        iter_start = transfer_window_idx*FILE_DATA_MAX_TRANSFER_SIZE
        iter_end = (transfer_window_idx+1)*FILE_DATA_MAX_TRANSFER_SIZE
        if (iter_end+1) >= UDPFile.file_byte_size:
            transfering = False # End transfer
            iter_end = UDPFile.file_byte_size

            print("LAST PACKET")
            print(f"type window: {type(transfer_window_idx)}")
            # Wrap the buffer with appropriate header 
            print(f"file_data[iter_start:iter_end+1] len: {len(UDPFile.file_data[iter_start:iter_end])}")
            print(f"last_transfer_successul: {last_transfer_successul},iter_start:iter_end: {iter_start}:{iter_end}, transfering: {transfering}, UDPFile.file_byte_size: {UDPFile.file_byte_size}")
        
        message = UDPFile.MESSAGE_file_data(body=UDPFile.file_data[iter_start:iter_end], transfer_window_idx=transfer_window_idx)
        sock_send.sendto((message.astype(np.int8)).tobytes(), (UDP_SEND_IP, UDP_SEND_PORT))
        CURRENT_STATE = sender_states["wait_for_acknowledge"]
        continue

    elif CURRENT_STATE == sender_states["wait_for_acknowledge"]:
        # Wait for response
        print(f"Waiting for response, timeout: {SOCKET_TIMEOUT}...")
        success, data = wait_for_response(sock_receive, timeout=SOCKET_FAST_TIMEOUT)
        
        if not success:
            print("WARNING: wait_for_acknowledge: Receiver timed-out...")
            CURRENT_STATE = sender_states["sending_file_data"]
            continue
        else:
            # Parse received file request
            print(f'Received data of len: {len(data)}')
            print(f"Parsing data...")
            ret_dict = UDPFile.parse_file_acknowledge(data=data)
            
            # Parsing ret logic
            if ret_dict["return"] == PARSE_RETURNS["wrong_message_type"] or \
                    ret_dict["return"] == PARSE_RETURNS["wrong_crc"]:
                print(f"WARNING: file_request_wait: ret_dict: wrong_message_type, wrong_crc")
                CURRENT_STATE = sender_states["sending_file_data"]
                continue
            elif ret_dict["return"] == PARSE_RETURNS["request_successful"]:
                CURRENT_STATE = sender_states["sending_file_data"]    
                parsed_transfer_window_idx = ret_dict["transfer_window_idx"]
                transfer_window_idx = parsed_transfer_window_idx
                continue

    elif CURRENT_STATE == sender_states["calculate_and_send_hash"]:
        if MAX_HASH_SENDS_COUNTER <= 0:
            print(f"INFO: Sent maximum number of hash messages...")
            CURRENT_STATE = sender_states["end_sender"]
        else:
            MAX_HASH_SENDS_COUNTER -= 1

        # Change to faster timeout
        sock_send.settimeout(SOCKET_FAST_TIMEOUT)
        sock_receive.settimeout(SOCKET_FAST_TIMEOUT)

        calculated_hash = get_hash(bytes_data=UDPFile.file_data)
        print(f"calculated_hash: {calculated_hash}")
        message = UDPFile.MESSAGE_hash(hash=calculated_hash)
        
        # Send message
        print(f'Sent data of size: {len(message)} bytes')
        sock_send.sendto(message, (UDP_SEND_IP, UDP_SEND_PORT))

    elif CURRENT_STATE == sender_states["end_sender"]:
        print("Closing sender...")
        ## Currently the sender can get into infinite loop if he doesnt get
        # ack on last packet !!!

        ##
        break

