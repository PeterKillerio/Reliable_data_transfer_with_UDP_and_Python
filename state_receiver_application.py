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
path_to_server_file = 'C:/Users/peter/Desktop/CTU/Fifth_semester/KDS/cvut_kds_semestralni_projekt/python_implementation/v_2_miro_basic/git/CTU_KDS_reliable_udp_file_transfer/sender_server_filesystem/example.jpg'#'example.jpg'
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
                "end_receiver": 7}

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
with open(f'{path_to_receiver_directory}/{UDPFile.file_name}', 'wb') as file:
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
                elif ret_dict["return"] == PARSE_RETURNS["request_successful"]:
                    print(f"body_len: {body_len}")
                    file.write(bytes(body[:body_len]))
                    total_byte_idx = FILE_DATA_MAX_TRANSFER_SIZE*transfer_window_idx + (len(body)-1)
                    if total_byte_idx+1 >= UDPFile.file_byte_size:
                        writing_file = False
                        print(f"total_byte_idx: {total_byte_idx+1} >= UDPFile.file_byte_size: { UDPFile.file_byte_size}")
                    
                    CURRENT_STATE = receiver_states["send_acknowledge_new"]

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
                    file.write(bytes(body[:body_len]))
                    total_byte_idx = FILE_DATA_MAX_TRANSFER_SIZE*transfer_window_idx + (len(body)-1)
                    if total_byte_idx+1 >= UDPFile.file_byte_size:
                        writing_file = False
                        print(f"total_byte_idx: {total_byte_idx+1} >= UDPFile.file_byte_size: { UDPFile.file_byte_size}")
                    
                    CURRENT_STATE = receiver_states["send_acknowledge_new"]
                    continue

        elif CURRENT_STATE == receiver_states["send_acknowledge_new"]:
            transfer_window_idx += 1

            # Sent acknowledge with the transfer_window_idx we want next
            message = UDPFile.MESSAGE_acknowledge(True, transfer_window_idx)
            sock_send.sendto(message, (UDP_IP, UDP_SEND_PORT))
            
            if writing_file:
                CURRENT_STATE = receiver_states["receiving_file_data"]
                continue
            else:
                CURRENT_STATE = receiver_states["end_receiver"]
                continue

        elif CURRENT_STATE == receiver_states["send_acknowledge_current"]:
            # Sent acknowledge with the transfer_window_idx we want next
            message = UDPFile.MESSAGE_acknowledge(False, transfer_window_idx)
            sock_send.sendto(message, (UDP_IP, UDP_SEND_PORT))
            CURRENT_STATE = receiver_states["receiving_file_data"]

        elif CURRENT_STATE == receiver_states["end_receiver"]:
            break







exit()




























# Establish a connection
sock_send = socket.socket(socket.AF_INET, 
                    socket.SOCK_DGRAM) # UDP
sock_receive = socket.socket(socket.AF_INET, 
                    socket.SOCK_DGRAM) # UDP        
sock_receive.bind((UDP_IP, UDP_RECEIVE_PORT))

# Create receiver application object
UDPFile = UDPFile_receiver(receiver_directory=path_to_receiver_directory, path_to_file=path_to_server_file)
# Get UDP message to check if file exsits 
message = UDPFile.MESSAGE_check_file_exists() 
# Send message and wait for response

### Send file request
print(f"Sending data:")
# Resize message for print 
if DEBUG: 
    # print_msg = np.resize(message,(-1,8))
    print(message)
sock_send.sendto(message, (UDP_IP, UDP_SEND_PORT))
print(f'Sent data of size: {len(message)} bytes')

