#!/usr/bin/env python3

import operator
import random

import Ice
Ice.loadSlice('-I/usr/share/Ice/slice', ['/usr/share/slice/Murmur.ice'])
import Murmur
from sqlalchemy.orm.exc import NoResultFound

import db

class Authenticator(Murmur.ServerAuthenticator):
	def authenticate(self, name, pw, certificates, certhash, certstrong, current=None):
		try:
			new_name = ''

			if name == 'raylu-bot' and pw == 'bot':
				return 0, new_name, []

			try:
				db.session.query(db.User).filter(db.User.username==name).one()
			except NoResultFound:
				new_name = '[G] ' + name
				return random.randint(1000000000, 2147483647), new_name, [] # guest

			user = db.User.login(name, pw)
			if not user:
				return -1, new_name, [] # bad password for registered user

			entities = user.entities()
			groups = user.groups(entities)
			group_names = list(map(operator.attrgetter('name'), groups))
			if user.flags == 1:
				group_names.append('admin')
			return user.id, new_name, group_names # regular login
		finally:
			db.session.remove()

	def getInfo(self, id, current=None):
		return False, {}

	def nameToId(self, name, current=None):
		return -2

	def idToName(self, id, corrent=None):
		return ''

	def idToTexture(self, id, corrent=None):
		return []

def ice_auth(obj):
	return obj.ice_context({'secret': 'ice'})

ice = Ice.initialize()
meta = Murmur.MetaPrx.checkedCast(ice.stringToProxy('Meta:tcp -h 127.0.0.1 -p 6502'))
meta = ice_auth(meta)
adapter = ice.createObjectAdapterWithEndpoints('Callback.Client', 'tcp -h 127.0.0.1')
adapter.activate()
server = ice_auth(meta.getBootedServers()[0])
authenticator = Authenticator()
server_authenticator = Murmur.ServerAuthenticatorPrx.uncheckedCast(adapter.addWithUUID(authenticator))
server_authenticator = ice_auth(server_authenticator)
server.setAuthenticator(server_authenticator)

try:
	ice.waitForShutdown()
finally:
	ice.shutdown()
