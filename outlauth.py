#!/usr/bin/env python3

import gevent.monkey
gevent.monkey.patch_all()

import os

import cleancss
import flask
from flask import request, session
import gevent.wsgi
from sqlalchemy import orm

import ccp_pls
import config
import db

app = flask.Flask(__name__)
app.secret_key = config.secret_key

@app.route('/')
def home():
	user = None
	if 'user_id' in session:
		user = get_current_user()
	return flask.render_template('home.html', user=user)

@app.route('/register', methods=['GET', 'POST'])
def register():
	if request.method == 'GET':
		# step 1
		return flask.render_template('register.html')
	else:
		key_info = check_api_key(request.form['key_id'], request.form['vcode'])
		char_id = request.form.get('character_id')
		username = request.form.get('username')
		password = request.form.get('password')
		email = request.form.get('email')
		if not char_id or not username or not password or not email:
			# step 2
			return flask.render_template('register.html',
					key_id=request.form['key_id'], vcode=request.form['vcode'], characters=key_info['characters'])
		else:
			# step 3
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

@app.route('/admin/add/<id>')
def make_admin(id):
	if 'user_id' in session:
		user = get_current_user()
		if user.user_flag != 1:
			flask.abort(403)
	else:
		flask.abort(403)
	db.session.query(db.User) \
	.filter(db.User.id==int(id)) \
	.update({'user_flag': 1})

	db.session.commit()
	return flask.redirect(flask.url_for('admin'))

@app.route('/admin/remove/<id>')
def remove_admin(id):
	if 'user_id' in session:
		user = get_current_user()
		if user.user_flag != 1:
			flask.abort(403)
	else:
		flask.abort(403)
	db.session.query(db.User) \
	.filter(db.User.id==int(id)) \
	.update({'user_flag': 0})

	db.session.commit()

	return flask.redirect(flask.url_for('admin'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
	admins = None
	non_admins = None
	user = None

	if 'user_id' in session:
		user = get_current_user()

		if user.user_flag != 1:
			flask.abort(403)

		admins = db.session.query(db.User) \
		.filter(db.User.user_flag==1)

		non_admins = db.session.query(db.User) \
		.filter(db.User.user_flag!=1)

	else:
		return flask.redirect(flask.url_for('home'))

	return flask.render_template('admin.html', user=user, admins=admins, non_admins=non_admins)

def get_current_user():
	user = db.session.query(db.User) \
	.filter(db.User.id==session['user_id']) \
	.one()

	return user

def check_api_key(key_id, vcode):
	key_info = ccp_pls.key_info(key_id, vcode)

	error = None
	if not key_info:
		error = 'API key ID and vCode combination were not valid.'
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
		flask.redirect(flask.url_for('register'))
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
	http_server = gevent.wsgi.WSGIServer(('', config.web_port), app)
	http_server.serve_forever()
