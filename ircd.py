#!/usr/bin/env python3

import gevent.monkey
gevent.monkey.patch_all()

import errno
import socket

import gevent

users = {}
channels = {}

DEBUG = True

class Commands:
	USER = 'USER'
	NICK = 'NICK'
	MODE = 'MODE'
	PING = 'PING'
	PONG = 'PONG'
	WHOIS = 'WHOIS'
	JOIN = 'JOIN'
	QUIT = 'QUIT'
	PRIVMSG = 'PRIVMSG'

class ReplyCodes:
	WELCOME = 1
	YOURHOST = 2
	CREATED = 3
	MYINFO = 4
	MOTD_CONTENT = 372
	MOTD_START = 375
	MOTD_END = 376

class User:
	def __init__(self, conn, addr, username=None):
		self.conn = conn
		self.addr = addr
		self.username = username
		self.channels = []

	@classmethod
	def parse_username(self, message):
		username = message.split(' ')[1]
		return username

	def _format_message(self, code, message):
		return ':outlauth {} {} :{}'.format(code, self.username, message)

	def send_message(self, message):
		if DEBUG:
			print('->', message)
		message = message + '\r\n'
		try:
			self.conn.sendall(message.encode('utf-8'))
		except OSError as e:
			if e.errno in [errno.EBADF, errno.ECONNRESET]:
				self.disconnect()
			else:
				raise

	def privmsg(self, message):
		if not self.username:
			return
		_, channel_name, message = message.split(' ', 2)
		channel = channels[channel_name]
		channel.message(self, message)

	def send_notice(self, message):
		message = self._format_message('NOTICE', message)
		self.send_message(message)

	def send_reply(self, code, message):
		message = self._format_message(code, message)
		self.send_message(message)

	def set_mode(self):
		self.send_message('{0} MODE {0} :+i'.format(self.username))

	def whois(self):
		self.send_message(':outlauth 311 {0} {0} outlauth * :dude'.format(self.username))
		self.send_message(':outlauth 318 {0} :End of WHOIS list'.format(self.username))

	def join_channel(self, message):
		message = message.split(' ')
		if len(message) > 1:
			channel_name = message[1]
			if channel_name not in channels:
				channels[channel_name] = channel = Channel(channel_name)
			else:
				channel = channels[channel_name]
				if channel in self.channels:
					return
			channel.add_user(self)
			self.channels.append(channel)
			names = ' '.join((str(user.username) for user in channel.users))
			self.send_message(':outlauth 353 {0} @ {0} :names'.format(channel.name, names))
			self.send_message(':outlauth 366 {0} {0} :End of /NAMES list')

	def disconnect(self):
		for channel in self.channels:
			channel.remove_user(self)
		self.conn.close()
		del users[self.username]

class Channel:
	def __init__(self, name):
		self.name = name
		self.users = []

	def add_user(self, user):
		self.users.append(user)

	def remove_user(self, user):
		self.users.remove(user)

	def message(self, user, message):
		line = ':{} PRIVMSG {} :{}'.format(user.username, self.name, message)
		for u in self.users:
			if user is u:
				continue
			u.send_message(line)

def get_command(message):
	return message.split(' ')[0]

def run_command(user, cmd, message):
	if cmd == Commands.NICK:
		username = User.parse_username(message)
		user.username = username
		users[username] = user
		user.send_notice('*** Nick set to {}'.format(user.username))
	elif cmd == Commands.USER:
		user.send_notice('*** Connected')
		user.send_reply(ReplyCodes.WELCOME, 'Welcome to outlauth')
		user.send_reply(ReplyCodes.YOURHOST, 'Your host is outlauth, running version 0.0')
		user.send_reply(ReplyCodes.CREATED, 'The server was created today')
		user.send_reply(ReplyCodes.MYINFO, 'outlauth 0.0')
		user.send_reply(ReplyCodes.MOTD_START, '*** Message of the Day:')
		user.send_reply(ReplyCodes.MOTD_CONTENT, 'This is the message of the day, bitch')
		user.send_reply(ReplyCodes.MOTD_END, '*** End of Message of the Day')
	elif cmd == Commands.QUIT:
		user.disconnect()
		return False
	elif user.username is not None:
		if cmd == Commands.MODE:
			user.set_mode()
		elif cmd == Commands.WHOIS:
			user.whois()
		elif cmd == Commands.JOIN:
			user.join_channel(message)
		elif cmd == Commands.PRIVMSG:
			user.privmsg(message)
	return True

def handle_conn(conn, addr):
	print('connected by', addr)
	user = User(conn, addr)
	keep_going = True
	while keep_going:
		try:
			data = conn.recv(1024)
		except OSError as e:
			if e.errno in [errno.EBADF, errno.ECONNRESET]:
				user.disconnect()
				break
			raise
		if not data:
			break
		messages = data.splitlines()
		for message in messages:
			message = message.decode('utf-8')
			if DEBUG:
				print('<-', message)
			cmd = get_command(message)
			keep_going = run_command(user, cmd, message)
	print('disconnecting', addr)
	conn.close()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 6667))
s.listen(4)
try:
	while True:
		conn, addr = s.accept()
		gevent.spawn(handle_conn, conn, addr)
except KeyboardInterrupt:
	print('closing all connections')
	for user in list(users.values()):
		user.disconnect()
