from xml.etree import ElementTree

from datetime import datetime
from datetime import timedelta
import requests
import pdb


base_url = 'https://api.eveonline.com'

def key_info(key_id, vcode):
	result = query('/account/APIKeyInfo.xml.aspx', key_id, vcode).find('result')
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

def alliance_contact_list(key_id, key_vcode, char_id=None):
	contacts = []
	xml = query('/char/ContactList.xml.aspx', 1188900,'cJvDc3cuvWAuQUKGpDB1Dh44r8bHUTnN6E8SQ9laUIUoMhxstLyyeNbIGg2MqUfv', 92301442)
	if not xml:
		return
	cached_until = datetime.strptime(xml.find('cachedUntil').text, '%Y-%m-%d %H:%M:%S')
	current_time = datetime.strptime(xml.find('currentTime').text, '%Y-%m-%d %H:%M:%S')
	#if timedelta(minutes=15) == (cached_until - current_time):
	result = xml.find('result')
	for row in result.findall('./rowset[@name="allianceContactList"]/'):
		contacts.append({
			'id' : int(row.get('contactID')),
			'contact_name': row.get('contactName'),
			'standing': float(row.get('standing')),
			'type_id': int(row.get('contactTypeID')),
			})
	return contacts
	#return contacts

def query(endpoint, key_id, vcode, char_id=None):
	response = rs.get(base_url + endpoint, params={'keyID': key_id, 'vCode': vcode, 'characterID': char_id})
	xml = ElementTree.fromstring(response.content)
	return xml

