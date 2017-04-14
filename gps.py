#!/usr/bin/python
import signal
import os
import sys
import location
import gobject
from datetime import datetime
import sqlite3 as db
from subprocess import Popen
from subprocess import call
from pythonwifi import iwlibs
import time

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

def on_error(control, error, data):
    print "location error: %d... quitting" % error
    data.quit()

def check_fix(device):
  if not device:
    log("There is no GPS device.")
    return False
  if not device.fix:
    log("Device has not fix.")
    return False
  if device.satellites_in_use == 0:
    log("0 sattelites in use.")
    return False
  if not device.fix[1] & location.GPS_DEVICE_LATLONG_SET:
    log("Device does not have latlong set.")
    return False
  if not device.fix[1] & location.GPS_DEVICE_TIME_SET:
    log("Device does not have time set.")
    return False
  if device.status & location.GPS_DEVICE_STATUS_NO_FIX:
    log("Device has status no_fix.")
    return False
  return True

def on_changed(device, data):
    global has_fix
    global poczatek
    global first
    global p
    global first
    global count
    pomiar_id = False
    delta = datetime.now() - poczatek
    if delta.seconds > 780:
      log("No fix found in more then 600 sec")
      data.stop()

    if check_fix(device):
      if len(sys.argv) > 1 and count > int(sys.argv[1]):
          log("Count exceeded, exitting.")
          data.stop()
      count = count + 1
      if not has_fix:
          log("Fix acquired.")
          has_fix = True

      poczatek = datetime.now()
      cur = con.cursor()
      cur.execute("""INSERT INTO measurement_gps
        (mode,
         fields,
         gps_timestamp,
         ept,latitude,
         longitude,
         eph,
         altitude,
         epv,
         track,
         epd,
         speed,
         eps,
         climb,
         epc,
         sat_seen,
         sat_used
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (device.fix[0],
         device.fix[1],
         device.fix[2],
         device.fix[3],
         device.fix[4],
         device.fix[5],
         device.fix[6],
         device.fix[7],
         device.fix[8],
         device.fix[9],
         device.fix[10],
         device.fix[11],
         device.fix[12],
         device.fix[13],
         device.fix[14],
         device.satellites_in_view,
         device.satellites_in_use
        )
      )
      con.commit()
      cur.execute("SELECT last_insert_rowid() AS LAST")
      pomiar_id = cur.fetchone()[0]
      #if first or not p.poll():
      #    first = 0
          #p = Popen(['/root/bin/gps_send.py'])
    else:
       if has_fix:
          log('Fix lost')
          has_fix = False
    if geolocate_wifi(pomiar_id):
      data.stop()

def on_stop(control, data):
    log("Stopping GPS...")
    data.quit()

def start_location(data):
    data.start()
    return False

def geolocate_wifi(pomiar_id=False):
    best_bssid = "00:00:00:00:00:00"
    best_quality = 0
    call(['/sbin/ifconfig', 'wlan0', 'up'])
    i = 0
    for siec in iwlibs.Iwscan("wlan0",fullscan = True):
      if pomiar_id:
        cur = con.cursor()
        i = i + 1
        cur.execute("""
            SELECT ID
            FROM known_wifi
            WHERE bssid = ?;
        """,(siec.bssid))
        wifi_id = cur.fetchone()[0]
        if not wifi_id:
            cur.execute("""
                INSERT INTO known_wifi (
                    ssid,bssid
                ) VALUES (?,?)
            """,(siec.ssid,siec.bssid)
            )
            con.commit()
            cur.execute("SELECT last_insert_rowid() AS LAST")
            wifi_id = cur.fetchone()[0]
        cur.execute("""
            INSERT INTO measurement_wifi (
                 siglevel,
                 nlevel,
                 quality,
                 id_known_wifi,
                 id_measurement_gps
                ) VALUES (?,?,?,?,?)""",
                (
                 siec.quality.siglevel,
                 siec.quality.nlevel,
                 siec.quality.quality,
                 wifi_id,
                 pomiar_id
                )
        )
        con.commit()

      if best_quality < siec.quality.quality:
        cur = con.cursor()
        cur.execute(
            """
            SELECT *
            FROM known_wifi
            WHERE bssid = ?
            AND real_coord = 1;
            """,
            [siec.bssid]
        )
        wynik = cur.fetchone()
        if(wynik):
          best_bssid = siec.bssid
          best_quality = siec.quality.quality
          best_wifi_coord = (wynik['latitude'],wynik['longitude'],wynik['epd'])
          best_siec = siec

    if i > 0:
        log("WiFi found: %s " % i)
    if best_bssid != "00:00:00:00:00:00":
        log("Known WiFi found: %s..." % best_siec.essid)
        cur.execute("""
            INSERT INTO measurement_gps (
                mode,
                latitude,
                longitude,
                eph
                )
             VALUES ('wifi',?,?,?)""",
             (best_wifi_coord[0],
              best_wifi_coord[1],
              best_wifi_coord[2]
             )
        )
        con.commit()
        #p = Popen(['/root/bin/gps_send.py'])
        return True
    return False

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



con = db.connect('/home/user/MyDocs/gps.db')
con.row_factory = db.Row

i = 1
not_found_counter = 0

while True:
  if not geolocate_wifi():
    not_found_counter = not_found_counter + 1
    if not_found_counter < 10:
       log("No known wifi found, trying again in 3 sec (%s/10) before firing gps recivier" % (not_found_counter))
       time.sleep(3)
       continue
    i = 1
    log('Starting gps...')

    signal.signal(signal.SIGINT,on_stop)
    first = 1
    count = 0
    has_fix = False
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
  else:
    not_found_counter = 0
  if i < 300:
    i = i + 1
  log("Sleeping... %s sec" % i)
  time.sleep(i)
