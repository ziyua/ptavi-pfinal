#!/usr/bin/python
# -*- coding: iso-8859-15 -*-

from xml.sax import make_parser
from xml.sax.handler import ContentHandler
import os
import time
import socket
import sys
import re

# ------------------------------------------
# from xml.sax import make_parser
# from xml.sax.handler import ContentHandler
# ------------------------------------------


class XML_handler(ContentHandler):

    xmlInfo = {}

    def __init__(self, file):
        parser = make_parser()
        parser.setContentHandler(self)
        parser.parse(open(file))

    def startElement(self, name, attrs):
        for attrName in attrs.getNames():
            dic_key = (name[:3] + '_' + attrName).encode('utf-8')
            dic_value = attrs.getValue(attrName).encode('utf-8')
            self.xmlInfo[dic_key] = dic_value

    def l(self, strAttr):
        if strAttr in self.xmlInfo:
            return self.xmlInfo[strAttr]

# --------------------------
# from os.path import exists
# import time
# --------------------------


class log2file:

    def __init__(self, path):
        self.path = path
        self.timeFormat = '%Y%m%d%H%M%S'  # 24Hours
        self.summary = False

    def print2file(self, text):
        if self.summary and len(text.split('\r\n', 1)[1]) > 0:
            text = text.split('\r\n', 1)[0] + ' [...]\r\n'
        print text[:-2]
        # file exists
        Method = 'a'
        if not os.path.exists(self.path):
            Method = 'w'
        # Time format
        Time = time.strftime(self.timeFormat, time.localtime(time.time()))
        # file
        ofile = open(self.path, Method)
        ofile.write(Time + ' ' + text)
        ofile.close()


# -------------
# import socket
# import log2file
# import methodSIP
# -------------


class UAclient_SIP:

    def __init__(self, addr, user, logpath):
        # config:
        self.ver = 'SIP/2.0'
        # Get elemente
        self.addr = addr
        self.user = user
        # recv list
        self.trok = [self.ver, '100', 'Trying', self.ver,
                     '180', 'Ringing', self.ver, '200', 'OK']
        # Log
        self.log = log2file(logpath)
        self.log.print2file('Starting...\r\n')
        # Cliente UDP simple (socket).
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.my_socket.connect(addr)
        # self.my_socket.settimeout(5.0)

    def send(self, Method):
        LINE = '{} sip:{} {}\r\n'.format(Method, self.user, self.ver)
        # --- Add LINE ---
        if Method == 'REGISTER':
            LINE += 'Expires: ' + EXPIRES + '\r\n'
        elif Method == 'INVITE':
            LINE += 'Content-Type: application/sdp\r\n\r\n'
            LINE += 'v=0\r\n' \
                    + 'o=' + self.user + ' ' + IP + ' \r\n' \
                    + 's=misesion\r\n' \
                    + 't=0\r\n' \
                    + 'm=audio ' + PORT_RTP + ' RTP'
        LINE += '\r\n'
        # -- END --
        self.my_socket.send(LINE)
        # -- Debug --
        Debug = 'Sent to {}:{}: {}'.format(self.addr[0], self.addr[1], LINE)
        self.log.print2file(Debug)

    def recv(self, bufferSize=1024):
        try:
            data = self.my_socket.recvfrom(bufferSize)
        except socket.error:
            # -- Debug --
            Debug = 'Error: No server listening at {} port {}\r\n'.format(
                self.addr[0], str(self.addr[1]))
            self.log.print2file(Debug)
        else:
            Debug = 'Received from {}:{}: {}'.format(
                    data[1][0], data[1][1], data[0])
            self.log.print2file(Debug)

            if data[0].split()[:9] == self.trok:
                self.send('ACK')
                # -- RTP -- #
                IPs = data[0].split()[9:][2]
                Ports = int(data[0].split()[9:][-2])
                rtps = toRTP((IPs, Ports), AUDIO, int(PORT_RTP))
                rtps.send()
                rtps.recv()

    def close(self):
        # -- Debug --
        self.my_socket.close()
        self.log.print2file('Finishing.\r\n')


from threading import Thread


class myThread(Thread):
    def __init__(self, func):
        super(myThread, self).__init__()
        self.func = func

    def run(self):
        self.func()


class toRTP:

    def __init__(self, sendAddr, path, recvPort):
        self.addr = sendAddr
        self.path = path
        timeout = 2.0
        # Init socket rtp
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rtpSocket.settimeout(timeout)
        try:
            self.rtpSocket.bind(('', recvPort))
        except:
            raise

    def _send(self):
        # send RTP -> ./mp32rtp
        execute = "./mp32rtp -i {} -p {} < {}".format(
            self.addr[0], str(self.addr[1]), self.path)
        print 'run: ' + execute
        os.system(execute)

    def send(self):
        thread = myThread(self._send)
        thread.start()

    def recv(self, buff=1024):
        while 1:
            try:
                data = self.rtpSocket.recvfrom(buff)
            except socket.timeout:
                break
            except:
                raise
            else:
                print data[0], 'from', data[1]
        self.close()

    """
    def _recv(self):
        thread = myThread(self._recv)
        thread.start()
    """

    def close(self):
        self.rtpSocket.close()


if __name__ == '__main__':
    Method = ['REGISTER', 'INVITE', 'BYE']
    Usage = 'Usage: python uaclient.py config method option'
    if len(sys.argv) != 4 or sys.argv[2] not in Method:
        sys.exit(Usage)

    # xml init
    x = XML_handler(sys.argv[1])

    # xml Get Parametros
    addr = (x.l('reg_ip'), int(x.l('reg_puerto')))
    logpath = x.l('log_path')

    # -- REGISTER --
    if sys.argv[2] == 'REGISTER':
        IPlocal = socket.gethostbyname(socket.gethostname())
        user = '{}@{}:{}'.format(
            x.l('acc_username'), IPlocal, x.l('uas_puerto'))
        try:
            EXPIRES = str(int(sys.argv[3]))
        except ValueError:
            sys.exit(Usage)

    # -- INVITE --
    elif sys.argv[2] == 'INVITE' or 'BYE':
        mat = re.match(r'^\w+@(\w+|\d+(\.\d+){3})$', sys.argv[3].strip())
        if mat is not None:
            IP = socket.gethostbyname(mat.groups()[0])
            user = sys.argv[3]
        else:
            sys.exit(Usage)
        # -- RTP --
        PORT_RTP = x.l('rtp_puerto')
        AUDIO = x.l('aud_path')

    # SIP class Init
    mySip = UAclient_SIP(addr, user, logpath)

    # mySip
    mySip.send(Method=sys.argv[2])
    mySip.recv()
    mySip.close()
