import os

import pandokia.db_sqlite as dbx

minipyt_test_order = 'alpha'

try :
    os.unlink('sqlite.db')
except OSError :
    pass

dbx = dbx.PandokiaDB('sqlite.db')

dbx.execute('drop table if exists test_table')

import shared
shared.dbx = dbx

from shared import *

import csv_t
csv_t.dbx = dbx

from csv_t import *

import pandokia.helpers.minipyt as minipyt

@minipyt.test
def t020_sequence() :
    dbx.execute("create table foo ( n integer primary key, s varchar );")
    c = dbx.execute("insert into foo ( s ) values ( 'x' )")
    assert c.lastrowid == 1
    c = dbx.execute("insert into foo ( s ) values ( 'x' )")
    assert c.lastrowid == 2
    c = dbx.execute("insert into foo ( s ) values ( 'x' )")
    assert c.lastrowid == 3

@minipyt.test
def t020_implicit_sequence() :
    assert dbx.next is None
