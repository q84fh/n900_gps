#!/usr/bin/env python
import signal
import os
import sys
import sqlite3 as db
import httplib, urllib
from datetime import datetime

def log(str):
    t = datetime.now()
    print "[%s] gps_send: %s" % (t.strftime("%Y-%m-%d %H:%M:%S"),str)
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
    if(check_pid(int(file(pidfile, 'r').read()))):
       log("Lock file %s already exists, exiting" % pidfile)
       sys.exit()
    else:
       log("%s stale lock file, removing" % pidfile)
       os.unlink(pidfile)
       file(pidfile, 'w').write(pid)
else:
    file(pidfile, 'w').write(pid)

con = db.connect('/root/bin/gps.db')

con.row_factory = db.Row

cur = con.cursor() 

cur.execute("select count(*) as count from POMIARY WHERE SENT = 0 AND MODE = 3")
count = cur.fetchone()

log("Starting gps_send: Entries in queue: %d" % (count['count']))

cur.execute("select * from POMIARY WHERE SENT = 0 AND MODE = 3 LIMIT 1000")
send_counter = 0
rows = cur.fetchall()
headers = {"Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain"}
try: 
    conn = httplib.HTTPConnection("q84fh.mydevil.net")
    for row in rows:
        params = urllib.urlencode({
            'lat': row['latitude'],
            'long': row['longitude'],
            'eph': row['eph'], 
            'alt': row['altitude'],
            'epv': row['epv'],
            'track': row['track'],
            'ept': row['ept'],
            'speed': row['speed'],
            'eps': row['eps'],
            'climb': row['climb'],
            'epc': row['epc'],
            'ssid': row['essid'],
            'bssid': row['apaddr'],
            'signal': row['siglevel'],
            'noise': row['nlevel'],
            'quality': row['quality'],
            'timestamp': row['time_aquired']
        })
        conn.request("POST", "/gps.php", params, headers)
        response = conn.getresponse()
        response.read()
        if response.status == 200:
            cur.execute("UPDATE POMIARY SET sent_timestamp = CURRENT_TIMESTAMP, sent = 1 WHERE id = ?;", [row['id']] )
            con.commit()
            send_counter = send_counter + 1
except:
    log("Error: Sending job completed: Brak polaczenia")
    conn.close()   
    os.unlink(pidfile)
    raise 
    sys.exit()
deleter = con.cursor()
deleter.execute("DELETE from POMIARY WHERE SENT = 1 AND time_aquired < date('now', '-1 days');")
con.commit()
log("Sending job completed: sent %s entries, deleted %d old rows in database" % (send_counter,deleter.rowcount))
con.close()
conn.close()
os.unlink(pidfile)
