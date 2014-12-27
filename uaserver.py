#!/usr/bin/python
# -*- coding: iso-8859-15 -*-

import SocketServer
import socket
import sys
import re

from uaclient import XML_handler
from uaclient import toRTP
from os import path


class UAhandler(SocketServer.DatagramRequestHandler):

    ALLOW = r'INVITE|ACK|BYE|CANCEL|OPTIONS|REGISTER'
    USERSIP = r'sip:(\w+@(\w+|\d+(\.\d+){3}))(:\d+){0,1}'
    PROTOCOL = r'^(' + ALLOW + r')\s' + USERSIP + r'\sSIP/2.0'
    sdp = {}

    def handle(self):
        while 1:
            line = self.rfile.read()
            if not line:
                break

            try:
                head, body = line.split('\r\n\r\n')
            except ValueError:
                self.wfile.write('SIP/2.0 400 Bad Request\r\n\r\n')

            # if lines:
            mat = re.match(self.PROTOCOL, head.split('\r\n')[0])
            if not mat:
                self.wfile.write('SIP/2.0 400 Bad Request\r\n\r\n')
            else:
                Method, userSIP = mat.groups()[:2]
                # Body: # -- SDP -- #
                if len(head.split('\r\n')) != 1 \
                        and head.split(
                            '\r\n')[1] == 'Content-Type: application/sdp':
                    # process Body
                    sdp = self.sdp[userSIP] = {}
                    for label in body.strip().split('\r\n'):
                        key, value = label.split('=')
                        sdp[key] = value.split()

                # Head: # -- Head Allows -- #
                if Method == 'INVITE':
                    userIP = socket.gethostbyname(ip_local)
                    message = 'SIP/2.0 100 Trying\r\n\r\n' \
                              + 'SIP/2.0 180 Ringing\r\n\r\n' \
                              + 'SIP/2.0 200 OK\r\n\r\n' \
                              + 'v=0\r\n' \
                              + 'o=' + USER + ' ' + userIP + ' 127.0.0.1\r\n' \
                              + 's=misesion\r\n' \
                              + 't=0\r\n' \
                              + 'm=audio ' + RTPORT + ' RTP\r\n'
                    self.wfile.write(message)
                elif Method == 'BYE':
                    self.wfile.write('SIP/2.0 200 OK\r\n\r\n')
                elif Method == 'ACK':
                    # Send RTP #
                    sdp = self.sdp[userSIP]
                    addr = sdp['o'][1], int(sdp['m'][1])
                    rtp = toRTP(addr, AUDIO, int(RTPORT))
                    rtp.send()
                    rtp.recv()
                else:
                    self.wfile.write('SIP/2.0 405 Method Not Allowed\r\n\r\n')

if __name__ == '__main__':

    # Usage
    Usage = 'Usage: python uaserver.py config'
    if len(sys.argv) != 2 or not path.exists(sys.argv[1]):
        sys.exit(Usage)

    # xml
    xml = XML_handler(sys.argv[1])

    # variables
    addr = xml.xmlInfo['uas_ip'], int(xml.xmlInfo['uas_puerto'])

    # global
    ip_local = xml.xmlInfo['uas_ip'] == '' \
        and '127.0.0.1' or xml.xmlInfo['uas_ip']
    USER = '{}@{}'.format(xml.xmlInfo['acc_username'], ip_local)
    RTPORT = xml.xmlInfo['rtp_puerto']
    AUDIO = xml.xmlInfo['aud_path']

    # Socket Server
    serv = SocketServer.UDPServer(addr, UAhandler)
    print "Listening at port {}...".format(str(addr[1]))
    serv.serve_forever()
