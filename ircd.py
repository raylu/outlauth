#!/usr/bin/env python3

import gevent.monkey
gevent.monkey.patch_all()

import socket

import gevent

class Commands:
    USER = b'USER'
    MODE = b'MODE'
    PING = b'PING'
    PONG = b'PONG'
    WHOIS = b'WHOIS'
    JOIN = b'JOIN'
    QUIT = b'QUIT'

class ReplyCodes:
    WELCOME = 1
    MOTD_CONTENT = 372
    MOTD_START = 375
    MOTD_END = 376

class User:
    def __init__(self, conn, username):
        self.conn = conn
        self.username = username

    @classmethod
    def parse_username(self, message):
        username = message.split(b' ')[1]
        return username

    def _format_message(self, code, message):
        return ':outlauth {} {} :{}\r\n'.format(code, self.username, message)

    def send_message(self, message):
        self.conn.sendall(bytearray(message, 'utf-8'))

    def send_notice(self, message):
        message = self._format_message('NOTICE', message)
        self.send_message(message)

    def send_reply(self, code, message):
        message = self._format_message(code, message)
        self.send_message(message)

    def respond_to_mode(self):
        self.send_message('{0} MODE {0} :+i'.format(self.username))

    def respond_to_whois(self):
        self.send_message('{0} 318 {0} :+i'.format(self.username))

def get_command(message):
    return message[0:4]

def handle_conn(conn, addr):
    print('Connected by', addr)
    user = None
    while True:
        data = conn.recv(1024)
        if not data: break
        print(data)
        messages = data.splitlines()
        for message in messages:
            cmd = get_command(message)
            if cmd == Commands.USER:
                username = User.parse_username(message)
                user = User(conn, username)
                user.send_notice('*** Connected')
                user.send_reply(ReplyCodes.WELCOME, 'Welcome to outlauth')
                user.send_reply(ReplyCodes.MOTD_START, '*** Message of the Day:')
                user.send_reply(ReplyCodes.MOTD_CONTENT, 'This is the message of the day, bitch')
                user.send_reply(ReplyCodes.MOTD_END, '*** End of Message of the Day')
            elif cmd == Commands.MODE:
                user.respond_to_mode()
            elif cmd == Commands.WHOIS:
                user.respond_to_whois()
    conn.close()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 6667))
s.listen(4)
while True:
    conn, addr = s.accept()
    gevent.spawn(handle_conn, conn, addr)
