#!/usr/bin/env python3

import eventlet
eventlet.monkey_patch()

import atexit
from datetime import timedelta, datetime
import errno
import socket

from sqlalchemy import orm

import config
import db

users = {}
channels = {}

DEBUG = True

class RPL:
	WELCOME = 1
	YOURHOST = 2
	CREATED = 3
	MYINFO = 4
	WHOISUSER = 311
	WHOWASUSER = 314
	ENDOFWHO = 315
	ENDOFWHOIS = 318
	CHANNELMODEIS = 324
	WHOREPLY = 352
	NAMREPLY = 353
	ENDOFNAMES = 366
	ENDOFBANLIST = 368
	ENDOFWHOWAS = 369
	MOTD_CONTENT = 372
	MOTD_START = 375
	MOTD_END = 376
	NOSUCHCHANNEL = 403
	WASNOSUCHNICK = 406
	UNKNOWNCOMMAND = 421
	NONICKNAMEGIVEN = 431
	ERRONEUSNICKNAME = 432
	NOTREGISTERED = 451
	UNKNOWNMODE = 472
	UMODEUNKNOWNFLAG = 501
	USERSDONTMATCH = 502

class ClientMessage:
	''' command, target, text '''
	def __init__(self, line):
		self.line = line

		split = line.split(' ', 2) # this is technically wrong, but works for most things
		self.command = split[0]
		if len(split) > 1:
			self.target = split[1]
			if len(split) == 2 and self.target[0] == ':':
				self.target = self.target[1:]
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
		self.recv_greenlet = self.send_greenlet = None
		self.send_queue = eventlet.queue.LightQueue()
		self.last_buf = None
		self.nick = self.user = self.host = self.real_name = self.source = self.groups = None
		self.password = None
		self.channels = set()
		self.last_recv_time = None

	def handle_conn(self):
		print('connected by', self.addr)
		self.recv_greenlet = eventlet.getcurrent()
		self.send_greenlet = eventlet.spawn(self.handle_send_queue)
		self.last_recv_time = datetime.utcnow()
		while True:
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
				self.handle_message(message)
			last = lines[-1]
			if last:
				self.last_buf = last

	def handle_send_queue(self):
		while True:
			line = self.send_queue.get()
			try:
				self.conn.sendall(line.encode('utf-8'))
			except OSError as e:
				if e.errno in [errno.EBADF, errno.ECONNRESET]:
					self.disconnect()
				else:
					raise

	def handle_message(self, msg):
		self.last_recv_time = datetime.utcnow()
		handler = User.handlers.get(msg.command)
		if handler:
			handler(self, msg)
		else:
			print('unhandled command', msg)
			self.send(RPL.UNKNOWNCOMMAND)

	def send(self, command, *args, target=None, source=None):
		if target is None:
			target = self.nick
		if args and (' ' in args[-1] or args[-1].startswith(':')):
			args = list(args)
			args[-1] = ':' + args[-1]
		line = '%s %s %s' % (command, target, ' '.join(args))
		if source is not None:
			line = ':%s %s' % (source, line)
		if DEBUG:
			print('->', line)
		line += '\r\n'
		self.send_queue.put_nowait(line)

	def disconnect(self):
		print('disconnecting', self.addr)
		current_greenlet = eventlet.getcurrent()
		for greenlet in [self.recv_greenlet, self.send_greenlet]:
			# we might be called by handle_conn/quit, handle_send_queue, or ping_all/disconnect_all
			if greenlet is not current_greenlet:
				greenlet.kill()

		for channel in self.channels:
			channel.quit(self)
		self.conn.close()
		try:
			del users[self.nick]
		except KeyError:
			pass

	def check_timeout(self):
		since = datetime.now() - self.last_recv_time
		if since >= timedelta(minutes=4):
			self.disconnect()
		elif since >= timedelta(minutes=3):
			self.send('PING', target=self.nick)

	# handlers

	def pass_handler(self, msg):
		self.password = msg.target

	def nick(self, msg):
		if not msg.target:
			self.send(RPL.NONICKNAMEGIVEN)
		elif not self.password:
			self.send(RPL.ERRONEUSNICKNAME, 'No password specified.')
		elif msg.target in users:
			self.send(RPL.ERRONEUSNICKNAME, 'Already a User connected')
			self.disconnect()
		elif self.nick is None:
			try:
				user = db.User.login(msg.target, self.password)
				if not user:
					self.send(RPL.ERRONEUSNICKNAME, 'Invalid nick/password combination.')
					self.disconnect()
					return
				entities = user.entities()
				self.real_name = entities['character'].name
				self.user = self.real_name.replace(' ', '_')
				self.host = entities['corporation'].name.replace(' ', '.')
				self.nick = msg.target
				self.source = '%s!%s@%s' % (self.nick, self.user, self.host)
				self.groups = user.groups(entities)
			finally:
				db.session.remove()
			users[self.nick] = self
		else:
			self.send(RPL.ERRONEUSNICKNAME, 'You cannot change your nick from your auth username.')

	def user(self, msg):
		if not self.nick:
			self.send(RPL.NOTREGISTERED, 'You have not registered')
			return
		self.send(RPL.WELCOME, 'Welcome to outlauth')
		self.send(RPL.YOURHOST, 'Your host is outlauth, running version 0.0')
		self.send(RPL.CREATED, 'The server was created today')
		self.send(RPL.MYINFO, 'outlauth 0.0')
		self.send(RPL.MOTD_START, '*** Message of the day:')
		self.send(RPL.MOTD_CONTENT, 'This is the message of the day.')
		self.send(RPL.MOTD_END, '*** End of message of the day')

		for group in self.groups:
			if group.name == 'grim sleepers':
				self._join('#grimsleepers')
				break

	def mode(self, msg):
		if not self.nick or not msg.target:
			return
		if msg.target.startswith('#'):
			channel = channels.get(msg.target)
			if not channel:
				self.send(RPL.NOSUCHCHANNEL, msg.target, 'No such channel')
			else:
				if not msg.text:
					self.send(RPL.CHANNELMODEIS, channel.name, '+nt')
				elif msg.text in ['+b', 'b']:
					self.send(RPL.ENDOFBANLIST, channel.name, 'End of channel ban list')
				else:
					self.send(RPL.UNKNOWNMODE, 'Setting modes is not implemented')
		else:
			if msg.target == self.nick:
				self.send(RPL.UMODEUNKNOWNFLAG, 'Unknown MODE flag')
			else:
				self.send(RPL.USERSDONTMATCH, 'Cannot change mode for other users')

	def who(self, msg):
		if not msg.target:
			return
		channel = channels.get(msg.target)
		if not channel:
			self.send(RPL.NOSUCHCHANNEL, msg.target, 'No such channel')
		else:
			for user in channel.users:
				self.send(RPL.WHOREPLY, channel.name, user.user, user.host, 'outlauth', user.nick,
						'H', '0 ' + user.real_name) # here, hopcount 0
			self.send(RPL.ENDOFWHO, channel.name, 'End of WHO list.')

	def whois(self, msg):
		if not msg.target:
			return
		user = users.get(msg.target)
		if user:
			self.send(RPL.WHOISUSER, user.nick, user.user, user.host, '*', user.real_name)
			self.send(RPL.ENDOFWHOIS, 'End of WHOIS list')
		else:
			try:
				db_user = db.session.query(db.User).filter(db.User.username==msg.target) \
						.options(orm.joinedload('character').joinedload('parent')).first()
				if db_user:
					real_name = db_user.character.name
					host = db_user.character.parent.name.replace(' ', '.')
					user_user = real_name.replace(' ', '_')
					self.send(RPL.WHOWASUSER, db_user.username, user_user, host, '*', real_name)
					self.send(RPL.ENDOFWHOWAS, 'End of WHOWAS')
				else:
					self.send(RPL.WASNOSUCHNICK, 'There is no user by the name ' + msg.target)
			finally:
				db.session.remove()

	def join(self, msg):
		if not self.nick or not msg.target:
			return
		self._join(msg.target)

	def _join(self, chan_name):
		if chan_name not in channels:
			channels[chan_name] = channel = Channel(chan_name)
		else:
			channel = channels[chan_name]
			if channel in self.channels:
				return
		channel.join(self)
		self.channels.add(channel)

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

	def pong(self, msg):
		# amusingly, we don't actually need to do anything here
		pass

	handlers = {
		'PASS': pass_handler,
		'NICK': nick,
		'USER': user,
		'MODE': mode,
		'WHOIS': whois,
		'WHO': who,
		'JOIN': join,
		'PART': part,
		'PRIVMSG': privmsg,
		'QUIT': quit,
		'PONG': pong,
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
			if user is u:
				continue
			u.send('JOIN', target=self.name, source=user.source)
		user.send('JOIN', target=self.name, source=user.source)

		names = []
		for x in self.users:
			names.append(x.nick)
			if len(names) == 10:
				user.send(RPL.NAMREPLY, '@', self.name, ' '.join(names), source=config.irc_host)
				names.clear()

		if len(names) > 0:
		    user.send(RPL.NAMREPLY, '@', self.name, ' '.join(names), source=config.irc_host)
		user.send(RPL.ENDOFNAMES, self.name, 'End of /NAMES list')

	def part(self, user):
		for u in self.users:
			u.send('PART', target=self.name, source=user.source)
		self.users.remove(user)

	def quit(self, user):
		self.users.remove(user)
		for u in self.users:
			if user is u:
				continue
			u.send('QUIT', target='', source=user.source)

	def privmsg(self, user, text):
		for u in self.users:
			if user is u:
				continue
			u.send('PRIVMSG', text, target=self.name, source=user.nick)

	def __hash__(self):
		return hash(self.name)

def ping_all():
	while True:
		for user in list(users.values()):
			user.check_timeout()
		eventlet.sleep(60)

def disconnect_all():
	print('closing all connections')
	for user in list(users.values()):
		user.recv_greenlet.kill()
		user.disconnect()

def main():
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	s.bind((config.irc_host, 6667))
	s.listen(4)

	eventlet.spawn(ping_all)
	atexit.register(disconnect_all)

	while True:
		conn, addr = s.accept()
		user = User(conn, addr)
		eventlet.spawn(user.handle_conn)

if __name__ == '__main__':
	main()
