#!/usr/bin/env python3

import eventlet
eventlet.monkey_patch()

import operator
import os
import string

import cleancss
import flask
from flask import request, session
import eventlet.wsgi
from collections import defaultdict

import ccp_pls
import config
import db

app = flask.Flask(__name__)
app.secret_key = config.secret_key
flask.Response.autocorrect_location_header = False

@app.route('/')
def home():
	user = entities = groups = None
	if 'user_id' in session:
		user = get_current_user()
		entities = user.entities()
		groups = user.groups(entities)
	return flask.render_template('home.html', user=user, entities=entities, groups=groups)

@app.route('/register', methods=['GET', 'POST'])
def register():
	def step_2():
		return flask.render_template('register.html',
				key_id=request.form['key_id'], vcode=request.form['vcode'], characters=key_info['characters'])

	if request.method == 'GET':
		# step 1
		return flask.render_template('register.html')
	else:
		key_info = check_api_key(request.form['key_id'], request.form['vcode'])
		if not key_info:
			return flask.redirect(flask.url_for('register'))
		char_id = request.form.get('character_id')
		username = request.form.get('username')
		password = request.form.get('password')
		email = request.form.get('email')
		if not char_id or not username or not password or not email:
			if char_id or username or password or email:
				flask.flash('You must pick a character, username, and password and provide an email address.')
			# step 2
			return step_2()
		else:
			# step 3
			for whitespace in string.whitespace:
				if whitespace in username:
					flask.flash('Whitespace is not allowed in usernames.')
					return step_2()
			if '@' not in email or '.' not in email:
					flask.flash("That doesn't look like a valid e-mail address.")
					return step_2()

			char_id = int(char_id)
			for char in key_info['characters']:
				if char['character_id'] == char_id:
					if char['faction_id'] != 500003: # Amarr Empire
						flask.abort(400)
					update_db_for_char(char)
					db.session.commit()
					break
			else:
				flask.abort(400)

			password, salt = db.User.hash_pw(password)
			user = db.User(username=username, password=password, salt=salt, email=email,
					apikey_id=int(request.form['key_id']), apikey_vcode=request.form['vcode'],
					character_id=char_id)
			db.session.add(user)
			db.session.commit()

			session.permanent = True
			session['user_id'] = user.id
			return flask.redirect(flask.url_for('home'))

def check_api_key(key_id, vcode):
	key_info = ccp_pls.key_info(key_id, vcode)

	error = None
	if not key_info:
		error = 'API key ID and vCode combination were not valid.'
	else:
		if key_info['type'] != 'Account':
			error = 'API key must be account-wide, not character-specific.'
		if key_info['accessmask'] & 65405259 != 65405259:
			error = 'API key has insufficient permissions. Please use the create link.'
		for char in key_info['characters']:
			if char['faction_id'] == 500003: # Amarr Empire
				break
		else:
			error = 'No characters on this key are enlisted in the Amarr Militia.'

	if error:
		flask.flash(error)
	else:
		return key_info

def update_db_for_char(char):
	db.session.merge(db.Entity(
		id=char['faction_id'], type='faction', name=char['faction_name']))
	if char['alliance_id']:
		db.session.merge(db.Entity(
			id=char['alliance_id'], type='alliance',
			name=char['alliance_name'], parent_id=char['faction_id']))
		db.session.merge(db.Entity(
			id=char['corporation_id'], type='corporation',
			name=char['corporation_name'], parent_id=char['alliance_id']))
	else:
		db.session.merge(db.Entity(
			id=char['corporation_id'], type='corporation',
			name=char['corporation_name'], parent_id=char['faction_id']))
	db.session.merge(db.Entity(
		id=char['character_id'], type='character',
		name=char['character_name'], parent_id=char['corporation_id']))

@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'GET':
		return flask.render_template('login.html')
	else:
		user =  db.User.login(request.form['username'], request.form['password'])
		if user:
			session['user_id'] = user.id
			return flask.redirect(flask.url_for('home'))
		else:
			flask.flash('Invalid username/password combination.')
			return flask.redirect(flask.url_for('login'))

@app.route('/logout')
def logout():
	try:
		del session['user_id']
	except KeyError:
		pass
	return flask.redirect(flask.url_for('home'))

def admin_route(route): # decorator
	def wrapped():
		if 'user_id' not in session:
			return flask.redirect(flask.url_for('login'))
		user = get_current_user()
		if user.flags != 1:
			flask.abort(403)
		return route()
	return wrapped

@admin_route
@app.route('/admins')
def admins():
	admins = db.session.query(db.User).filter(db.User.flags==1)
	non_admins = db.session.query(db.User).filter(db.User.flags!=1)
	return flask.render_template('admins.html', admins=admins, non_admins=non_admins)

