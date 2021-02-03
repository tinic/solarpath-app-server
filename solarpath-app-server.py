#!/usr/bin/python3

from bitstream import *
from bitstring import *
from datetime import *
from urllib.parse import *

import json
import http.server
import socketserver
import base64
import requests
import pymongo
import signal
import sys
import time
import threading
import socket

mc = pymongo.MongoClient("localhost", 27017)

class SolarPathHttpRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/solarpath/hass'):
            try:
                self.send_response(200, 'OK')
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                entries = mc.solarpath.stations.find()
                response = []
                for entry in entries:
                    response.append({
                        'device_eui' : entry['device_eui'],
                        'solar_voltage' : entry['state']['solar_voltage'],              
                        'battery_voltage' : entry['state']['battery_voltage'],              
                        'temperature' : entry['state']['temperature'],              
                        'humidity' : entry['state']['humidity'],              
                        'light_on' : entry['settings']['light_on'],              
                        'auto_light_on' : entry['settings']['auto_light_on'],              
                        'color' : entry['settings']['colors'][0]})
                self.wfile.write(bytes(json.dumps(response), 'utf-8'))
                self.send_response(200)
                return
            except:
                self.send_response(500)
                self.end_headers()
                return

    def do_POST(self):
        if self.path.startswith('/solarpath/hass'):
            try:
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.data_string = self.rfile.read(int(self.headers['Content-Length']))
                json_data = json.loads(self.data_string)
                for entry in json_data:
                    if 'light_on' in entry:
                        mc.solarpath.stations.update_one({'device_eui' : entry['device_eui']}, {'$set' : {'settings.light_on' : entry['light_on']}}, upsert=False)
                    if 'auto_light_on' in entry:
                        mc.solarpath.stations.update_one({'device_eui' : entry['device_eui']}, {'$set' : {'settings.auto_light_on' : entry['auto_light_on']}}, upsert=False)
                    if 'color' in entry:
                        mc.solarpath.stations.update_one({'device_eui' : entry['device_eui']}, {'$set' : {'settings.colors.0' : entry['color']}}, upsert=False)
                self.send_response(200)
                return
            except:
                self.send_response(500)
                self.end_headers()
                return

        if self.path.startswith('/solarpath/chirp'):
            try:
                if (urlparse(self.path).query != 'event=up'):
                    self.send_response(200)
                    self.end_headers()
                    return

                self.send_header("Content-type", "text/html")
                self.end_headers()

                self.data_string = self.rfile.read(int(self.headers['Content-Length']))
                json_data = json.loads(self.data_string)

                entry = mc.solarpath.stations.find_one({'device_eui' : base64.b64decode(json_data['devEUI'])})
                if (not entry):
                    entry = {
                        'device_eui' : '',
                        'last_seen' : '',
                        'settings' : {
                            'light_on' : 0,
                            'auto_light_on' : 0,
                            'colors' : [
                                [1.0, 1.0, 1.0],
                                [1.0, 1.0, 1.0],
                                [1.0, 1.0, 1.0]
                            ]
                        },
                        'state' : {
                            'battery_voltage' : 0,
                            'solar_voltage' : 0,
                            'temperature' : 0,
                            'humidity' : 0,
                            'power_good' : 0,
                            'state_good' : 0
                        },
                        'last_downlink' : { },
                        'last_uplink' : { }
                    }
                entry = entry.copy()
                if hasattr(entry, '_id'):
                    del entry['_id']

                devEUI = base64.b64decode(json_data['devEUI']).hex()

                entry['device_eui'] = devEUI
                entry['last_seen'] = datetime(2019, 5, 18, 15, 17, tzinfo=timezone.utc).isoformat()

                bits = BitString(base64.b64decode(json_data['data']))

                entry['state']['battery_voltage'] = 0.1 * bits.read('uint:4') + 2.7
                entry['state']['solar_voltage'] = 0.05 * bits.read('uint:4')
                entry['state']['temperature'] = 0.25 * bits.read('uint:8') - 10
                entry['state']['humidity'] = (1.0 / 63.0) * bits.read('uint:6')
                entry['state']['power_good'] = bits.read('uint:1')
                entry['state']['state_good'] = bits.read('uint:1')

                self.send_response(200)
                self.end_headers()

                payload_str = base64.b64encode(pack("uint:1, uint:1, "\
                    "uint:6, uint:6, uint:6, "\
                    "uint:6, uint:6, uint:6, "\
                    "uint:6, uint:6, uint:6",
                    int(entry['settings']['light_on']),
                    int(entry['settings']['auto_light_on']),
                    int(entry['settings']['colors'][0][0]*63),
                    int(entry['settings']['colors'][0][1]*63),
                    int(entry['settings']['colors'][0][2]*63),
                    int(entry['settings']['colors'][1][0]*63),
                    int(entry['settings']['colors'][1][1]*63),
                    int(entry['settings']['colors'][1][2]*63),
                    int(entry['settings']['colors'][2][0]*63),
                    int(entry['settings']['colors'][2][1]*63),
                    int(entry['settings']['colors'][2][2]*63)).bytes).decode("utf-8")

                down_data = {
                    'deviceQueueItem' : {
                        "confirmed": False,
                        "data": payload_str,
                        "fPort": 1
                    }
                }

                queueURL = "http://localhost:8080/api/devices/" + devEUI + "/queue"
                headers = {'Grpc-Metadata-Authorization' : 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlfa2V5X2lkIjoiNWM1MzI1MGQtZTgzZC00MjMxLWJiOWYtNmVjMDMyY2E0YTUwIiwiYXVkIjoiYXMiLCJpc3MiOiJhcyIsIm5iZiI6MTYxMjM3NDAxMCwic3ViIjoiYXBpX2tleSJ9.p7dvcogUdJrJO86_MHMO6n-Apz0cymHQ-pTXqqvXFPs'}

                entry['last_downlink'] = json_data
                entry['last_uplink'] = down_data

                mc.solarpath.stations.replace_one({'device_eui' : devEUI}, entry, upsert=True)
                return

            except:
                self.send_response(500)
                self.end_headers()
                return

        if self.path.startswith('/solarpath/ttn'):
            try:
                self.send_header("Content-type", "text/html")
                self.end_headers()

                self.data_string = self.rfile.read(int(self.headers['Content-Length']))
                json_data = json.loads(self.data_string)

                entry = mc.solarpath.stations.find_one({'device_eui' : json_data['hardware_serial']})
                if (not entry):
                    entry = {
                        'device_eui' : '',
                        'last_seen' : '',
                        'settings' : {
                            'light_on' : 0,
                            'auto_light_on' : 0,
                            'colors' : [
                                [1.0, 1.0, 1.0],
                                [1.0, 1.0, 1.0],
                                [1.0, 1.0, 1.0]
                            ]
                        },
                        'state' : {
                            'battery_voltage' : 0,
                            'solar_voltage' : 0,
                            'temperature' : 0,
                            'humidity' : 0,
                            'power_good' : 0,
                            'state_good' : 0
                        },
                        'last_downlink' : { },
                        'last_uplink' : { }
                    }
                entry = entry.copy()
                if hasattr(entry, '_id'):
                    del entry['_id']

                entry['device_eui'] = json_data['hardware_serial']
                entry['last_seen'] = json_data['metadata']['time']

                bits = BitString(base64.b64decode(json_data['payload_raw']))

                entry['state']['battery_voltage'] = 0.1 * bits.read('uint:4') + 2.7
                entry['state']['solar_voltage'] = 0.05 * bits.read('uint:4')
                entry['state']['temperature'] = 0.25 * bits.read('uint:8') - 10
                entry['state']['humidity'] = (1.0 / 63.0) * bits.read('uint:6')
                entry['state']['power_good'] = bits.read('uint:1')
                entry['state']['state_good'] = bits.read('uint:1')

                self.send_response(200)
                self.end_headers()

                payload_str = base64.b64encode(pack("uint:1, uint:1, "\
                    "uint:6, uint:6, uint:6, "\
                    "uint:6, uint:6, uint:6, "\
                    "uint:6, uint:6, uint:6",
                    int(entry['settings']['light_on']),
                    int(entry['settings']['auto_light_on']),
                    int(entry['settings']['colors'][0][0]*63),
                    int(entry['settings']['colors'][0][1]*63),
                    int(entry['settings']['colors'][0][2]*63),
                    int(entry['settings']['colors'][1][0]*63),
                    int(entry['settings']['colors'][1][1]*63),
                    int(entry['settings']['colors'][1][2]*63),
                    int(entry['settings']['colors'][2][0]*63),
                    int(entry['settings']['colors'][2][1]*63),
                    int(entry['settings']['colors'][2][2]*63)).bytes).decode("utf-8")

                down_data = {
                    "dev_id" : json_data['dev_id'],
                    "port" : 1,
                    "confirmed" : False,
                    "payload_raw" : payload_str
                }

                print(requests.post(json_data['downlink_url'], json.dumps(down_data)))

                entry['last_downlink'] = json_data
                entry['last_uplink'] = down_data

                mc.solarpath.stations.replace_one({'device_eui' : json_data['hardware_serial']}, entry, upsert=True)
                return
            except:
                self.send_response(500)
                self.end_headers()
                return

        self.send_response(404)
        return

addr = ('', 8050)
sock = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(addr)
sock.listen(5)

class Thread(threading.Thread):
    def __init__(self, i):
        threading.Thread.__init__(self)
        self.i = i
        self.daemon = True
        self.start()
    def run(self):
        httpd = http.server.HTTPServer(addr, SolarPathHttpRequestHandler, False)
        httpd.socket = sock
        httpd.server_bind = self.server_close = lambda self: None
        httpd.serve_forever()

[Thread(i) for i in range(16)]
time.sleep(9e9)
