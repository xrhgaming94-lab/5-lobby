import threading
import jwt
import random
from threading import Thread
import json
import requests
import google.protobuf
from protobuf_decoder.protobuf_decoder import Parser
import json
import datetime
from datetime import datetime
from google.protobuf.json_format import MessageToJson
import my_message_pb2
import data_pb2
import base64
import logging
import re
import socket
from google.protobuf.timestamp_pb2 import Timestamp
import jwt_generator_pb2
import os
import binascii
import sys
import psutil
import MajorLoginRes_pb2
from time import sleep
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import time
import urllib3
from important_zitado import*
from byte import*

# Flask API imports
from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_activity.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Global variables
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Flask API Setup
app = Flask(__name__)
CORS(app)

# Shared command queue
command_queue = []
command_queue_lock = threading.Lock()

# Store request status
request_status = {}

def encrypt_packet(plain_text, key, iv):
    try:
        plain_text = bytes.fromhex(plain_text)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        cipher_text = cipher.encrypt(pad(plain_text, AES.block_size))
        return cipher_text.hex()
    except Exception as e:
        logging.error(f"Error in encrypt_packet: {e}")
        return None

def get_random_avatar():
    avatar_list = [
        '902050001', '902050002', '902050003', '902039016', '902050004', 
        '902047011', '902047010', '902049015', '902050006', '902049020'
    ]
    return random.choice(avatar_list)

def get_available_room(input_text):
    try:
        parsed_results = Parser().parse(input_text)
        parsed_results_objects = parsed_results
        parsed_results_dict = parse_results(parsed_results_objects)
        json_data = json.dumps(parsed_results_dict)
        return json_data
    except Exception as e:
        logging.error(f"error {e}")
        return None