### Wait for response
print('Waiting for file request response...')
while True:
    try:
        data, addr = sock_receive.recvfrom(MAX_BUFFER_SIZE) # Buffer 1024 bytes
        if not data: break
    except socket.timeout as e:
        print(e,f': RECEIVER APPLICATION: Connection timeout {SOCKET_TIMEOUT} seconds')
        sock_receive.close()
        break
    if DEBUG: print(f'Received data: {data}')

    
    # Parse received file request
    print(f'Received data: {data}')
    ret_was_found = UDPFile.parse_file_request_response(data=data)
    print(f'Received file size length: {UDPFile.file_byte_size}')
    
    # if file was found -> return start transfer message
    # else loop
    if ret_was_found == True:
        message = UDPFile.MESSAGE_start_transfer()

        # Send the message
        print(f"Sending start transfer message:")
        # Resize message for print 
        if DEBUG: 
            print_msg = np.resize(message,(-1,8))
            print(print_msg)
        sock_send.sendto(message, (UDP_IP, UDP_SEND_PORT))
        print(f'Sent data of size: {len(message)} bytes')
        
        break
    elif ret_was_found == False:
        print("ERROR: File wasn't found...")
        continue
    elif ret_was_found == -1:
        # Ask again
        message = UDPFile.MESSAGE_check_file_exists() 
        # Send message and wait for response

        ### Send file request
        print(f"Sending data again:")
        # Resize message for print 
        if DEBUG: 
            # print_msg = np.resize(message,(-1,8))
            print(message)
        sock_send.sendto(message, (UDP_IP, UDP_SEND_PORT))
        print(f'Sent data of size: {len(message)} bytes')


# Start accepting the data from the server and write it to the local
# directory
transfer_window_idx = 0
writing_file = True
with open(f'{path_to_receiver_directory}/{UDPFile.file_name}', 'wb') as file:
    while writing_file:
        print(f'Waiting for file data window {transfer_window_idx}...')
        try:
            data, addr = sock_receive.recvfrom(MAX_BUFFER_SIZE) # Buffer 1024 bytes
            if not data: break
        except socket.timeout as e:
            print(e,f': RECEIVER APPLICATION INCOMING DATA: Connection timeout {SOCKET_TIMEOUT} seconds')
            sock_receive.close()
            break

        
        if DEBUG: print(f'Received data: {data}')
        
        # Check if data is corrupted, if not save and increment windows
        valid, body, body_len, parsed_transfer_window_idx = UDPFile.parse_file_data(data=data)
        print(f"parsed transfer_window_idx: {parsed_transfer_window_idx}")
        #print(f"WWWWWWWWWWWBheadY: {data}")
        #print(f"WWWWWWWWWWWBODY: {data[8]}")

        if valid and (parsed_transfer_window_idx == transfer_window_idx):
            print(f"HAAHAA: {len(body[:body_len])}")
            file.write(bytes(body[:body_len]))
            # WORKS BETTER
            #file.write(data[8:UDPFile.file_byte_size+8])

            total_byte_idx = FILE_DATA_MAX_TRANSFER_SIZE*transfer_window_idx + (len(body)-1)

            #print(sys.getsizeof(chr(data[byte_idx]).encode('utf8')))
            #print(chr(data[byte_idx]).encode('utf8'))
            #print(chr(data[-3]).encode('utf8'))

            #file.write(data[start_index:end_index])
            #print(f"body: {bytes(body)}")
            

            if total_byte_idx+1 >= UDPFile.file_byte_size:
                writing_file = False
                print(f"total_byte_idx: {total_byte_idx+1} >= UDPFile.file_byte_size: { UDPFile.file_byte_size}")
                #break
            
            

            transfer_window_idx += 1
        

        # Sent acknowledge with the transfer_window_idx we want next
        message = UDPFile.MESSAGE_acknowledge(valid, transfer_window_idx)
        sock_send.sendto(message, (UDP_IP, UDP_SEND_PORT))
        if DEBUG: print(f"ACKNOWLEDGE message sent for window: {transfer_window_idx}:\n{message}")




    


















# img_data = []
# while True:
#     try:
#         data, addr = sock.recvfrom(4096) # buffer size is 1024 bytes
#         if not data: break
#         # print("received message: %s" % data)
#         img_data.append(data)
#     except socket.timeout as e:
#         print(e,f': no connections after {SOCKET_TIMEOUT} seconds...')
#         sock.close()
#         break

# # Save message as img
# print(f"message length: {len(img_data)}")
# time_now = datetime.now().strftime('%m_%d_%Y_%H_%M_%S') 
# with open(f'{path_to_receiver_directory}/received_{time_now}.jpg', 'wb') as f:
#     for byte_idx, byte in enumerate(img_data):
#         f.write(byte)
