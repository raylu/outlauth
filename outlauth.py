#!/usr/bin/env python3

import gevent.monkey
gevent.monkey.patch_all()

import os

import cleancss
import flask
import gevent.wsgi

import config

app = flask.Flask(__name__)

@app.route('/')
def home():
	return flask.render_template('home.html')

css_path = os.path.join(os.path.dirname(__file__), 'static', 'css')
@app.route('/css/<filename>')
def css(filename):
	root, _ = os.path.splitext(filename)
	abs_path = os.path.join(css_path, root) + '.ccss'
	with open(abs_path, 'r') as f:
		return cleancss.convert(f), 200, {'Content-Type': 'text/css'}

if config.debug:
	app.run(port=config.web_port, debug=True)
else:
	http_server = gevent.wsgi.WSGIServer(('', config.web_port), app)
	http_server.serve_forever()
