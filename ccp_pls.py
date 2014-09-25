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
def query(endpoint, key_id, vcode):
	response = rs.get(base_url + endpoint, params={'keyID': key_id, 'vCode': vcode})
	xml = ElementTree.fromstring(response.content)
	return xml.find('result')