def parse_results(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {}
        field_data["wire_type"] = result.wire_type
        if result.wire_type == "varint":
            field_data["data"] = result.data
        if result.wire_type == "string":
            field_data["data"] = result.data
        if result.wire_type == "bytes":
            field_data["data"] = result.data
        elif result.wire_type == "length_delimited":
            field_data["data"] = parse_results(result.data.results)
        result_dict[result.field] = field_data
    return result_dict

def dec_to_hex(ask):
    try:
        ask_result = hex(ask)
        final_result = str(ask_result)[2:]
        if len(final_result) == 1:
            final_result = "0" + final_result
        return final_result
    except Exception as e:
        logging.error(f"Error in dec_to_hex: {e}")
        return "00"

def encrypt_api(plain_text):
    try:
        plain_text = bytes.fromhex(plain_text)
        key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
        iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
        cipher = AES.new(key, AES.MODE_CBC, iv)
        cipher_text = cipher.encrypt(pad(plain_text, AES.block_size))
        return cipher_text.hex()
    except Exception as e:
        logging.error(f"Error in encrypt_api: {e}")
        return None

def restart_program():
    logging.warning("Initiating bot restart...")
    try:
        p = psutil.Process(os.getpid())
        for handler in p.open_files() + p.connections():
            try:
                os.close(handler.fd)
            except Exception as e:
                logging.error(f"Failed to close handler {handler.fd}: {e}")
    except Exception as e:
        logging.error(f"Error during pre-restart cleanup: {e}")
    
    python = sys.executable
    os.execl(python, python, *sys.argv)

# ==================== FLASK API SECTION ====================

@app.route('/')
def api_home():
    """API Home endpoint"""
    return jsonify({
        "status": "success",
        "message": "🎮 FF Squad Bot API 🎮",
        "endpoints": {
            "/3": "Send 3-player squad invite (GET param: uid)",
            "/4": "Send 4-player squad invite (GET param: uid)",
            "/5": "Send 5-player squad invite (GET param: uid)", 
            "/6": "Send 6-player squad invite (GET param: uid)",
            "/room": "Room spam (30x create/invite/leave)",
            "/spm": "Squad spam (30x create/invite/leave)", 
            "/status": "Check bot status",
            "/queue": "Check command queue"
        },
        "usage": "Example: /5?uid=1234567890, /room?uid=1234567890"
    })

@app.route('/status')
def api_status():
    """Check bot status"""
    queue_size = len(command_queue)
    
    return jsonify({
        "status": "success",
        "data": {
            "tcp_bot": "online",
            "api_server": "online", 
            "queue_size": queue_size,
            "pending_requests": len(request_status)
        }
    })

@app.route('/queue')
def api_queue():
    """Check command queue"""
    with command_queue_lock:
        queue_info = [{
            "type": cmd['type'],
            "uid": cmd['uid'],
            "request_id": cmd.get('request_id', 'N/A')
        } for cmd in command_queue]
    
    return jsonify({
        "status": "success",
        "queue_size": len(command_queue),
        "pending_commands": queue_info
    })

@app.route('/3')
def api_squad_3():
    """Handle 3-player squad invite"""
    return handle_squad_request('3')

@app.route('/4')  
def api_squad_4():
    """Handle 4-player squad invite"""
    return handle_squad_request('4')

@app.route('/5')
def api_squad_5():
    """Handle 5-player squad invite"""
    return handle_squad_request('5')

@app.route('/6')
def api_squad_6():
    """Handle 6-player squad invite"""
    return handle_squad_request('6')

@app.route('/room')
def api_room_spam():
    """Handle room spam (30x create/invite/leave)"""
    return handle_spam_request('room_spam')

@app.route('/spm')
def api_squad_spam():
    """Handle squad spam (30x create/invite/leave)"""
    return handle_spam_request('squad_spam')

def handle_squad_request(squad_type):
    """Common handler for all squad requests"""
    global command_queue, request_status
    
    # Get UID from query parameters
    uid = request.args.get('uid', '').strip()
    
    # Validate UID
    if not uid:
        return jsonify({
            "status": "error",
            "message": "UID parameter is required",
            "usage": f"/{squad_type}?uid=1234567890"
        }), 400
    
    if not uid.isdigit():
        return jsonify({
            "status": "error", 
            "message": "UID must contain only numbers",
            "your_uid": uid
        }), 400
    
    if len(uid) < 8 or len(uid) > 15:
        return jsonify({
            "status": "error",
            "message": "UID must be 8-15 digits long", 
            "your_uid": uid,
            "uid_length": len(uid)
        }), 400
    
    # Generate request ID
    request_id = str(uuid.uuid4())[:8]
    
    # Add command to queue
    with command_queue_lock:
        command_queue.append({
            'type': squad_type,
            'uid': uid,
            'request_id': request_id,
            'timestamp': time.time()
        })
    
    # Initialize request status
    request_status[request_id] = {
        'status': 'queued',
        'type': squad_type,
        'uid': uid,
        'message': 'Command added to queue',
        'timestamp': time.time()
    }
    
    queue_size = len(command_queue)
    
    logging.info(f"✅ API Request {request_id}: {squad_type}-squad for UID: {uid}")
    
    return jsonify({
        "status": "success",
        "message": "Command added to queue",
        "request_id": request_id,
        "data": {
            "squad_type": f"{squad_type}-player",
            "target_uid": uid,
            "queue_position": queue_size
        },
        "next_steps": [
            f"Create {squad_type}-player squad",
            f"Send invite to UID: {uid}", 
            "Return to solo after 5 seconds"
        ]
    })

def handle_spam_request(spam_type):
    """Common handler for spam requests"""
    global command_queue, request_status
    
    # Get UID from query parameters
    uid = request.args.get('uid', '').strip()
    
    # Validate UID
    if not uid:
        return jsonify({
            "status": "error",
            "message": "UID parameter is required",
            "usage": f"/{spam_type}?uid=1234567890"
        }), 400
    
    if not uid.isdigit():
        return jsonify({
            "status": "error", 
            "message": "UID must contain only numbers",
            "your_uid": uid
        }), 400
    
    if len(uid) < 8 or len(uid) > 15:
        return jsonify({
            "status": "error",
            "message": "UID must be 8-15 digits long", 
            "your_uid": uid,
            "uid_length": len(uid)
        }), 400
    
    # Generate request ID
    request_id = str(uuid.uuid4())[:8]
    
    # Add command to queue
    with command_queue_lock:
        command_queue.append({
            'type': spam_type,
            'uid': uid,
            'request_id': request_id,
            'timestamp': time.time(),
            'spam_count': 30
        })
    
    # Initialize request status
    request_status[request_id] = {
        'status': 'queued',
        'type': spam_type,
        'uid': uid,
        'message': 'Spam command added to queue',
        'timestamp': time.time(),
        'current_cycle': 0,
        'total_cycles': 30
    }
    
    queue_size = len(command_queue)
    
    spam_name = "Room Spam" if spam_type == "room_spam" else "Squad Spam"
    
    logging.info(f"✅ API Request {request_id}: {spam_name} for UID: {uid}")
    
    return jsonify({
        "status": "success",
        "message": f"{spam_name} command added to queue",
        "request_id": request_id,
        "data": {
            "spam_type": spam_name,
            "target_uid": uid,
            "cycles": 30,
            "queue_position": queue_size
        },
        "next_steps": [
            f"Start {spam_name} - 30 cycles",
            "Each cycle: Create → Invite → Leave",
            "Speed: Fast execution"
        ]
    })

@app.route('/request/<request_id>')
def check_request_status(request_id):
    """Check status of a specific request"""
    if request_id in request_status:
        return jsonify({
            "status": "success",
            "request_id": request_id,
            "data": request_status[request_id]
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Request ID not found"
        }), 404

def update_request_status(request_id, status, message, current_cycle=None, total_cycles=None):
    """Update the status of a request"""
    global request_status
    if request_id in request_status:
        update_data = {
            'status': status,
            'message': message,
            'updated_at': time.time()
        }
        if current_cycle is not None:
            update_data['current_cycle'] = current_cycle
        if total_cycles is not None:
            update_data['total_cycles'] = total_cycles
            
        request_status[request_id].update(update_data)

# ==================== TCP BOT SECTION ====================

class FF_CLIENT(threading.Thread):
    def __init__(self, id, password):
        super().__init__()
        self.id = id
        self.password = password
        self.key = None
        self.iv = None
        self.start_time = time.time()
        self.socket_client = None
        self.get_tok()

    def parse_my_message(self, serialized_data):
        try:
            MajorLogRes = MajorLoginRes_pb2.MajorLoginRes()
            MajorLogRes.ParseFromString(serialized_data)
            key = MajorLogRes.ak
            iv = MajorLogRes.aiv
            if isinstance(key, bytes):
                key = key.hex()
            if isinstance(iv, bytes):
                iv = iv.hex()
            self.key = key
            self.iv = iv
            logging.info(f"Key: {self.key} | IV: {self.iv}")
            return self.key, self.iv
        except Exception as e:
            logging.error(f"{e}")
            return None, None

    def nmnmmmmn(self, data):
        key, iv = self.key, self.iv
        try:
            if isinstance(key, str):
                key = bytes.fromhex(key)
            if isinstance(iv, str):
                iv = bytes.fromhex(iv)
            data = bytes.fromhex(data)
            cipher = AES.new(key, AES.MODE_CBC, iv)
            cipher_text = cipher.encrypt(pad(data, AES.block_size))
            return cipher_text.hex()
        except Exception as e:
            logging.error(f"Error in nmnmmmmn: {e}")
            return None

    # Room Functions
    def create_room_packet(self):
        """Create room packet"""
        fields = {
            1: 2,
            2: {
                1: 1,
                2: 15,
                3: 5,
                4: "ROOM SPAM",
                5: "1",
                6: 12,
                7: 1,
                8: 1,
                9: 1,
                11: 1,
                12: 2,
                14: 36981056,
                15: {
                    1: "IDC3",
                    2: 126,
                    3: "BD"
                },
                16: "\u0001\u0003\u0004\u0007\t\n\u000b\u0012\u000f\u000e\u0016\u0019\u001a \u001d",
                18: 2368584,
                27: 1,
                34: "\u0000\u0001",
                40: "en",
                48: 1,
                49: {
                    1: 21
                },
                50: {
                    1: 36981056,
                    2: 2368584,
                    5: 2
                }
            }
        }

        packet = create_protobuf_packet(fields)
        if not packet:
            logging.error("Failed to create room packet")
            return None
            
        packet_hex = packet.hex()
        encrypted = encrypt_packet(packet_hex, self.key, self.iv)
        if not encrypted:
            logging.error("Failed to encrypt room packet")
            return None
            
        header_length = len(encrypted) // 2
        header_length_final = dec_to_hex(header_length)
        
        if len(header_length_final) == 2:
            final_packet = "0515000000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 3:
            final_packet = "051500000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 4:
            final_packet = "05150000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 5:
            final_packet = "0515000" + header_length_final + self.nmnmmmmn(packet_hex)
        else:
            final_packet = "0515" + ("0" * (10 - len(header_length_final))) + header_length_final + self.nmnmmmmn(packet_hex)
        
        try:
            return bytes.fromhex(final_packet)
        except ValueError as e:
            logging.error(f"Invalid hex in final_packet: {e}")
            return None

    def invite_room_packet(self, uid):
        """Invite to room packet"""
        fields = {
            1: 22,
            2: {
                1: int(uid)
            }
        }

        packet = create_protobuf_packet(fields)
        if not packet:
            return None
            
        packet_hex = packet.hex()
        encrypted = encrypt_packet(packet_hex, self.key, self.iv)
        if not encrypted:
            return None
            
        header_length = len(encrypted) // 2
        header_length_final = dec_to_hex(header_length)
        
        if len(header_length_final) == 2:
            final_packet = "0515000000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 3:
            final_packet = "051500000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 4:
            final_packet = "05150000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 5:
            final_packet = "0515000" + header_length_final + self.nmnmmmmn(packet_hex)
        else:
            final_packet = "0515" + ("0" * (10 - len(header_length_final))) + header_length_final + self.nmnmmmmn(packet_hex)
        
        try:
            return bytes.fromhex(final_packet)
        except ValueError as e:
            logging.error(f"Invalid hex in invite_room_packet: {e}")
            return None

    def leave_room_packet(self):
        """Leave room packet"""
        fields = {
            1: 6,
            2: {
                1: int(self.id)
            }
        }

        packet = create_protobuf_packet(fields)
        if not packet:
            return None
            
        packet_hex = packet.hex()
        encrypted = encrypt_packet(packet_hex, self.key, self.iv)
        if not encrypted:
            return None
            
        header_length = len(encrypted) // 2
        header_length_final = dec_to_hex(header_length)
        
        if len(header_length_final) == 2:
            final_packet = "0515000000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 3:
            final_packet = "051500000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 4:
            final_packet = "05150000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 5:
            final_packet = "0515000" + header_length_final + self.nmnmmmmn(packet_hex)
        else:
            final_packet = "0515" + ("0" * (10 - len(header_length_final))) + header_length_final + self.nmnmmmmn(packet_hex)
        
        try:
            return bytes.fromhex(final_packet)
        except ValueError as e:
            logging.error(f"Invalid hex in leave_room_packet: {e}")
            return None

    # Squad Functions
    def invite_skwad(self, idplayer):
        fields = {
            1: 2,
            2: {
                1: int(idplayer),
                2: "BD",
                4: 1
            }
        }
        packet = create_protobuf_packet(fields)
        if not packet:
            return None
            
        packet_hex = packet.hex()
        encrypted = encrypt_packet(packet_hex, self.key, self.iv)
        if not encrypted:
            return None
            
        header_length = len(encrypted) // 2
        header_length_final = dec_to_hex(header_length)
        
        if len(header_length_final) == 2:
            final_packet = "0515000000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 3:
            final_packet = "051500000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 4:
            final_packet = "05150000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 5:
            final_packet = "0515000" + header_length_final + self.nmnmmmmn(packet_hex)
        else:
            final_packet = "0515" + ("0" * (10 - len(header_length_final))) + header_length_final + self.nmnmmmmn(packet_hex)
        
        try:
            return bytes.fromhex(final_packet)
        except ValueError as e:
            logging.error(f"Invalid hex in invite_skwad: {e}")
            return None

    def skwad_maker(self):
        fields = {
            1: 1,
            2: {
                2: "\u0001",
                3: 1,
                4: 1,
                5: "en",
                9: 1,
                11: 1,
                13: 1,
                14: {
                    2: 5756,
                    6: 11,
                    8: "1.109.5",
                    9: 3,
                    10: 2
                },
            }
        }

        packet = create_protobuf_packet(fields)
        if not packet:
            return None
            
        packet_hex = packet.hex()
        encrypted = encrypt_packet(packet_hex, self.key, self.iv)
        if not encrypted:
            return None
            
        header_length = len(encrypted) // 2
        header_length_final = dec_to_hex(header_length)
        
        if len(header_length_final) == 2:
            final_packet = "0515000000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 3:
            final_packet = "051500000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 4:
            final_packet = "05150000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 5:
            final_packet = "0515000" + header_length_final + self.nmnmmmmn(packet_hex)
        else:
            final_packet = "0515" + ("0" * (10 - len(header_length_final))) + header_length_final + self.nmnmmmmn(packet_hex)
        
        try:
            return bytes.fromhex(final_packet)
        except ValueError as e:
            logging.error(f"Invalid hex in skwad_maker: {e}")
            return None

    def changes(self, num):
        fields = {
            1: 17,
            2: {
                1: 12480598706,
                2: 1,
                3: int(num),
                4: 62,
                5: "\u001a",
                8: 5,
                13: 329
            }
        }

        packet = create_protobuf_packet(fields)
        if not packet:
            return None
            
        packet_hex = packet.hex()
        encrypted = encrypt_packet(packet_hex, self.key, self.iv)
        if not encrypted:
            return None
            
        header_length = len(encrypted) // 2
        header_length_final = dec_to_hex(header_length)
        
        if len(header_length_final) == 2:
            final_packet = "0515000000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 3:
            final_packet = "051500000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 4:
            final_packet = "05150000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 5:
            final_packet = "0515000" + header_length_final + self.nmnmmmmn(packet_hex)
        else:
            final_packet = "0515" + ("0" * (10 - len(header_length_final))) + header_length_final + self.nmnmmmmn(packet_hex)
        
        try:
            return bytes.fromhex(final_packet)
        except ValueError as e:
            logging.error(f"Invalid hex in changes: {e}")
            return None

    def leave_s(self):
        fields = {
            1: 7,
            2: {
                1: 12480598706
            }
        }

        packet = create_protobuf_packet(fields)
        if not packet:
            return None
            
        packet_hex = packet.hex()
        encrypted = encrypt_packet(packet_hex, self.key, self.iv)
        if not encrypted:
            return None
            
        header_length = len(encrypted) // 2
        header_length_final = dec_to_hex(header_length)
        
        if len(header_length_final) == 2:
            final_packet = "0515000000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 3:
            final_packet = "051500000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 4:
            final_packet = "05150000" + header_length_final + self.nmnmmmmn(packet_hex)
        elif len(header_length_final) == 5:
            final_packet = "0515000" + header_length_final + self.nmnmmmmn(packet_hex)
        else:
            final_packet = "0515" + ("0" * (10 - len(header_length_final))) + header_length_final + self.nmnmmmmn(packet_hex)
        
        try:
            return bytes.fromhex(final_packet)
        except ValueError as e:
            logging.error(f"Invalid hex in leave_s: {e}")
            return None

    def sockf1(self, tok, online_ip, online_port):
        try:
            self.socket_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            online_port = int(online_port)

            self.socket_client.connect((online_ip, online_port))
            logging.info(f"✅ Connected to port {online_port} Host {online_ip}")
            
            # Validate token before sending
            try:
                token_bytes = bytes.fromhex(tok)
                self.socket_client.send(token_bytes)
            except ValueError as e:
                logging.error(f"Invalid token hex: {e}")
                return

            while True:
                try:
                    if time.time() - self.start_time > 600:
                        logging.warning("Scheduled 10-minute restart from sockf1.")
                        restart_program()

                    data2 = self.socket_client.recv(9999)
                    
                    if data2 == b"":
                        logging.error("Connection closed by remote host. Restarting.")
                        restart_program()
                        break
                except Exception as e:
                    logging.critical(f"Unhandled error in sockf1: {e}. Restarting bot.")
                    restart_program()
        except Exception as e:
            logging.error(f"Error in sockf1: {e}")
            restart_program()

    def connect(self, tok, packet, key, iv, whisper_ip, whisper_port, online_ip, online_port):
        global clients
        global command_queue
        
        try:
            clients = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            clients.connect((whisper_ip, whisper_port))
            
            # Validate token before sending
            try:
                token_bytes = bytes.fromhex(tok)
                clients.send(token_bytes)
            except ValueError as e:
                logging.error(f"Invalid token hex in connect: {e}")
                return
            
            # Start socket thread
            thread = threading.Thread(
                target=self.sockf1, args=(tok, online_ip, online_port)
            )
            thread.daemon = True
            thread.start()

            logging.info("✅ TCP Bot is online and waiting for commands...")
            logging.info("📋 Checking command queue every 2 seconds...")

            while True:
                if time.time() - self.start_time > 600:
                    logging.warning("Scheduled 10-minute restart.")
                    restart_program()
                
                try:
                    # Check for commands
                    if command_queue and self.socket_client:
                        with command_queue_lock:
                            if command_queue:
                                cmd = command_queue.pop(0)
                        
                        command_type = cmd.get('type')
                        target_id = cmd.get('uid')
                        request_id = cmd.get('request_id')
                        spam_count = cmd.get('spam_count', 1)
                        
                        logging.info(f"📨 Processing: {command_type} for UID {target_id} (Request: {request_id})")
                        
                        # Handle different command types
                        if command_type in ['3', '4', '5', '6']:
                            self.process_squad_command(command_type, target_id, request_id)
                        elif command_type == 'room_spam':
                            self.process_room_spam(target_id, request_id, spam_count)
                        elif command_type == 'squad_spam':
                            self.process_squad_spam(target_id, request_id, spam_count)
                    
                    # Check every 2 seconds
                    time.sleep(2)

                except socket.error as e:
                    logging.error(f"Socket error: {e}")
                    time.sleep(5)
                except Exception as e:
                    logging.error(f"Error in main loop: {e}")
                    # Update status to error
                    if 'request_id' in locals():
                        update_request_status(request_id, 'error', f'Error: {str(e)}')
                    time.sleep(2)

        except Exception as e:
            logging.critical(f"Critical error in connect: {e}. Restarting bot.")
            restart_program()

    def process_squad_command(self, squad_type, target_id, request_id):
        """Process single squad command"""
        # Update status to processing
        update_request_status(request_id, 'processing', 'Creating squad...')
        
        # Create squad
        packetmaker = self.skwad_maker()
        if packetmaker:
            self.socket_client.send(packetmaker)
            sleep(0.5)
        else:
            update_request_status(request_id, 'error', 'Failed to create squad packet')
            return
        
        # Change squad size
        squad_sizes = {'3': 2, '4': 3, '5': 4, '6': 5}
        size = squad_sizes.get(squad_type)
        
        if size:
            packetfinal = self.changes(size)
            if packetfinal:
                self.socket_client.send(packetfinal)
                sleep(0.5)
            else:
                update_request_status(request_id, 'error', 'Failed to create squad size packet')
                return
            
            # Update status to inviting
            update_request_status(request_id, 'processing', 'Sending invite...')
            
            # Send invite
            invitess = self.invite_skwad(target_id)
            if invitess:
                self.socket_client.send(invitess)
            else:
                update_request_status(request_id, 'error', 'Failed to create invite packet')
                return
            
            logging.info(f"✅ Sent {squad_type}-player squad invite to {target_id}")
            
            # Update status to success
            update_request_status(request_id, 'success', 
                f'Squad created and invite sent to {target_id}. Returning to solo...')
            
            # Leave and return to solo
            sleep(5)
            leavee = self.leave_s()
            if leavee:
                self.socket_client.send(leavee)
                sleep(1)
            change_to_solo = self.changes(1)
            if change_to_solo:
                self.socket_client.send(change_to_solo)
            
            logging.info("🔙 Bot returned to solo mode.")
            
            # Final status update
            update_request_status(request_id, 'completed', 
                f'Successfully completed {squad_type}-player squad invite to {target_id}')

    def process_room_spam(self, target_id, request_id, spam_count=30):
        """Process room spam - 30 cycles of create/invite/leave"""
        update_request_status(request_id, 'processing', f'Starting room spam - {spam_count} cycles...', 0, spam_count)
        
        for cycle in range(spam_count):
            try:
                # Update cycle status
                update_request_status(request_id, 'processing', 
                    f'Room spam cycle {cycle + 1}/{spam_count}', cycle + 1, spam_count)
                
                # Create room
                create_room = self.create_room_packet()
                if create_room:
                    self.socket_client.send(create_room)
                    sleep(0.1)
                
                # Invite to room
                invite_room = self.invite_room_packet(target_id)
                if invite_room:
                    self.socket_client.send(invite_room)
                    sleep(0.1)
                
                # Leave room
                leave_room = self.leave_room_packet()
                if leave_room:
                    self.socket_client.send(leave_room)
                    sleep(0.1)
                
                logging.info(f"🎯 Room spam cycle {cycle + 1}/{spam_count} completed for UID: {target_id}")
                
            except Exception as e:
                logging.error(f"Error in room spam cycle {cycle + 1}: {e}")
                continue
        
        # Final status update
        update_request_status(request_id, 'completed', 
            f'Room spam completed - {spam_count} cycles sent to {target_id}')

    def process_squad_spam(self, target_id, request_id, spam_count=30):
        """Process squad spam - 30 cycles of create/invite/leave"""
        update_request_status(request_id, 'processing', f'Starting squad spam - {spam_count} cycles...', 0, spam_count)
        
        for cycle in range(spam_count):
            try:
                # Update cycle status
                update_request_status(request_id, 'processing', 
                    f'Squad spam cycle {cycle + 1}/{spam_count}', cycle + 1, spam_count)
                
                # Create 5-player squad
                packetmaker = self.skwad_maker()
                if packetmaker:
                    self.socket_client.send(packetmaker)
                    sleep(0.1)
                
                # Change to 5-player squad
                packetfinal = self.changes(4)  # 4 for 5 players
                if packetfinal:
                    self.socket_client.send(packetfinal)
                    sleep(0.1)
                
                # Send invite
                invitess = self.invite_skwad(target_id)
                if invitess:
                    self.socket_client.send(invitess)
                    sleep(0.1)
                
                # Leave squad and return to solo
                leavee = self.leave_s()
                if leavee:
                    self.socket_client.send(leavee)
                    sleep(0.1)
                
                change_to_solo = self.changes(1)
                if change_to_solo:
                    self.socket_client.send(change_to_solo)
                    sleep(0.1)
                
                logging.info(f"🎯 Squad spam cycle {cycle + 1}/{spam_count} completed for UID: {target_id}")
                
            except Exception as e:
                logging.error(f"Error in squad spam cycle {cycle + 1}: {e}")
                continue
        
        # Final status update
        update_request_status(request_id, 'completed', 
            f'Squad spam completed - {spam_count} cycles sent to {target_id}')

    def parse_my_message_login(self, serialized_data):
        try:
            MajorLogRes = MajorLoginRes_pb2.MajorLoginRes()
            MajorLogRes.ParseFromString(serialized_data)
            
            timestamp = MajorLogRes.kts
            key = MajorLogRes.ak
            iv = MajorLogRes.aiv
            BASE64_TOKEN = MajorLogRes.token
            timestamp_obj = Timestamp()
            timestamp_obj.FromNanoseconds(timestamp)
            timestamp_seconds = timestamp_obj.seconds
            timestamp_nanos = timestamp_obj.nanos
            combined_timestamp = timestamp_seconds * 1_000_000_000 + timestamp_nanos
            return combined_timestamp, key, iv, BASE64_TOKEN
        except Exception as e:
            logging.error(f"Error in parse_my_message_login: {e}")
            return None, None, None, None

    def GET_PAYLOAD_BY_DATA(self, JWT_TOKEN, NEW_ACCESS_TOKEN, date):
        try:
            token_payload_base64 = JWT_TOKEN.split('.')[1]
            token_payload_base64 += '=' * ((4 - len(token_payload_base64) % 4) % 4)
            decoded_payload = base64.urlsafe_b64decode(token_payload_base64).decode('utf-8')
            decoded_payload = json.loads(decoded_payload)
            NEW_EXTERNAL_ID = decoded_payload['external_id']
            SIGNATURE_MD5 = decoded_payload['signature_md5']
            now = datetime.now()
            now = str(now)[:len(str(now))-7]
            formatted_time = date
            payload = bytes.fromhex("1a13323032352d30372d33302031313a30323a3531220966726565206669726528013a07312e3131382e31422c416e64726f6964204f5320372e312e32202f204150492d323320284e32473438482f373030323530323234294a0848616e6468656c645207416e64726f69645a045749464960c00c68840772033332307a1f41524d7637205646507633204e454f4e20564d48207c2032343635207c203480019a1b8a010f416472656e6f2028544d292036343092010d4f70656e474c20455320332e319a012b476f6f676c657c31663361643662372d636562342d343934622d383730622d623164616364373230393131a2010c3139372e312e31322e313335aa0102656eb201203939366136323964626364623339363462653662363937386635643831346462ba010134c2010848616e6468656c64ca011073616d73756e6720534d2d473935354eea014066663930633037656239383135616633306134336234613966363031393531366530653463373033623434303932353136643064656661346365663531663261f00101ca0207416e64726f6964d2020457494649ca03203734323862323533646566633136343031386336303461316562626665626466e003daa907e803899b07f003bf0ff803ae088004999b078804daa9079004999b079804daa907c80403d204262f646174612f6170702f636f6d2e6474732e667265656669726574682d312f6c69622f61726de00401ea044832303837663631633139663537663261663465376665666630623234643964397c2f646174612f6170702f636f6d2e6474732e667265656669726574682d312f626173652e61706bf00403f804018a050233329a050a32303139313138363933a80503b205094f70656e474c455332b805ff7fc00504e005dac901ea0507616e64726f6964f2055c4b71734854394748625876574c6668437950416c52526873626d43676542557562555551317375746d525536634e30524f3751453141486e496474385963784d614c575437636d4851322b7374745279377830663935542b6456593d8806019006019a060134a2060134b2061e40001147550d0c074f530b4d5c584d57416657545a065f2a091d6a0d5033")
            payload = payload.replace(b"2025-07-30 11:02:51", str(now).encode())
            payload = payload.replace(b"ff90c07eb9815af30a43b4a9f6019516e0e4c703b44092516d0defa4cef51f2a", NEW_ACCESS_TOKEN.encode("UTF-8"))
            payload = payload.replace(b"996a629dbcdb3964be6b6978f5d814db", NEW_EXTERNAL_ID.encode("UTF-8"))
            payload = payload.replace(b"7428b253defc164018c604a1ebbfebdf", SIGNATURE_MD5.encode("UTF-8"))
            PAYLOAD = payload.hex()
            PAYLOAD = encrypt_api(PAYLOAD)
            if not PAYLOAD:
                return None, None, None, None
            PAYLOAD = bytes.fromhex(PAYLOAD)
            whisper_ip, whisper_port, online_ip, online_port = self.GET_LOGIN_DATA(JWT_TOKEN, PAYLOAD)
            return whisper_ip, whisper_port, online_ip, online_port
        except Exception as e:
            logging.error(f"Error in GET_PAYLOAD_BY_DATA: {e}")
            return None, None, None, None

    def GET_LOGIN_DATA(self, JWT_TOKEN, PAYLOAD):
        url = "https://clientbp.ggblueshark.com/GetLoginData"
        headers = {
            'Expect': '100-continue',
            'Authorization': f'Bearer {JWT_TOKEN}',
            'X-Unity-Version': '2018.4.11f1',
            'X-GA': 'v1 1',
            'ReleaseVersion': 'OB51',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; G011A Build/PI)',
            'Host': 'clientbp.ggblueshark.com',
            'Connection': 'close',
            'Accept-Encoding': 'gzip, deflate, br',
        }
        
        max_retries = 3
        attempt = 0

        while attempt < max_retries:
            try:
                response = requests.post(url, headers=headers, data=PAYLOAD, verify=False)
                response.raise_for_status()
                x = response.content.hex()
                json_result = get_available_room(x)
                if not json_result:
                    attempt += 1
                    continue
                    
                parsed_data = json.loads(json_result)
                
                whisper_address = parsed_data['32']['data']
                online_address = parsed_data['14']['data']
                online_ip = online_address[:len(online_address) - 6]
                whisper_ip = whisper_address[:len(whisper_address) - 6]
                online_port = int(online_address[len(online_address) - 5:])
                whisper_port = int(whisper_address[len(whisper_address) - 5:])
                return whisper_ip, whisper_port, online_ip, online_port
            
            except requests.RequestException as e:
                logging.error(f"Request failed: {e}. Attempt {attempt + 1} of {max_retries}. Retrying...")
                attempt += 1
                time.sleep(2)

        logging.critical("Failed to get login data after multiple attempts. Restarting.")
        restart_program()
        return None, None, None, None

    def guest_token(self, uid, password):
        try:
            url = "https://100067.connect.garena.com/oauth/guest/token/grant"
            headers = {
                "Host": "100067.connect.garena.com",
                "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 10;en;EN;)",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "close",
            }
            data = {
                "uid": f"{uid}",
                "password": f"{password}",
                "response_type": "token",
                "client_type": "2",
                "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
                "client_id": "100067",
            }
            response = requests.post(url, headers=headers, data=data)
            data = response.json()
            NEW_ACCESS_TOKEN = data['access_token']
            NEW_OPEN_ID = data['open_id']
            OLD_ACCESS_TOKEN = "ff90c07eb9815af30a43b4a9f6019516e0e4c703b44092516d0defa4cef51f2a"
            OLD_OPEN_ID = "996a629dbcdb3964be6b6978f5d814db"
            time.sleep(0.2)
            data = self.TOKEN_MAKER(OLD_ACCESS_TOKEN, NEW_ACCESS_TOKEN, OLD_OPEN_ID, NEW_OPEN_ID, uid)
            return data
        except Exception as e:
            logging.error(f"Error in guest_token: {e}")
            return None

    def TOKEN_MAKER(self, OLD_ACCESS_TOKEN, NEW_ACCESS_TOKEN, OLD_OPEN_ID, NEW_OPEN_ID, id):
        try:
            headers = {
                'X-Unity-Version': '2018.4.11f1',
                'ReleaseVersion': 'OB51',
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-GA': 'v1 1',
                'Content-Length': '928',
                'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 7.1.2; ASUS_Z01QD Build/QKQ1.190825.002)',
                'Host': 'clientbp.ggblueshark.com',
                'Connection': 'Keep-Alive',
                'Accept-Encoding': 'gzip'
            }
            data = bytes.fromhex('1a13323032352d30372d33302031313a30323a3531220966726565206669726528013a07312e3131382e31422c416e64726f6964204f5320372e312e32202f204150492d323320284e32473438482f373030323530323234294a0848616e6468656c645207416e64726f69645a045749464960c00c68840772033332307a1f41524d7637205646507633204e454f4e20564d48207c2032343635207c203480019a1b8a010f416472656e6f2028544d292036343092010d4f70656e474c20455320332e319a012b476f6f676c657c31663361643662372d636562342d343934622d383730622d623164616364373230393131a2010c3139372e312e31322e313335aa0102656eb201203939366136323964626364623339363462653662363937386635643831346462ba010134c2010848616e6468656c64ca011073616d73756e6720534d2d473935354eea014066663930633037656239383135616633306134336234613966363031393531366530653463373033623434303932353136643064656661346365663531663261f00101ca0207416e64726f6964d2020457494649ca03203734323862323533646566633136343031386336303461316562626665626466e003daa907e803899b07f003bf0ff803ae088004999b078804daa9079004999b079804daa907c80403d204262f646174612f6170702f636f6d2e6474732e667265656669726574682d312f6c69622f61726de00401ea044832303837663631633139663537663261663465376665666630623234643964397c2f646174612f6170702f636f6d2e6474732e667265656669726574682d312f626173652e61706bf00403f804018a050233329a050a32303139313138363933a80503b205094f70656e474c455332b805ff7fc00504e005dac901ea0507616e64726f6964f2055c4b71734854394748625876574c6668437950416c52526873626d43676542557562555551317375746d525536634e30524f3751453141486e496474385963784d614c575437636d4851322b7374745279377830663935542b6456593d8806019006019a060134a2060134b2061e40001147550d0c074f530b4d5c584d57416657545a065f2a091d6a0d5033')
            data = data.replace(OLD_OPEN_ID.encode(), NEW_OPEN_ID.encode())
            data = data.replace(OLD_ACCESS_TOKEN.encode(), NEW_ACCESS_TOKEN.encode())
            hex_data = data.hex()
            d = encrypt_api(data.hex())
            if not d:
                return False
            Final_Payload = bytes.fromhex(d)
            URL = "https://loginbp.ggblueshark.com/MajorLogin"

            RESPONSE = requests.post(URL, headers=headers, data=Final_Payload, verify=False)
            
            combined_timestamp, key, iv, BASE64_TOKEN = self.parse_my_message_login(RESPONSE.content)
            if RESPONSE.status_code == 200:
                if len(RESPONSE.text) < 10:
                    return False
                whisper_ip, whisper_port, online_ip, online_port = self.GET_PAYLOAD_BY_DATA(BASE64_TOKEN, NEW_ACCESS_TOKEN, 1)
                self.key = key
                self.iv = iv
                return(BASE64_TOKEN, key, iv, combined_timestamp, whisper_ip, whisper_port, online_ip, online_port)
            else:
                return False
        except Exception as e:
            logging.error(f"Error in TOKEN_MAKER: {e}")
            return False

    def get_tok(self):
        global g_token
        token_data = self.guest_token(self.id, self.password)
        if not token_data:
            logging.critical("Failed to get token data from guest_token. Restarting.")
            restart_program()

        token, key, iv, Timestamp, whisper_ip, whisper_port, online_ip, online_port = token_data
        g_token = token
        
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            account_id = decoded.get('account_id')
            encoded_acc = hex(account_id)[2:]
            hex_value = dec_to_hex(Timestamp)
            time_hex = hex_value
            BASE64_TOKEN_ = token.encode().hex()
            logging.info(f"Token decoded and processed. Account ID: {account_id}")
        except Exception as e:
            logging.error(f"Error processing token: {e}. Restarting.")
            restart_program()

        try:
            # Validate hex values before constructing final token
            encrypted_packet_hex = encrypt_packet(BASE64_TOKEN_, key, iv)
            if not encrypted_packet_hex:
                logging.error("Failed to encrypt packet for token")
                restart_program()
                
            head_length = len(encrypted_packet_hex) // 2
            head_hex = hex(head_length)[2:]
            
            length = len(encoded_acc)
            zeros = '00000000'

            if length == 9:
                zeros = '0000000'
            elif length == 8:
                zeros = '00000000'
            elif length == 10:
                zeros = '000000'
            elif length == 7:
                zeros = '000000000'
            else:
                logging.warning('Unexpected length encountered')
                
            head = f'0115{zeros}{encoded_acc}{time_hex}00000{head_hex}'
            final_token = head + encrypted_packet_hex
            
            # Validate final token is proper hex
            bytes.fromhex(final_token)
            logging.info("Final token constructed successfully.")
        except Exception as e:
            logging.error(f"Error constructing final token: {e}. Restarting.")
            restart_program()
        
        token = final_token
        self.connect(token, 'anything', key, iv, whisper_ip, whisper_port, online_ip, online_port)
        
        return token, key, iv

