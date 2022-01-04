import socket
import os
from os import path
import numpy as np
import sys
from crc import CrcCalculator, Crc16
from protocol_descriptors import HASH_LENGTH, MESSAGE_TYPES, FILE_REQUEST_SUCCESSFUL_BODY_SIZE, FILE_REQUEST_UNSUCCESSFUL_BODY_SIZE, HEADER_SIZE, FILE_REQUEST_BODY_SIZE, FILE_START_TRANSFER_BODY_SIZE, FILE_DATA_TRANSFER_ACKNOWLEDGE, FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_MAX_NUM_SIZE, FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_HEADER_START_IDX, FILE_DATA_MAX_TRANSFER_SIZE, FILE_DATA_HEADER_BODY_LEN_START_IDX, FILE_DATA_HEADER_MAX_BODY_LEN, FILE_DATA_HEADER_TRANSFER_WINDOW_START_IDX, FILE_DATA_HEADER_TRANSFER_WINDOW_MAX_LEN, FILE_REQUEST_BODY_SIZE_FILENAME_LEN,BODY_END_CRC_LENGTH
from protocol_descriptors import pop_zeros, get_hash, get_crc, append_crc_to_message, check_crc_received_message
from protocol_descriptors import PARSE_RETURNS

class UDPFile_receiver:
    def __init__(self, receiver_directory, path_to_file):
        self.receiver_directory = receiver_directory
        self.path_to_file = path_to_file
        self.file_name = self.path_to_file.split('/')[-1]
        # Constants
        self.header_size = HEADER_SIZE # Bytes
        self.file_byte_size = 0
        # HASH variables
        self.calculated_hash = b'1'
        self.received_hash = b'0'

    def parse_data(self, data, int_format=True):
        ''' Parse data to int array and return header and body. '''
        data_array = []
        for byte_idx, byte in enumerate(data):
            if int_format: 
                data_array.append(int(byte))
            else:
                data_array.append(byte)

        header = data_array[0:HEADER_SIZE]
        body =   data_array[HEADER_SIZE:]

        return header, body

    def create_and_save_hashes(self, hash, file_data):
        self.received_hash = hash
        self.calculated_hash = get_hash(bytes_data=file_data)
        return

    def parse_file_request_response(self, data):
        ''' Parse received file request response message from receiver application
            to body and header -> extract file size and return True if
            file was found else return False '''

        header, body = self.parse_data(data)
        ret_dict = {}

        # NET DERPER CHANGES FIRST NUM TO CHAR
        if not str(chr(header[0])).isnumeric():
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict

        message_type = int(str(chr(header[0])))
        if ord(chr(message_type)) != MESSAGE_TYPES['file_request_successful'] and ord(chr(message_type )) != MESSAGE_TYPES['file_request_unsuccessful'] : 
            print(f'ERROR in parse_file_request_response(): Message type {ord(chr(message_type))} doesn\'t match {MESSAGE_TYPES["file_request_successful"]} or  {MESSAGE_TYPES["file_request_unsuccessful"]}')
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict

        # Check CRC
        if not check_crc_received_message(data):
            ret_dict["return"] = PARSE_RETURNS["wrong_crc"]
            return ret_dict

        file_size = '0'
        print(f"body: {body}")
        # pop_zeros(body)
        for body_int_char in body:
            if body_int_char == 0: break
            print(f"body_int_char: {body_int_char}")
            file_size = file_size + str(chr(body_int_char))
        print(f"file_size: {file_size}")
        self.file_byte_size = int(file_size)

        if ord(chr(message_type )) == MESSAGE_TYPES['file_request_successful']:
            ret_dict["return"] = PARSE_RETURNS["request_successful"]
            return ret_dict
        else:
            ret_dict["return"] =PARSE_RETURNS["request_unsuccessful"]
            return ret_dict

    def parse_file_hash_response(self, data):
        ''' Parse received file hash message from receiver application '''

        header, body = self.parse_data(data)
        ret_dict = {}

        # NET DERPER CHANGES FIRST NUM TO CHAR
        if not str(chr(header[0])).isnumeric():
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict

        message_type = int(str(chr(header[0])))
        if ord(chr(message_type)) != MESSAGE_TYPES['file_hash']: 
            print(f'ERROR in parse_file_hash_response(): Message type {ord(chr(message_type))} doesn\'t match {MESSAGE_TYPES["file_hash"]}')
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict

        # Check CRC
        if not check_crc_received_message(data):
            ret_dict["return"] = PARSE_RETURNS["wrong_crc"]
            return ret_dict

        hash = data[HEADER_SIZE:HEADER_SIZE+HASH_LENGTH]
        ret_dict["return"] = PARSE_RETURNS["request_successful"]
        ret_dict["hash"] = hash
        return ret_dict

    def parse_file_data(self, data):
        ''' Parse received file data from sender application
            to body and header, check corruption as well. '''

        header, skip = self.parse_data(data, int_format=False)
        body = data[HEADER_SIZE:]
        ret_dict = {}
        ret_dict["valid"] = False
        ret_dict["body"] = []
        ret_dict["body_len"] = 0
        ret_dict["parsed_transfer_window_idx"] = 0

        # NET DERPER CHANGES FIRST NUM TO CHAR
        if not str(chr(header[0])).isnumeric():
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict

        message_type = int(str(chr(header[0])))

        if message_type != (MESSAGE_TYPES['file_data_sent']): 
            print(f'ERROR in parse_file_data(): Message type {message_type} doesn\'t match {MESSAGE_TYPES["file_data_sent"]}')
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict
        
        print(f"len of parse file data: {len(data)}")
        # Check CRC
        print(f"CCCHEECK : {np.concatenate((header, skip), axis=None)}")
        print(f"len bytes(data): {len(bytes(data))}")
        if not check_crc_received_message(np.concatenate((header, skip), axis=None)):
            ret_dict["return"] = PARSE_RETURNS["wrong_crc"]
            return ret_dict

        ## GET INFO FROM HEADER
        # Get message window idx
        transfer_window_idx = '0'
        header_transfer_window_idx = header[FILE_DATA_HEADER_TRANSFER_WINDOW_START_IDX:FILE_DATA_HEADER_TRANSFER_WINDOW_START_IDX+FILE_DATA_HEADER_TRANSFER_WINDOW_MAX_LEN]
        pop_zeros(header_transfer_window_idx)
        for header_int_char in header_transfer_window_idx:
            # if header_int_char == 0: break
            print(f"header_int_char: {header_int_char}")
            transfer_window_idx = transfer_window_idx + str(chr(header_int_char))
        print(f"transfer_window_idx: {transfer_window_idx}")
        # Length of data in the body, information is stored in the header
        data_body_len = '0'
        header_body_len_info = header[FILE_DATA_HEADER_BODY_LEN_START_IDX:FILE_DATA_HEADER_BODY_LEN_START_IDX+FILE_DATA_HEADER_MAX_BODY_LEN]
        print(f"received header: {header}")
        print(f"header len: {len(header)}, header_body_len_info len: {len(header_body_len_info)}")
        pop_zeros(header_body_len_info)
        for header_int_char in header_body_len_info:
            # if header_int_char == 0: break
            print(f"header_int_char: {header_int_char}")
            data_body_len = data_body_len + str(chr(header_int_char))
        print(f"data_body_len: {data_body_len}")

        ret_dict["valid"] = True
        ret_dict["body"] = body
        ret_dict["body_len"] = int(data_body_len)
        ret_dict["parsed_transfer_window_idx"] = int(transfer_window_idx)
        ret_dict["return"] = PARSE_RETURNS["request_successful"]
        return ret_dict         

    def MESSAGE_check_file_exists(self):
        ''' This function returns byte array of full message
        to be sent as request to check if file exists in the server filesystem,
        in body there is ASCII chars of the file name requested '''
        
        ## Write header
        header = self.get_empty_header(header_byte_size=self.header_size)
        header[0] = ord(str(MESSAGE_TYPES['file_request']))
        
        
        ## Write body
        # write filename
        ASCII_file_name = str(self.path_to_file)
        body = self.get_empty_body(body_byte_size=FILE_REQUEST_BODY_SIZE)#len(ASCII_file_name))
        # Iterate path to file and save the ASCII chars to array
        
        if not len(ASCII_file_name) <= FILE_REQUEST_BODY_SIZE_FILENAME_LEN: 
            print(f"ERROR: ERROR in MESSAGE_check_file_exists(), name {ASCII_file_name} len: {len(ASCII_file_name)} too long for body")
            return False
        for file_char_idx, file_char in enumerate(ASCII_file_name):
            body[file_char_idx] = ord(file_char)
        
        # Write in crc at the end of the body
        message_without_crc = np.concatenate((header, body), axis=None)
        message_with_crc = append_crc_to_message(message_without_crc)
        
        return message_with_crc

    def MESSAGE_start_transfer(self):
        ''' This function returns byte array of full message
        to be sent as request to transfering file data '''
        
        ## Write header
        header = self.get_empty_header(header_byte_size=self.header_size)
        header[0] = ord(str(MESSAGE_TYPES['file_start_transfer']))
        
        ## Write body
        body = self.get_empty_body(body_byte_size=FILE_START_TRANSFER_BODY_SIZE)
        # Iterate path to file and save the ASCII chars to array
        
        # Write in crc at the end of the body
        message_without_crc = np.concatenate((header, body), axis=None)
        message_with_crc = append_crc_to_message(message_without_crc)
        
        return message_with_crc

    def MESSAGE_acknowledge(self, valid, transfer_window_idx):
        ''' This function returns byte array of full message
        to be sent as acknowledge to data transfer '''
        
        ## Write header
        header = self.get_empty_header(header_byte_size=self.header_size)
        header[0] = ord(str(MESSAGE_TYPES['file_data_acknowledge']))
        header[1] = ord('1') if valid else ord('2')
        # Write ascii number of requiered transfer_window_idx to 2-8th byte idx
        # Convert file_byte_size to string and write the values to body
        ASCII_number = str(transfer_window_idx)
        # Check if FILE_REQUEST_SUCCESSFUL_BODY_SIZE is enough
        if not len(ASCII_number) <= FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_MAX_NUM_SIZE: 
            print(f"ERROR: ERROR in MESSAGE_acknowledge(), window of size {len(ASCII_number)} too large for header space {FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_MAX_NUM_SIZE}")
            return False
        for num_idx, num in enumerate(ASCII_number):
            print( ord(num))
            header[num_idx+FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_HEADER_START_IDX] = ord(num)
        print(f"header ACK: {header}")

        ## Write body
        body = self.get_empty_body(body_byte_size=FILE_DATA_TRANSFER_ACKNOWLEDGE)
        # Iterate path to file and save the ASCII chars to array
        
        # Write in crc at the end of the body
        message_without_crc = np.concatenate((header, body), axis=None)
        message_with_crc = append_crc_to_message(message_without_crc)
        
        return message_with_crc

        
    
    def get_empty_header(self, header_byte_size):
        header =  np.zeros((header_byte_size), dtype=np.int8)
        header[:] = ord(chr(0)) # Fill it with NULL's
        return header
    def get_empty_body(self, body_byte_size):
        body =  np.zeros((body_byte_size), dtype=np.int8)
        body[:] = ord(chr(0)) # Fill it with NULL's
        return body
