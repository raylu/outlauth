import binascii
import hashlib
import os

import sqlalchemy
from sqlalchemy import Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, backref
import sqlalchemy.ext.declarative

import config

import postgresql.clientparameters
postgresql.clientparameters.default_host = None
engine = sqlalchemy.create_engine(sqlalchemy.engine.url.URL(
	drivername='postgresql+pypostgresql',
	username=config.db_user,
	database=config.database,
	query={'unix': '/var/run/postgresql/.s.PGSQL.5432', 'port': None}
), echo=config.debug)
session = sqlalchemy.orm.scoped_session(sqlalchemy.orm.sessionmaker(
		autocommit=False, autoflush=False, bind=engine))
Base = sqlalchemy.ext.declarative.declarative_base()
Base.query = session.query_property()

class Entity(Base):
	__tablename__ = 'entities'
	id = Column(Integer, primary_key=True, autoincrement=False)
	type = Column(Enum('character', 'corporation', 'alliance', 'faction', name='entity_type'), nullable=False)
	name = Column(String(64), nullable=False)
	parent_id = Column(Integer, ForeignKey('entities.id'))

	children = relationship('Entity', backref=backref('parent', remote_side=[id]))

	def __repr__(self):
		return '<Entity(id=%r, type=%r, name=%r, parent_id=%r)>' % (self.id, self.type, self.name, self.parent_id)

class User(Base):
	__tablename__ = 'users'
	id = Column(Integer, primary_key=True)
	username = Column(String(64), nullable=False, unique=True)
	password = Column(sqlalchemy.types.CHAR(128), nullable=False)
	salt = Column(sqlalchemy.types.CHAR(32), nullable=False)
	email = Column(String(64), nullable=False, unique=True)
	apikey_id = Column(Integer, nullable=False, unique=True)
	apikey_vcode = Column(sqlalchemy.types.CHAR(64), nullable=False)
	character_id = Column(Integer, ForeignKey('entities.id'), nullable=False, unique=True)

	character = relationship('Entity')

	@staticmethod
	def hash_pw(password, salt=None):
		if salt is None:
			salt = os.urandom(16)
		hashed = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, 100000)
		hashed_hex = binascii.hexlify(hashed).decode()
		salt_hex = binascii.hexlify(salt).decode()
		return hashed_hex, salt_hex

	@staticmethod
	def login(username, password):
		user = session.query(User).filter(User.username==username).first()
		if not user:
			return False
		hashed, _ = User.hash_pw(password, binascii.unhexlify(user.salt.encode()))
		if hashed == user.password:
			return user

	def __repr__(self):
		return '<User(id=%r, username=%r, character_id=%r)>' % (self.id, self.username, self.character_id)

def init_db():
	Base.metadata.create_all(bind=engine)
def drop_db():
	Base.metadata.drop_all(bind=engine)

if __name__ == '__main__':
	import sys
	if len(sys.argv) == 2:
		if sys.argv[1] == 'init':
			init_db()
		elif sys.argv[1] == 'drop':
			drop_db()
