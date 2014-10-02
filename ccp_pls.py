from xml.etree import ElementTree

import requests

base_url = 'https://api.eveonline.com'

def key_info(key_id, vcode):
	result = query('/account/APIKeyInfo.xml.aspx', key_id, vcode)
	if not result:
		return
	key = result.find('key')
	info = {
		'type': key.get('type'),
		'accessmask': int(key.get('accessMask')),
		'characters': [],
	}
	for row in key.find('rowset'):
		info['characters'].append({
			'character_id': int(row.get('characterID')),
			'character_name': row.get('characterName'),
			'corporation_id': int(row.get('corporationID')),
			'corporation_name': row.get('corporationName'),
			'alliance_id': int(row.get('allianceID')),
			'alliance_name': row.get('allianceName'),
			'faction_id': int(row.get('factionID')),
			'faction_name': row.get('factionName')
		})
	return info

rs = requests.Session()
def query(endpoint, key_id, vcode, char_id=None):
	response = rs.get(base_url + endpoint, params={'keyID': key_id, 'vCode': vcode, 'characterID': char_id})
	xml = ElementTree.fromstring(response.content)
	return xml.find('result')

def alliance_contact_list(key_id, key_vcode, char_id=None):
	contacts = []
	result = query('/char/ContactList.xml.aspx', key_id, key_vcode, char_id)
	if not result:
		return
	for row in result.find('rowset[@name="allianceContactList"]'):
		contacts.append({
			'contactName': row.get('contactName'),
			'standing': int(row.get('standing')),
			'comments': '',
		})
	return contacts
