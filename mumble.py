#!/usr/bin/env python3

import Ice
Ice.loadSlice('-I/usr/share/Ice/slice', ['/usr/share/slice/Murmur.ice'])
import Murmur

def ice_auth(obj):
	return obj.ice_context({'secret': 'ice'})

class Authenticator(Murmur.ServerAuthenticator):
	def authenticate(self, name, pw, certificates, certhash, certstrong, current=None):
		print(name, pw, current)
		return -2, '', []

	def getInfo(self, id, current=None):
		return False, {}

	def nameToId(self, name, current=None):
		return -2

	def idToName(self, id, corrent=None):
		return ''

	def idToTexture(self, id, corrent=None):
		return []

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