# ==================== MAIN EXECUTION ====================

def load_accounts():
    """Load accounts from accs.txt"""
    try:
        with open('accs.txt', 'r') as file:
            data = json.load(file)
        return list(data.items())
    except Exception as e:
        logging.error(f"Error loading accounts: {e}")
        return []

ids_passwords = load_accounts()

def run_tcp_client(id, password):
    logging.info(f"🎮 Starting TCP client for ID: {id}")
    client = FF_CLIENT(id, password)

def run_flask_api():
    """Run Flask API server"""
    logging.info("🚀 Starting Flask API Server...")
    print("""
╔════════════════════════════════════════╗
║   🎮 FF SQUAD BOT API 🎮               ║
╠════════════════════════════════════════╣
║  ✅ TCP Bot: Starting...               ║
║  ✅ API Server: Starting...            ║
║  Routes: /3 /4 /5 /6 /room /spm        ║
║          /status /queue                 ║
║                                        ║
║  🌐 API Endpoints:                     ║
║  http://localhost:5001/5?uid=12345678  ║
║  http://localhost:5001/room?uid=12345678
║  http://localhost:5001/spm?uid=12345678
║  http://localhost:5001/status          ║
╚════════════════════════════════════════╝
    """)
    
    # Run Flask app on port 5001 to avoid conflict
    app.run(host='0.0.0.0', port=5901, debug=False, threaded=True)

if __name__ == "__main__":
    # Start Flask API in separate thread
    api_thread = threading.Thread(target=run_flask_api, daemon=True)
    api_thread.start()
    
    # Give API time to start
    time.sleep(3)
    
    # Start TCP bot
    while True:
        try:
            logging.info("🚀 Main execution block started.")
            
            # Start only first bot from XRAC.txt
            if ids_passwords:
                id_val, password_val = ids_passwords[0]
                run_tcp_client(id_val, password_val)
            else:
                logging.error("No accounts found in acces.txt")
                time.sleep(10)
                restart_program()
            
            logging.info("✅ Bot initiated. Main thread waiting...")
            
            # Keep main thread alive
            while True:
                time.sleep(10)

        except KeyboardInterrupt:
            logging.info("⚠️ Shutdown signal received. Exiting.")
            break
        except Exception as e:
            logging.critical(f"❌ A critical error occurred: {e}")
            logging.info("🔄 Restarting in 5 seconds...")
            time.sleep(5)
            restart_program()