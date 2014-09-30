#!/usr/bin/env python3

import gevent.monkey
gevent.monkey.patch_all()

import errno
import socket

import gevent

users = {}
channels = {}

DEBUG = True

class RPL:
	WELCOME = 1
	YOURHOST = 2
	CREATED = 3
	MYINFO = 4
	WHOISUSER = 311
	ENDOFWHOIS = 318
	NAMREPLY = 353
	ENDOFNAMES = 366
	MOTD_CONTENT = 372
	MOTD_START = 375
	MOTD_END = 376
	UNKNOWNCOMMAND = 421
	NONICKNAMEGIVEN = 431
	ERRONEUSNICKNAME = 432


class ClientMessage:
	''' command, target, text '''
	def __init__(self, line):
		self.line = line

		split = line.split(' ', 2) # this is technically wrong, but works for most things
		self.command = split[0]
		if len(split) > 1:
			self.target = split[1]
		else:
			self.target = None # this shouldn't happen
		self.text = None
		if len(split) > 2 and split[2]:
			self.text = split[2]
			if self.text[0] == ':':
				self.text = self.text[1:]

	def __str__(self):
		return '<ClientMessage>%s' % self.__dict__

class User:
	def __init__(self, conn, addr):
		self.conn = conn
		self.addr = addr
		self.last_buf = None
		self.nick = None
		self.channels = set()

	def handle_conn(self):
		print('connected by', self.addr)
		keep_going = True
		while keep_going:
			try:
				data = self.conn.recv(4096)
			except OSError as e:
				if e.errno in [errno.EBADF, errno.ECONNRESET]:
					self.disconnect()
					break
				raise
			if not data:
				self.disconnect()
				break
			if self.last_buf is not None:
				data = self.last_buf + data
				self.last_buf = None
			lines = data.split(b'\r\n')
			for i in range(len(lines) - 1):
				line = str(lines[i], 'utf-8', 'replace')
				if DEBUG:
					print('<-', line)
				message = ClientMessage(line)
				keep_going = self.handle_message(message)
			last = lines[-1]
			if last:
				self.last_buf = last
		print('disconnecting', self.addr)
		self.conn.close()

	def handle_message(self, msg):
		handler = User.handlers.get(msg.command)
		if handler:
			handler(self, msg)
			if msg.command == 'QUIT':
				return False
		else:
			print('unhandled command', msg)
			self.send(RPL.UNKNOWNCOMMAND)
		return True

	def send(self, command, *args, target=None, source=None):
		if target is None:
			target = self.nick
		if args and ' ' in args[-1]:
			args = list(args)
			args[-1] = ':' + args[-1]
		line = '%s %s %s' % (command, target, ' '.join(args))
		if source is not None:
			line = ':%s %s' % (source, line)
		if DEBUG:
			print('->', line)
		line += '\r\n'
		try:
			self.conn.sendall(line.encode('utf-8'))
		except OSError as e:
			if e.errno in [errno.EBADF, errno.ECONNRESET]:
				self.disconnect()
			else:
				raise

	def disconnect(self):
		for channel in self.channels:
			channel.quit(self)
		self.conn.close()
		if self.nick is not None:
			del users[self.nick]

	# handlers

	def nick(self, msg):
		if not msg.target:
			self.send(RPL.NONICKNAMEGIVEN)
		elif self.nick is None:
			self.nick = msg.target
			users[self.nick] = self
		else:
			self.send(RPL.ERRONEUSNICKNAME, 'You cannot change your nick from your auth username.')

	def user(self, msg):
		self.send(RPL.WELCOME, 'Welcome to outlauth')
		self.send(RPL.YOURHOST, 'Your host is outlauth, running version 0.0')
		self.send(RPL.CREATED, 'The server was created today')
		self.send(RPL.MYINFO, 'outlauth 0.0')
		self.send(RPL.MOTD_START, '*** Message of the day:')
		self.send(RPL.MOTD_CONTENT, 'This is the message of the day, bitch')
		self.send(RPL.MOTD_END, '*** End of message of the day')

	def mode(self, msg):
		if not self.nick:
			return

	def whois(self, msg):
		if not msg.target:
			return
		self.send(RPL.WHOISUSER, msg.target + '? ? * :?')
		self.send(RPL.ENDOFWHOIS, 'End of WHOIS list')

	def join(self, msg):
		if not self.nick or not msg.target:
			return
		if msg.target not in channels:
			channels[msg.target] = channel = Channel(msg.target)
		else:
			channel = channels[msg.target]
			if channel in self.channels:
				return
		channel.join(self)
		self.channels.add(channel)
		names = ' '.join((str(user.nick) for user in channel.users))
		self.send(RPL.NAMREPLY, '@', channel.name, names)
		self.send(RPL.ENDOFNAMES, channel.name, 'End of /NAMES list')

	def part(self, msg):
		if not self.nick or msg.target not in channels:
			return
		channel = channels[msg.target]
		if channel not in self.channels:
			return
		channel.part(self)
		self.channels.remove(channel)

	def privmsg(self, msg):
		if not self.nick:
			return
		channel = channels[msg.target]
		channel.privmsg(self, msg.text)

	def quit(self, msg):
		self.disconnect()

	handlers = {
		'NICK': nick,
		'USER': user,
		'MODE': mode,
		'WHOIS': whois,
		'JOIN': join,
		'PART': part,
		'PRIVMSG': privmsg,
		'QUIT': quit,
	}

	def __hash__(self):
		return hash(self.nick)

class Channel:
	def __init__(self, name):
		self.name = name
		self.users = set()

	def join(self, user):
		self.users.add(user)
		for u in self.users:
			gevent.spawn(u.send, 'JOIN', target=self.name, source=user.nick)

	def part(self, user):
		for u in self.users:
			gevent.spawn(u.send, 'PART', target=self.name, source=user.nick)
		self.users.remove(user)

	def quit(self, user):
		self.users.remove(user)
		for u in self.users:
			if user is u:
				continue
			gevent.spawn(u.send, 'QUIT', target='', source=user.nick)

	def privmsg(self, user, text):
		for u in self.users:
			if user is u:
				continue
			gevent.spawn(u.send, 'PRIVMSG', text, target=self.name, source=user.nick)

	def __hash__(self):
		return hash(self.name)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 6667))
s.listen(4)
try:
	while True:
		conn, addr = s.accept()
		user = User(conn, addr)
		gevent.spawn(user.handle_conn)
except KeyboardInterrupt:
	print('closing all connections')
	for user in list(users.values()):
		user.disconnect()
