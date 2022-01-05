import socket
import os
from os import path
from crc import CrcCalculator, Crc16
import struct
import numpy as np
from protocol_descriptors import MESSAGE_TYPES, FILE_DATA_HASH_MESSAGE_BODY_SIZE, HASH_LENGTH, FILE_REQUEST_SUCCESSFUL_BODY_SIZE, FILE_REQUEST_UNSUCCESSFUL_BODY_SIZE, HEADER_SIZE, FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_MAX_NUM_SIZE, FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_HEADER_START_IDX, FILE_DATA_HEADER_MAX_BODY_LEN, FILE_DATA_HEADER_BODY_LEN_START_IDX, FILE_DATA_HEADER_TRANSFER_WINDOW_START_IDX, FILE_DATA_HEADER_TRANSFER_WINDOW_MAX_LEN, FILE_REQUEST_BODY_SIZE_FILENAME_LEN,BODY_END_CRC_LENGTH
from protocol_descriptors import pop_zeros, get_crc, append_crc_to_message, check_crc_received_message
from protocol_descriptors import PARSE_RETURNS

class UDPFile_sender:
    def __init__(self):
        # Constants
        self.header_size = HEADER_SIZE # Bytes
        self.file_data = []
    
    def parse_data(self, data):
        ''' Parse data to int array and return header and body. '''
        data_array = []
        for byte_idx, byte in enumerate(data):
            data_array.append(int(byte))
        header = data_array[0:HEADER_SIZE]
        body =   data_array[HEADER_SIZE:]

        return header, body

    def parse_file_request(self, data):
        ''' Parse received file request message from receiver application
            to body and header -> extract file name and return it. '''

        header, body = self.parse_data(data)
        ret_dict = {}

        # NET DERPER CHANGES FIRST NUM TO CHAR
        if not str(chr(header[0])).isnumeric():
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict

        # Check message type
        message_type = int(str(chr(int(header[0]))))
       # print(f"TESTING MESSAGE TYPE : {message_type}, before: {header[0]}")
        if message_type != MESSAGE_TYPES['file_request']: 
            print(f'ERROR in parse_file_request(): Message type {message_type} doesn\'t match {MESSAGE_TYPES["file_request"]}')
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict
        # Check CRC
        if not check_crc_received_message(data):
            ret_dict["return"] = PARSE_RETURNS["wrong_crc"]
            return ret_dict

        file_path = ''
        for body_int_char in body:
            if body_int_char == 0: break
            file_path = file_path + chr(body_int_char)
        
        ret_dict["return"] = PARSE_RETURNS["request_successful"]
        ret_dict["file_path"] = file_path
        return ret_dict

    def parse_start_transfer(self, data):
        header, body = self.parse_data(data)
        ret_dict = {}

        # NET DERPER CHANGES FIRST NUM TO CHAR
        if not str(chr(header[0])).isnumeric():
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict

        message_type = int(str(chr(header[0])))
        if message_type != MESSAGE_TYPES['file_start_transfer']: 
            print(f'ERROR in parse_start_transfer(): Message type {message_type} doesn\'t match {MESSAGE_TYPES["file_start_transfer"]}')
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict
        
        # Check CRC
        if not check_crc_received_message(data):
            ret_dict["return"] = PARSE_RETURNS["wrong_crc"]
            return ret_dict

        ret_dict["return"] = PARSE_RETURNS["request_successful"]
        return ret_dict

    def parse_file_acknowledge(self, data): 
        header, body = self.parse_data(data)
        ret_dict = {}

        # NET DERPER CHANGES FIRST NUM TO CHAR
        if not str(chr(header[0])).isnumeric():
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict

        message_type = int(str(chr(header[0])))
        print(f"message_type: {message_type}")

        valid = True if message_type == MESSAGE_TYPES['file_data_acknowledge'] else False

        if message_type != MESSAGE_TYPES['file_data_acknowledge']: 
            print(f'ERROR in parse_file_acknowledge(): Message type {message_type} doesn\'t match {MESSAGE_TYPES["file_data_acknowledge"]}')
            ret_dict["return"] = PARSE_RETURNS["wrong_message_type"]
            return ret_dict
        
        # Check CRC
        if not check_crc_received_message(data):
            ret_dict["return"] = PARSE_RETURNS["wrong_crc"]
            return ret_dict

        # Parse window idx
        transfer_window_idx = '0'
        print(f"ACK response transfer windows index data: {header[FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_HEADER_START_IDX:FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_HEADER_START_IDX+FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_MAX_NUM_SIZE]}")
        for header_int_char in header[FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_HEADER_START_IDX:FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_HEADER_START_IDX+FILE_DATA_TRANSFER_ACKNOWLEDGE_WINDOW_MAX_NUM_SIZE]:
            if header_int_char == 0: break
            print(f"header_int_char: {header_int_char}")
            transfer_window_idx = transfer_window_idx + chr(header_int_char)
            print(f"transfer_window_idx: {transfer_window_idx}")
        transfer_window_idx = int(transfer_window_idx)

        ret_dict["return"] = PARSE_RETURNS["request_successful"]
        ret_dict["transfer_window_idx"] = transfer_window_idx
        return ret_dict
        
    def load_file_data(self):
        with open(self.path_to_file, 'rb') as file:
            self.file_data = file.read()
        return

    def check_file_existence(self, path_to_file):
        print(f"path_to_file: {path_to_file}")
        if path.exists(path_to_file):
            self.path_to_file = path_to_file
            return True
        else:
            return False
    def MESSAGE_file_exists(self):
        ''' This function returns byte array of full message
        to be sent as response to ~ file exists in server file system '''
        
        # Get file size
        self.file_byte_size = os.path.getsize(self.path_to_file)
        print(f"GETTING FILE SIZE OF : {self.path_to_file}... its: {os.path.getsize(self.path_to_file)}")
        

        ## Write header
        header = self.get_empty_header(header_byte_size=self.header_size)
        header[0] = ord(str(MESSAGE_TYPES['file_request_successful']))
        
        ## Write body
        body = self.get_empty_body(body_byte_size=FILE_REQUEST_SUCCESSFUL_BODY_SIZE)
        # Convert file_byte_size to string and write the values to body
        ASCII_number = str(self.file_byte_size)
        # Check if FILE_REQUEST_SUCCESSFUL_BODY_SIZE is enough
        if not len(ASCII_number) <= FILE_REQUEST_SUCCESSFUL_BODY_SIZE: 
            print("ERROR: ERROR in MESSAGE_file_exists(), file too big for body")
            return False
        for num_idx, num in enumerate(ASCII_number):
            print(f"bbbbbb: {body.shape}")
            body[num_idx] = ord(num)
        
        # Write in crc at the end of the body
        message_without_crc = np.concatenate((header, body), axis=None)
        message_with_crc = append_crc_to_message(message_without_crc)
        
        return message_with_crc

    def MESSAGE_file_doesnt_exists(self):
        ''' This function returns byte array of full message
        to be sent as response to ~ file doesnt exists in server file system '''
        
        ## Write header
        header = self.get_empty_header(header_byte_size=self.header_size)
        header[0] = ord(str(MESSAGE_TYPES['file_request_unsuccessful']))
        
        ## Write body
        body = self.get_empty_body(body_byte_size=FILE_REQUEST_UNSUCCESSFUL_BODY_SIZE)
        
        # Write in crc at the end of the body
        message_without_crc = np.concatenate((header, body), axis=None)
        message_with_crc = append_crc_to_message(message_without_crc)
        
        return message_with_crc

    def MESSAGE_file_data(self, body, transfer_window_idx):
        ''' This function returns wrapped message i.e. header+body 
            for file transfer where body is the file data '''
        
        # Get file size
        self.file_byte_size = os.path.getsize(self.path_to_file)
        
        ## Write header
        # PACKET NUMBER IN HEADER
        header = self.get_empty_header(header_byte_size=self.header_size)
        header[0] = ord(str(MESSAGE_TYPES['file_data_sent']))
        # Save information about transfer window idx in header
        ASCII_number = str(transfer_window_idx)
        # Check if FILE_REQUEST_SUCCESSFUL_BODY_SIZE is enough
        if not len(ASCII_number) <= FILE_DATA_HEADER_TRANSFER_WINDOW_MAX_LEN: 
            print("ERROR: ERROR in MESSAGE_file_data(), packet number too big for header")
            return False
        for num_idx, num in enumerate(ASCII_number):
            # print(f"bbbbbb: {body.shape}")
            header[FILE_DATA_HEADER_TRANSFER_WINDOW_START_IDX+num_idx] = ord(num)
        # BODY SIZE INFO IN HEADER
        # Save information about body size in the header
        ASCII_number = str(len(body))
        # Check if FILE_REQUEST_SUCCESSFUL_BODY_SIZE is enough
        if not len(ASCII_number) <= FILE_DATA_HEADER_MAX_BODY_LEN: 
            print("ERROR: ERROR in MESSAGE_file_data(), body too big for header")
            return False
        for num_idx, num in enumerate(ASCII_number):
            # print(f"bbbbbb: {body.shape}")
            header[FILE_DATA_HEADER_BODY_LEN_START_IDX+num_idx] = ord(num)

        print(f"message file data header: {header}")

        body = [ body[i] for i in range (0, len(body))]
        # body = [body[i:i+1] for i in range(0, len(body), 1)]
        print(f"FFFFFFFFFFFFF: {len(body)}")
        

        
        ## Write in crc at the end of the body
        # Create additional crc empty body
        crc_sufx = self.get_empty_body(body_byte_size=BODY_END_CRC_LENGTH)
        message_without_crc = np.concatenate((header, body), axis=None)
        message_without_crc = np.concatenate((message_without_crc, crc_sufx), axis=None)
        message_with_crc = append_crc_to_message(message_without_crc)
        return message_with_crc
    
    def MESSAGE_hash(self, hash):
        ''' This function returns byte array of full message
        to be sent as response to ~ file exists in server file system '''
        
        ## Write header
        header = self.get_empty_header(header_byte_size=self.header_size)
        header[0] = ord(str(MESSAGE_TYPES['file_hash']))
        
        ## Write body
        body = self.get_empty_body(body_byte_size=FILE_DATA_HASH_MESSAGE_BODY_SIZE)
        # Write hash into the body
        for hash_byte_val_idx in range(HASH_LENGTH):
            body[hash_byte_val_idx] = hash[hash_byte_val_idx]
        
        # Write in crc at the end of the body
        message_without_crc = np.concatenate((header, body), axis=None)
        message_with_crc = append_crc_to_message(message_without_crc)
        
        return message_with_crc
        
    def read_save_binary_data(self, path_to_file):
        # Get file size and initialize an empty array for each byte
        print(f"GETTING FILE SIZE OF : {path_to_file}... its: {os.path.getsize(path_to_file)}")
        self.file_byte_size = os.path.getsize(path_to_file)
        self.data = np.zeros(1,self.file_byte_size)

        byte_idx = 1
        with open(path_to_file, 'rb') as f:
            byte = f.read(byte_idx)
            while byte:
                self.data[byte_idx] = byte
                byte = f.read(byte_idx)
                byte_idx+=1
    
    def get_empty_header(self, header_byte_size):
        header = np.zeros((header_byte_size), dtype=np.int8)
        #print(f"AAAAAAA {header_byte_size}: {header.size}")
        header[:] = ord(chr(0)) # Fill it with NULL's
        return header
    def get_empty_body(self, body_byte_size):
        body = np.zeros((body_byte_size), dtype=np.int8)
        body[:] = ord(chr(0)) # Fill it with NULL's
        return body
    def shorten_body_message(self, buffer, last_valid_byte_idx):
        return buffer[:last_valid_byte_idx+1] # Copy the data 