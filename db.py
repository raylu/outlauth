import binascii
import hashlib
import os

import sqlalchemy
from sqlalchemy import Column, ForeignKey, Integer, SmallInteger, String
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
	type = Column(SmallInteger, nullable=False)
	name = Column(String(64), nullable=False)
	parent_id = Column(Integer, ForeignKey('entities.id'))

	parent = relationship('Entity', backref=backref('children', remote_side=[id]))

	TYPE_CHAR = 1
	TYPE_CORP = 2
	TYPE_ALLIANCE = 3
	TYPE_FACTION = 4

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
