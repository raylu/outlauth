#!/usr/bin/env python3

import gevent.monkey
gevent.monkey.patch_all()

import socket

import gevent

def handle_conn(conn, addr):
    print('Connected by', addr)
    while True:
        data = conn.recv(1024)
        if not data: break
        print(data)
    conn.close()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 6667))
s.listen(4)
while True:
    conn, addr = s.accept()
    gevent.spawn(handle_conn, conn, addr)
