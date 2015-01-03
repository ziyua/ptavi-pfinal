#!/usr/bin/python
# -*- coding: iso-8859-15 -*-

import SocketServer
import time
import sys
import re

from os import path
from uaclient import XML_handler
from uaclient import log2file


class ProxyHandler(SocketServer.DatagramRequestHandler):

    Ver = r'SIP/2.0'

    # PROTOCOL client request
    ALLOW = r'INVITE|ACK|BYE|CANCEL|OPTIONS|REGISTER'
    USERSIP = r'sip:(\w+@([\w\.]+|\d+(\.\d+){3}))(:\d+){0,1}'
    REQUEST = r'^(' + ALLOW + r')\s' + USERSIP + r'\s' + Ver

    # PROTOCOL Serv reply
    REPLY = '^' + Ver + r'\s\d{3}(\s\w+)+'
    TROK = [Ver, '100', 'Trying', Ver, '180', 'Ringing', Ver, '200', 'OK']

    # List Global
    Users = {}
    Callings = {}

    def reply(self, message):
        ip, port = self.client_address
        self.wfile.write(message)
        # LOG
        LOG.print2file('send to {}:{}: {}'.format(ip, port, repr(message)))

    def forward(self, message, to):
        ip, port = to
        self.socket.sendto(message, to)
        # LOG
        LOG.print2file('send to {}:{}: {}'.format(ip, port, repr(message)))

    def register2file(self):
        # DATPATH = xml.getInfo('dat_path')
        ofile = open(DATPATH, 'w')
        style = '{} \t {} \t {} \t {} \t {}\r\n'
        ofile.write(style.format('User', 'IP', 'Port', 'Date', 'Expiration'))
        for userSIP, userInfo in self.Users.items():
            ofile.write(style.format(userSIP,
                                     userInfo['Addr'][0],
                                     userInfo['Addr'][1],
                                     time.strftime(
                                         '%Y-%m-%d %H:%M:%S',
                                         time.gmtime(userInfo['Time'][0])),
                                     userInfo['Time'][1]),)
        ofile.close()

    def handle(self):
        # Expired Users
        Now = time.time()
        for userSIP in self.Users.keys():
            if Now > sum(self.Users[userSIP]['Time']):
                del self.Users[userSIP]

        while 1:
            line = self.rfile.read()
            if not line:
                break

            # LOG
            ip, port = self.client_address
            LOG.print2file(
                'Received from {}:{}: {}'.format(ip, port, repr(line)))

            try:
                head, body = line.rsplit('\r\n\r\n', 1)
            except ValueError:
                self.reply('SIP/2.0 400 Bad Request\r\n\r\n')
                break

            # if lines:
            isRequest = re.match(self.REQUEST, head.split('\r\n')[0])
            isReply = head.split() == self.TROK \
                or re.match(self.REPLY, head.split('\r\n')[0])
            if not isRequest and not isReply:
                self.reply('SIP/2.0 400 Bad Request\r\n\r\n')
                break
            # ------------------------------------------------
            # if is request receive from client send to server
            # ------------------------------------------------
            elif isRequest:
                Info = isRequest.groups()
                Method, userSIP = Info[:2]
                # -- REGISTER --
                if Method == 'REGISTER':
                    print '-- register --'
                    IP = self.client_address[0]
                    Port = Info[-1] and int(Info[-1][1:])
                    Now = time.time()
                    try:
                        Expires = int(head.split()[-1])
                    except ValueError:
                        self.reply('SIP/2.0 400 Bad Request\r\n\r\n')
                        break
                    else:
                        self.reply('SIP/2.0 200 OK\r\n\r\n')
                        if Expires != 0:
                            # Register User or Update
                            user = self.Users[userSIP] = {}
                            user['Addr'] = IP, Port
                            user['Time'] = Now, Expires
                        elif userSIP in self.Users:
                            del self.Users[userSIP]
                            for sips in self.Callings:
                                if userSIP in sips:
                                    del self.Callings[sips]
                                    break
                        self.register2file()
                elif userSIP not in self.Users:
                    self.reply('SIP/2.0 404 User Not Found\r\n\r\n')
                    break
                else:
                    user = self.Users[userSIP]
                    # INVITE
                    if Method == 'INVITE':
                        print '-- Invite --'
                        self.forward(line, user['Addr'])
                        if len(body) != 0 \
                            and len(body.split()) >= 2 \
                                and 'o=' in body.split()[1]:
                            userCall = body.split()[1].split('=')[1]
                        # calling = (call, called)
                        sips = (userCall, userSIP)
                        ips = [self.client_address, user['Addr']]
                        self.Callings[sips] = ips
                    elif Method == 'BYE':
                        print '-- Bye --'
                        for sips in self.Callings:
                            if user['Addr'] == self.Callings[sips][1]:
                                self.Callings[sips][0] = self.client_address
                                break
                        else:
                            self.reply('SIP/2.0 481 Call/Transaction '
                                       + 'Does Not Exist\r\n\r\n')
                            break
                        self.forward(line, user['Addr'])
                    elif Method == 'ACK':
                        print '-- Ack --'
                        self.forward(line, user['Addr'])
                    # - others - method not allowed
                    else:
                        self.reply('SIP/2.0 405 Method Not Allowed\r\n\r\n')
            # ----------------------------------------------
            # is Reply, recieve from server, send to client:
            # ----------------------------------------------
            elif isReply:
                # know: self.client_address
                for ips in self.Callings.values():
                    if self.client_address == ips[1]:
                        # Allowing only one communication.(a,b),(c,b) not ok.
                        clientAddr = ips[0]
                        break
                else:
                    # print 'Call/Transaction Does Not Exist'  # SIP/2.0 481
                    break

                self.forward(line, clientAddr)

    def finish(self):
        if self.wfile.getvalue() != '':
            self.socket.sendto(self.wfile.getvalue(), self.client_address)

if __name__ == '__main__':
    Usage = 'Usage: python proxy_registrar.py config'
    if len(sys.argv) != 2 or not path.exists(sys.argv[1]):
        sys.exit(Usage)

    xml = XML_handler(sys.argv[1])
    name = xml.getInfo('ser_name') == '' \
        and ' ' or (' ' + xml.getInfo('ser_name') + ' ')
    addr = ip, port = xml.getInfo('ser_ip'), int(xml.getInfo('ser_puerto'))
    DATPATH = xml.getInfo('dat_path')
    # LOG
    LOG = log2file(xml.getInfo('log_path'))
    LOG.print2file('starting...')

    serv = SocketServer.UDPServer(addr, ProxyHandler)
    print 'Server{}listening at port {}...'.format(name, port)
    try:
        serv.serve_forever()
    except KeyboardInterrupt:
        LOG.print2file('Finishing...')
