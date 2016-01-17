#!/usr/bin/python
import signal
import os
import sys
import location
import gobject
from datetime import datetime
import sqlite3 as db
from subprocess import Popen
from pythonwifi import iwlibs

def log(str):
    t = datetime.now()
    print "[%s] gps: %s" % (t.strftime("%Y-%m-%d %H:%M:%S"),str)
    sys.stdout.flush()

def check_pid(pid):        
   try:
      os.kill(pid, 0)
   except OSError:
      return False
   else:
      return True

pid = str(os.getpid())
pidfile = "/tmp/gps.pid"

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

def on_error(control, error, data):
    print "location error: %d... quitting" % error
    data.quit()

def on_changed(device, data):
    global poczatek
    global first
    global p
    global first
    global count
#   Record = namedtuple("fix", ["mode","fields","time","ept","latitude","longitude","eph","altitude","epv","track","epd","speed","eps","climb","epc"])
#   data = Record(*device.fix)
    delta = datetime.now() - poczatek
    log("Szukam od %d (%d min.) Slysze %d satelit, w zasiegu mam %d" % (delta.seconds, delta.seconds/60,device.satellites_in_view,device.satellites_in_use))
    if delta.seconds > 780:
        log("No fix found in more then 600 sec")
        data.stop()
    if not device:
        return
    if device.fix:
        if (device.fix[1] & 
location.GPS_DEVICE_LATLONG_SET) and (device.fix[1] & 
location.GPS_DEVICE_TIME_SET) and not (device.status 
& location.GPS_DEVICE_STATUS_NO_FIX):
            if len(sys.argv) > 1 and count > int(sys.argv[1]):
                log("Count exceeded, exitting.")
                data.stop()
            count = count + 1
            log("Fix: %f, %f" % device.fix[4:6])
            
            wifi = iwlibs.Wireless("wlan0")
            APaddr = wifi.getAPaddr()
            Essid = wifi.getEssid()
            aq = wifi.getStatistics()[1]
            Siglevel = aq.siglevel
            Nlevel = aq.nlevel
            Quality = aq.quality
            
            
            poczatek = datetime.now()
            cur = con.cursor()    
            cur.execute("INSERT INTO POMIARY (mode,fields,time,ept,latitude,longitude,eph,altitude,epv,track,epd,speed,eps,climb,epc,sat_seen,sat_used,apaddr,essid,siglevel,nlevel,quality) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(device.fix[0],device.fix[1],device.fix[2],device.fix[3],device.fix[4],device.fix[5],device.fix[6],device.fix[7],device.fix[8],device.fix[9],device.fix[10],device.fix[11],device.fix[12],device.fix[13],device.fix[14],device.satellites_in_view,device.satellites_in_use,APaddr,Essid,Siglevel,Nlevel,Quality))
            con.commit()
            cur.execute("SELECT last_insert_rowid() AS LAST")
            pomiar_id = cur.fetchone()[0] 
            #for siec in iwlibs.Iwscan("wlan0",fullscan=True)
            #   cur.execute("INSERT INTO SIECI (ssid,bssid,siglevel,nlevel,quality,pomiar_gps) VALUES (?,?,?,?,?,?)",(siec.essid,siec.bssid,siec.quality.siglevel,siec.quality.nlevel,siec.quality.quality,pomiar_id))
            #   con.commit()
            if first or not p.poll():
                first = 0
                p = Popen(['/root/bin/gps_send.py'])

def on_stop(control, data):
    #print ""
    os.unlink(pidfile)
    data.quit()

def start_location(data):
    data.start()
    return False

signal.signal(signal.SIGINT,on_stop)
first = 1
count = 0

con = db.connect('/root/bin/gps.db')
con.row_factory = db.Row
wifi_first = iwlibs.Wireless("wlan0")
APaddr_first = wifi_first.getAPaddr()
if(APaddr_first != "00:00:00:00:00:00"):
   cur = con.cursor()
   cur.execute("select * from znane_sieci WHERE bssid = ?;",[APaddr_first])
   wynik = cur.fetchone()
   if(wynik):
      log("Znana sieci wifi")
      wifi = iwlibs.Wireless("wlan0")
      APaddr = wifi.getAPaddr()
      Essid = wifi.getEssid()
      aq = wifi.getStatistics()[1]
      Siglevel = aq.siglevel
      Nlevel = aq.nlevel
      Quality = aq.quality
      cur.execute("INSERT INTO POMIARY (mode,latitude,longitude,eph,apaddr,essid,siglevel,nlevel,quality) VALUES (3,?,?,?,?,?,?,?,?)",(wynik['lat'],wynik['long'],wynik['delta'],APaddr,Essid,Siglevel,Nlevel,Quality))
      con.commit()
      p = Popen(['/root/bin/gps_send.py'])
      print wynik
      os.unlink(pidfile)
      sys.exit()
else:
   log("Nie polaczony z wifi, wlaczam GPS.")

poczatek = datetime.now()
loop = gobject.MainLoop()
control = location.GPSDControl.get_default()
device = location.GPSDevice()
control.set_properties(preferred_method=location.METHOD_USER_SELECTED,
                       
preferred_interval=location.INTERVAL_DEFAULT)

control.connect("error-verbose", on_error, loop)
device.connect("changed", on_changed, control)
control.connect("gpsd-stopped", on_stop, loop)

gobject.idle_add(start_location, control)
   
loop.run()
