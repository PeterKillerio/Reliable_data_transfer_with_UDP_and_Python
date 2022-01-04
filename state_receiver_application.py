import socket
from datetime import datetime
from protocol_descriptors import HEADER_SIZE, SOCKET_FAST_TIMEOUT ,SOCKET_TIMEOUT, MAX_BUFFER_SIZE, FILE_DATA_MAX_TRANSFER_SIZE
from protocol_descriptors import wait_for_response
from protocol_descriptors import PARSE_RETURNS
from UDPFile_receiver import UDPFile_receiver
import numpy as np
import sys
import select


path_to_receiver_directory = 'receiver_client_filesystem/'
path_to_server_file = 'C:/Users/peter/Desktop/CTU/Fifth_semester/KDS/cvut_kds_semestralni_projekt/python_implementation/v_2_miro_basic/git/CTU_KDS_reliable_udp_file_transfer/sender_server_filesystem/vir.mp4'#'example.jpg'
DEBUG = False

# Server IP
UDP_IP = "127.0.0.1"
UDP_RECEIVE_PORT =5011 #5011#5005
UDP_SEND_PORT = 5012 #5012#5006
print(f"UDP target IP: {UDP_IP}")
print(f"UDP send port: {UDP_SEND_PORT}, UDP receive port: {UDP_RECEIVE_PORT}" )

# States
receiver_states = {"file_request": 0, \
                "file_request_wait": 1, \
                "file_start_transfer": 2, \
                "file_start_transfer_wait": 3, \
                "receiving_file_data": 4, \
                "send_acknowledge_new": 5, \
                "send_acknowledge_current": 6, \
                "send_last_acknowledge": 7, \
                "waiting_for_hash": 8, \
                "valid_invalid_hash": 9, \
                "end_receiver": 10 }

CURRENT_STATE = receiver_states["file_request"]

# Establish a connection
sock_send = socket.socket(socket.AF_INET, 
                    socket.SOCK_DGRAM) # UDP
sock_send.settimeout(SOCKET_TIMEOUT)
sock_receive = socket.socket(socket.AF_INET, 
                    socket.SOCK_DGRAM) # UDP        
sock_receive.bind((UDP_IP, UDP_RECEIVE_PORT))
sock_receive.settimeout(SOCKET_TIMEOUT)

# Create receiver application object
UDPFile = UDPFile_receiver(receiver_directory=path_to_receiver_directory, path_to_file=path_to_server_file)


# Main while loop
transfer_window_idx = 0
writing_file = True

file = open(f'{path_to_receiver_directory}/{UDPFile.file_name}', 'wb')
file_byte_data = bytearray()

