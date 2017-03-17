#!/usr/bin/env python
import signal
import os
import sys
import sqlite3 as db
import httplib, urllib
from time import time,sleep
from datetime import datetime
#import socket

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
       sys.exit()
    else:
       log("%s stale lock file, removing" % pidfile)
       os.unlink(pidfile)
       file(pidfile, 'w').write(pid)
else:
    file(pidfile, 'w').write(pid)

con = db.connect('/home/user/MyDocs/gps.db')

con.row_factory = db.Row
con.text_factory = str

cur = con.cursor() 
cur.execute("select count(*) as count from POMIARY WHERE SENT = 0 AND MODE = 3")
count = cur.fetchone()
cnt = int(count['count'])
new_count = cnt
time_mark = time()
if count['count'] == 0:
   log("Nothing to send, quiting. %d")
   sys.exit()
log("Starting, queue: %d" % (count['count']))

cur.execute("select * from POMIARY WHERE SENT = 0 AND MODE = 3 LIMIT 1000")
send_counter = 0
net_counter = 0
rows = cur.fetchall()
headers = {"Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain"}
try:
    conn = httplib.HTTPConnection("q84fh.mydevil.net")
    
    for row in rows:
        cur.execute("select * from sieci where pomiar_gps = ?",[row['id']])
        sieci = cur.fetchall()
        scn = []
        for siec in sieci:
          scn.append("%s;%s;%s;%s;%s" % (siec['ssid'],siec['bssid'],siec['siglevel'],siec['nlevel'],siec['quality']))
          net_counter = net_counter + 1
        try:
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
             'timestamp': row['time_aquired'],
             'scn[]': scn
         },True)
        except UnicodeEncodeError:
          log("Warning: UnicodeEncodeError.")
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
             'timestamp': row['time_aquired'],
         },True)
        conn.set_debuglevel(10)
        conn.request("POST", "/gps.php", params, headers)
        sleep(3)
        try:
           response = conn.getresponse()
        except:
           log('httplib exception risen')
           conn = httplib.HTTPConnection("q84fh.mydevil.net")
           continue
           pass
        
        if response.status == 200:
            cur.execute("UPDATE POMIARY SET sent_timestamp = CURRENT_TIMESTAMP, sent = 1 WHERE id = ?;", [row['id']] )
            con.commit()
            send_counter = send_counter + 1
        if send_counter % 10 == 0:
            cur.execute("select count(*) as count from POMIARY WHERE SENT = 0 AND MODE = 3")
            cur_count = cur.fetchone()['count']
            
            log("Sent %d/%d (%d nets). %d left, d: %d" % (send_counter,cnt,net_counter,cnt-send_counter,cur_count-new_count))
            speed = (cur_count-new_count)/(time()-time_mark)
            eta = ((send_counter - cnt)/speed)/60 
            log("Speed: %f, eta: %d min." % (speed,eta))
            net_counter = 0
            time_mark = time()
            new_count = cur_count
except:
    log("Error: Sending job failed: exception risen")
    conn.close()   
    os.unlink(pidfile)
    print(row)
    print(scn)
    raise
    #pass
    sys.exit()

deleter = con.cursor()

deleter.execute("delete from sieci where pomiar_gps in (select id from POMIARY where sent = 1")
con.commit()
del_sieci = deleter.rowcount

deleter.execute("DELETE from POMIARY WHERE SENT = 1 AND time_aquired < date('now', '-1 days');")
con.commit()
del_pomiary = deleter.rowcount

log("Completed: sent %s entries, deleted %d/%d" % (send_counter,del_pomiary,del_sieci))

con.close()
conn.close()
os.unlink(pidfile)