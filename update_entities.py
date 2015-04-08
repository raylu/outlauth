#!/usr/bin/env python3

import time

import ccp_pls
import db

def check_api_key(key_id, vcode):
	key_info = ccp_pls.key_info(key_id, vcode)

	if not key_info:
		raise InvalidAPI('API key ID and vCode combination were not valid.')
	if key_info['type'] != 'Account':
		raise InvalidAPI('API key must be account-wide, not character-specific.')
	if key_info['accessmask'] & 65405275 != 65405275:
		raise InvalidAPI('API key has insufficient permissions. Please use the create link.')

	return key_info

def update_for_char(char):
	if char['alliance_id']:
		db.session.merge(db.Entity(
			id=char['alliance_id'], type='alliance', name=char['alliance_name']))
		db.session.commit()

	corporation = db.Entity(
		id=char['corporation_id'], type='corporation', name=char['corporation_name'])
	if char['alliance_id']:
		corporation.parent_id = char['alliance_id']
	db.session.merge(corporation)
	db.session.commit()

	db.session.merge(db.Entity(
		id=char['character_id'], type='character',
		name=char['character_name'], parent_id=char['corporation_id']))
	db.session.commit()

class InvalidAPI(Exception):
	def __init__(self, message):
		self.message = message

def main():
	for user in db.session.query(db.User):
		try:
			key_info = check_api_key(user.apikey_id, user.apikey_vcode)
		except InvalidAPI as e:
			user.character.parent_id = None
			print('%s: %s' % (user.username, e.message))
			continue
		for char in key_info['characters']:
			if char['character_id'] == user.character_id:
				update_for_char(char)
				break
		else:
			# couldn't find the character
			user.character.parent_id = None
			print(user.username + ": Key didn't have the character we were looking for.")
		time.sleep(1)

if __name__ == '__main__':
	main()
