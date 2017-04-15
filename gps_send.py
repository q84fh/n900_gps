#!/usr/bin/env python3
import signal
import os
import sys

from time import time,sleep
from datetime import datetime

import json
import requests
import sqlite3 as db

url = 'http://q84fh.mydevil.net/gps_rx.php'

def log(str):
    t = datetime.now()
    print("[{}] gps_send: {}".format(t.strftime("%Y-%m-%d %H:%M:%S"),str))
    sys.stdout.flush()

def check_pid(pid):
   try:
      os.kill(pid, 0)
   except OSError:
      return False
   else:
      return True

pid = str(os.getpid())
pidfile = "/tmp/gps_send.pid"

if os.path.isfile(pidfile):
    with open(pidfile) as f:
        if(check_pid(int(f.read()))):
            sys.exit()
    log("{} stale lock file, removing".format(pidfile))
    os.unlink(pidfile)
    with open(pidfile, 'w') as f:
        f.write(pid)
else:
    with open(pidfile, 'w') as f:
        f.write(pid)

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def push_data(table_name):
    con = db.connect('/home/user/MyDocs/gps.db')

    con.row_factory = dict_factory
    con.text_factory = str

    cur = con.cursor()

    cur.execute("select * from {} WHERE SENT != 1 LIMIT 10".format(table_name))
    rows = cur.fetchall()

    r = requests.post(url, data = { table_name: json.dumps(rows) } )
    print(r.text)
    con.close()

push_data('known_wifi');
push_data('measurement_gps');
push_data('measurement_wifi');

os.unlink(pidfile)