@admin_route
@app.route('/admins/add/<id>')
def admins_add(id):
	db.session.query(db.User).filter(db.User.id==int(id)).update({'flags': 1})
	db.session.commit()
	return flask.redirect(flask.url_for('admins'))

@admin_route
@app.route('/admins/remove/<id>')
def admins_remove(id):
	db.session.query(db.User).filter(db.User.id==int(id)).update({'flags': 0})
	db.session.commit()
	return flask.redirect(flask.url_for('admins'))

@admin_route
@app.route('/groups', methods=['GET', 'POST'])
def groups():
	if request.method == 'GET':
		entities = db.session.query(db.Entity)
		groups = db.session.query(db.Group)
		return flask.render_template('groups.html', entities=entities, groups=groups)
	else:
		group_id = int(request.form['group'])
		gm = db.group_membership
		members = db.session.query(gm).filter_by(group_id=group_id).values(gm.columns['entity_id'])
		member_ids = set(map(operator.itemgetter(0), members))
		entity_ids = set(map(int, request.form.getlist('entities')))
		to_insert = entity_ids - member_ids
		to_delete = member_ids - entity_ids
		if to_insert:
			db.session.execute(gm.insert(),
					list(map(lambda eid: {'group_id': group_id, 'entity_id': eid}, to_insert)))
		if to_delete:
			db.session.execute(gm.delete().where(
					gm.columns['group_id']==group_id).where(gm.columns['entity_id'].in_(to_delete)))
		db.session.commit()
		return flask.redirect(flask.url_for('groups'))

@app.route('/contacts', methods=['GET', 'POST'])
def contacts():
	if 'user_id' not in session:
		return flask.redirect(flask.url_for('login'))
	user = get_current_user()
	entities = user.entities()
	groups = user.groups(entities)
	contacts = []
	if db.Group.diplo not in groups:
		return flask.redirect(flask.url_for('home'))
	if request.method == 'GET':
		contacts = db.session.query(db.Contact)
	if request.method == 'POST':
		save_contacts(request.form)
		return flask.redirect(flask.url_for('contacts'))
	return flask.render_template('contacts.html', user=user, contacts=contacts)

def save_contacts(form):
	form_contacts = defaultdict(list)
	changed = []
	for contact in form:
		form_contacts[int(contact)].append(form[contact])
	for contact in db.session.query(db.Contact):
		if form_contacts[contact.id][0] != contact.comments:
			changed.append(db.Contact(
				id=contact.id,
				name=contact.name,
				standing=contact.standing,
				type_id=contact.type_id,
				comments=form_contacts[contact.id][0],
			))

	for contact in changed:
		db.session.merge(db.Contact(
			id=int(contact.id),
			comments=contact.comments,
		))
	db.session.commit()

@app.route('/update_contacts', methods=(['POST']))
def update_contacts():
	user = get_current_user()
	api_contacts = ccp_pls.alliance_contact_list(user.apikey_id, user.apikey_vcode, user.character_id)
	if api_contacts is None:
		return flask.redirect(flask.url_for('contacts'))

	api_standings = {}
	for contact in api_contacts:
		api_standings[contact['id']] = db.Contact(
			id=contact['id'],
			name=contact['contact_name'],
			standing=contact['standing'],
			type_id=contact['type_id']
		)

	changed = []
	removed = []
	for contact in db.session.query(db.Contact):
		try:
			api_standing = api_standings[contact.id].standing
		except KeyError:
			removed.append(contact)
		else:
			if contact.standing != api_standing:
				contact.standing = api_standing
				changed.append(contact)
			del api_standings[contact.id]

	db.session.add_all(api_standings.values())
	for contact in changed:
		db.session.merge(api_standings[contact.id])
	for contact in removed:
		db.session.delete(contact)
	db.session.commit()

	return flask.redirect(flask.url_for('contacts'))

def get_current_user():
	return db.session.query(db.User).get(session['user_id'])

css_path = os.path.join(os.path.dirname(__file__), 'static', 'css')
@app.route('/css/<filename>')
def css(filename):
	root, _ = os.path.splitext(filename)
	abs_path = os.path.join(css_path, root) + '.ccss'
	with open(abs_path, 'r') as f:
		return cleancss.convert(f), 200, {'Content-Type': 'text/css'}

@app.teardown_appcontext
def shutdown_session(exception=None):
	db.session.remove()

if config.debug:
	app.run(host=config.web_host, port=config.web_port, debug=True)
else:
	listener = eventlet.listen((config.web_host, config.web_port))
	eventlet.wsgi.server(listener, app)
