import socket
from datetime import datetime
from protocol_descriptors import HEADER_SIZE, SOCKET_TIMEOUT, MAX_BUFFER_SIZE, FILE_DATA_MAX_TRANSFER_SIZE
from UDPFile_receiver import UDPFile_receiver
import numpy as np
import sys
import select


path_to_receiver_directory = 'receiver_client_filesystem/'
path_to_server_file = 'C:/Users/peter/Desktop/CTU/Fifth_semester/KDS/semestralni_projekt/python_implementation/v_2_miro_basic/sender_server_filesystem/video.mp4'#'example.jpg'
DEBUG = False

# Server IP
UDP_IP = "127.0.0.1"
UDP_RECEIVE_PORT = 5011#5005
UDP_SEND_PORT = 5012 #5006
print(f"UDP target IP: {UDP_IP}")
print(f"UDP send port: {UDP_SEND_PORT}, UDP receive port: {UDP_RECEIVE_PORT}" )

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