while True:
    print(f"CURRENT STATE: {CURRENT_STATE}")

    if CURRENT_STATE == receiver_states["file_request"]:
        # Get UDP message to check if file exsits 
        message = UDPFile.MESSAGE_check_file_exists() 
        # Send message 
        print("Sent file request message...")
        sock_send.sendto(message, (UDP_IP, UDP_SEND_PORT))
        CURRENT_STATE = receiver_states["file_request_wait"]
        continue 

    elif CURRENT_STATE == receiver_states["file_request_wait"]:
        # Wait for response
        print(f"Waiting for response, timeout: {SOCKET_TIMEOUT}...")
        success, data = wait_for_response(sock_receive, timeout=SOCKET_FAST_TIMEOUT)
        
        if not success:
            print("WARNING: file_request_wait: Receiver timed-out...")
            CURRENT_STATE = receiver_states["file_request"]
            continue
        else:
            # Parse received file request
            print(f'Received data of len: {len(data)}')
            print(f"Parsing data...")
            ret_dict = UDPFile.parse_file_request_response(data=data)

            # Parsing ret logic
            if ret_dict["return"] == PARSE_RETURNS["request_unsuccessful"] or \
                    ret_dict["return"] == PARSE_RETURNS["wrong_message_type"] or \
                    ret_dict["return"] == PARSE_RETURNS["wrong_crc"]:
                print(f"WARNING: file_request_wait: ret_dict: request_unsuccessful, wrong_message_type, wrong_crc")
                CURRENT_STATE = receiver_states["file_request"]
                continue
            elif ret_dict["return"] == PARSE_RETURNS["request_successful"]:
                CURRENT_STATE = receiver_states["file_start_transfer"]
                continue

    elif CURRENT_STATE == receiver_states["file_start_transfer"]:
        # Send start transfer message
        message = UDPFile.MESSAGE_start_transfer()
        # Send the message
        print(f"Sending start transfer message:")
        sock_send.sendto(message, (UDP_IP, UDP_SEND_PORT))
        print(f'Sent data of size: {len(message)} bytes')
        CURRENT_STATE = receiver_states["file_start_transfer_wait"]

    elif CURRENT_STATE == receiver_states["file_start_transfer_wait"]:
        success, data = wait_for_response(sock_receive, timeout=SOCKET_FAST_TIMEOUT)
        
        if not success:
            print("WARNING: file_start_transfer_wait: Receiver timed-out...")
            CURRENT_STATE = receiver_states["file_start_transfer"]
            continue
        else:
            # Parse received file request
            print(f'Received data of len: {len(data)}')
            print(f"Parsing data...")
            ret_dict = UDPFile.parse_file_data(data=data)

            valid = ret_dict["valid"]
            body = ret_dict["body"]
            body_len = ret_dict["body_len"]
            parsed_transfer_window_idx = ret_dict["parsed_transfer_window_idx"]

            # Parsing ret logic
            if ret_dict["return"] == PARSE_RETURNS["wrong_message_type"] :
                print(f"WARNING: file_request_wait: ret_dict: wrong_message_type")
                CURRENT_STATE = receiver_states["file_start_transfer"]
                continue
            elif ret_dict["return"] == PARSE_RETURNS["wrong_crc"]:
                CURRENT_STATE = receiver_states["send_acknowledge_current"]
                continue
            elif ret_dict["return"] == PARSE_RETURNS["request_successful"]  and parsed_transfer_window_idx == transfer_window_idx:
                print(f"body_len: {body_len}")

                # file.write(bytes(body[:body_len]))
                file_byte_data.extend(bytearray(bytes(body[:body_len]))) 

                total_byte_idx = FILE_DATA_MAX_TRANSFER_SIZE*transfer_window_idx + (len(body)-1)
                if total_byte_idx+1 >= UDPFile.file_byte_size:
                    writing_file = False
                    print(f"total_byte_idx: {total_byte_idx+1} >= UDPFile.file_byte_size: { UDPFile.file_byte_size}")
                
                CURRENT_STATE = receiver_states["send_acknowledge_new"]
                continue
            else:
                CURRENT_STATE = receiver_states["send_acknowledge_current"]
                continue


    elif CURRENT_STATE == receiver_states["receiving_file_data"]:
        success, data = wait_for_response(sock_receive, timeout=SOCKET_FAST_TIMEOUT)
        print(f"transfer_window_idx: {transfer_window_idx}")
        
        if not success:
            print("WARNING: receiving_file_data: Receiver timed-out...")
            CURRENT_STATE = receiver_states["send_acknowledge_current"]
            continue
        else:
            # Parse received file request
            print(f'Received data of len: {len(data)}')
            print(f"Parsing data...")
            ret_dict = UDPFile.parse_file_data(data=data)

            valid = ret_dict["valid"]
            body = ret_dict["body"]
            body_len = ret_dict["body_len"]
            parsed_transfer_window_idx = ret_dict["parsed_transfer_window_idx"]

            # Parsing ret logic
            if ret_dict["return"] == PARSE_RETURNS["wrong_message_type"] :
                print(f"WARNING: ret_dict: wrong_message_type")
                CURRENT_STATE = receiver_states["send_acknowledge_current"]
                continue
            elif ret_dict["return"] == PARSE_RETURNS["wrong_crc"] or not valid:
                CURRENT_STATE = receiver_states["send_acknowledge_current"]
                continue
            elif ret_dict["return"] == PARSE_RETURNS["request_successful"] and parsed_transfer_window_idx == transfer_window_idx:
                
                # file.write(bytes(body[:body_len]))
                file_byte_data.extend(bytearray(bytes(body[:body_len]))) #############################
                
                total_byte_idx = FILE_DATA_MAX_TRANSFER_SIZE*transfer_window_idx + (len(body)-1)
                if total_byte_idx+1 >= UDPFile.file_byte_size:
                    writing_file = False
                    print(f"total_byte_idx: {total_byte_idx+1} >= UDPFile.file_byte_size: { UDPFile.file_byte_size}")
                
                CURRENT_STATE = receiver_states["send_acknowledge_new"]
                continue
            else:
                CURRENT_STATE = receiver_states["send_acknowledge_current"]
                continue

    elif CURRENT_STATE == receiver_states["send_acknowledge_new"]:
        transfer_window_idx += 1

        # Sent acknowledge with the transfer_window_idx we want next
        message = UDPFile.MESSAGE_acknowledge(True, transfer_window_idx)
        sock_send.sendto(message, (UDP_IP, UDP_SEND_PORT))
        
        if writing_file: CURRENT_STATE = receiver_states["receiving_file_data"]
        else: CURRENT_STATE = receiver_states["send_last_acknowledge"]

        continue

    elif CURRENT_STATE == receiver_states["send_acknowledge_current"]:
        # Sent acknowledge with the transfer_window_idx we want next
        message = UDPFile.MESSAGE_acknowledge(False, transfer_window_idx)
        sock_send.sendto(message, (UDP_IP, UDP_SEND_PORT))
        CURRENT_STATE = receiver_states["receiving_file_data"]
        
    elif CURRENT_STATE == receiver_states["send_last_acknowledge"]:
        transfer_window_idx += 1

        # Sent acknowledge with the transfer_window_idx we want next
        message = UDPFile.MESSAGE_acknowledge(True, transfer_window_idx)
        sock_send.sendto(message, (UDP_IP, UDP_SEND_PORT))

        CURRENT_STATE = receiver_states["waiting_for_hash"]
        continue

    elif CURRENT_STATE == receiver_states["waiting_for_hash"]:
        # Wait for response
        print(f"Waiting for response, timeout: {SOCKET_TIMEOUT}...")
        success, data = wait_for_response(sock_receive, timeout=SOCKET_FAST_TIMEOUT)
        
        if not success:
            print("WARNING: waiting_for_hash: Receiver timed-out...")
            CURRENT_STATE = receiver_states["send_last_acknowledge"]
            continue
        else:
            # Parse received file request
            print(f'Received data of len: {len(data)}')
            print(f"Parsing data...")
            ret_dict = UDPFile.parse_file_hash_response(data=data)

            # Parsing ret logic
            if ret_dict["return"] == PARSE_RETURNS["request_unsuccessful"] or \
                    ret_dict["return"] == PARSE_RETURNS["wrong_message_type"] or \
                    ret_dict["return"] == PARSE_RETURNS["wrong_crc"]:
                print(f"WARNING: waiting_for_hash: ret_dict: request_unsuccessful, wrong_message_type, wrong_crc")
                CURRENT_STATE = receiver_states["send_last_acknowledge"]
                continue
            elif ret_dict["return"] == PARSE_RETURNS["request_successful"]:
                # UDPFile has 2 variables, received_hash, calculated_hash
                UDPFile.create_and_save_hashes(hash=ret_dict["hash"], file_data=file_byte_data)
                CURRENT_STATE = receiver_states["valid_invalid_hash"]
                continue

    elif CURRENT_STATE == receiver_states["valid_invalid_hash"]:
        # Create logic on valid/invalid hash
        print(f"UDPFile.calculated_hash: {UDPFile.calculated_hash}, UDPFile.received_hash: {UDPFile.received_hash}")
        if UDPFile.calculated_hash == UDPFile.received_hash:
            print(f"Hashes are matching...")
        else:
            print(f"Hashes are not matching...")
        CURRENT_STATE = receiver_states["end_receiver"]

    elif CURRENT_STATE == receiver_states["end_receiver"]:
        print("INFO: Ending receiver...")
        break

file.write(file_byte_data)
file.close()


exit()

