import pymongo
from time import asctime, localtime, time

client = pymongo.MongoClient()
db = client.tesla
stream = db.tesla_stream

known_locs = { }
try:
    f = open('locations.txt','r')
    for line in f:
        line.strip()
        loc_name, loc_lat, loc_long = line.split(',')
        known_locs[loc_name] = { 'lat': float(loc_lat), 'long': float(loc_long) }
    f.close()
except IOError:
    pass

print known_locs

at_home = False
stuck = False
warning_count = 0
limit = None
last_date = None
last_car_state = None
last_shift_time = None
location_error = 0.002
commute = [ ]
commute_stuck_ms = 0
commutes = [ ]
unknown_locs = { }
show_all_warnings = True

def kinda_close(a, b):
    return ((a['lat'] > (b['lat'] - location_error))
            and (a['lat'] < (b['lat'] + location_error))
            and (a['long'] > (b['long'] - location_error))
            and (a['long'] < (b['long'] + location_error)))

i=0
for stream_data in stream.find():
    record = stream_data['record']
    time_string = asctime(localtime(float(record[0])/1000))
    
    new_date = time_string[:10]
    if new_date != last_date:
        last_date = new_date
        print new_date

    try:
        timestamp,speed,odometer,soc,elevation,est_heading,est_lat,est_lng,power,shift_state,range,est_range,heading = record
    except:
        if show_all_warnings or warning_count == 0:
            print "record not in expected format on " + time_string
            print record
        warning_count = warning_count + 1
        continue

    cur_loc = { 'lat': float(est_lat), 'long': float(est_lng) }

    if shift_state in [ 'D', 'R', 'N' ]:
        car_state = 'driving'
    elif shift_state in [ '', 'P']:
        car_state = 'parked'
    else:
        print "unexpected state " + shift_state + " at " + time_string

    if car_state != last_car_state:
        loc_found = False
        for check_loc in known_locs:
            if kinda_close(cur_loc, known_locs[check_loc]):
                cur_loc_str = check_loc
                loc_found = True
                break
        if not loc_found:
            cur_loc_str = str(cur_loc)
	    unknown_name = 'unknown ' + str(len(unknown_locs))
            unknown_locs[unknown_name] = cur_loc
	    known_locs[unknown_name] = cur_loc
        if last_shift_time:
            state_delta = (int(timestamp) - last_shift_time) / 60000
            print time_string + ": " + car_state + " after " + str(state_delta) + " minutes; at " + cur_loc_str
        if len(commute) > 0 and car_state == 'parked':
            commute.append(cur_loc_str)
        if cur_loc_str in [ 'work', 'home' ]:
            if len(commute) > 0 and commute[0] != cur_loc_str:
                # we got to the other side, record the commute
                commute_delta = (int(timestamp) - commute_start) / 60000
                #print ("********** commute from " + commute[0] +
                #       " to " + cur_loc_str + ": " + str(commute_delta) +
                #       " minutes via: " + str(commute[2:]))
                commutes.append({ 'route': commute, 'time': commute_delta, 'end_date': time_string, 'stuck_time': commute_stuck_ms/60000})
            # start a new commute
            commute = [ check_loc ]
            commute_start = int(timestamp)
            commute_stuck_ms = 0
        last_car_state = car_state
        last_shift_time = int(timestamp)

    if car_state == 'driving' and int(speed) < 15 and not stuck:
        #print time_string + ": hit light or traffic"
        stuck = True
        stuck_start = int(timestamp)
    elif stuck:
        #print time_string + ": unstuck"
        stuck = False
        commute_stuck_ms = commute_stuck_ms + int(timestamp) - stuck_start

    i = i + 1
    if limit and i > limit:
        break

if unknown_locs:
    print "had some unknown locations:"
    print unknown_locs
    f = open('locations.txt','a')
    for loc in unknown_locs:
        f.write("%s,%f,%f\n" % ( loc,unknown_locs[loc]['lat'], unknown_locs[loc]['long']) )
    f.close()

print "logged " + str(len(commutes)) + " commutes"

def print_rec(rec):
    print (rec['end_date'] + ": " + str(rec['time']) + " minutes, route: " + str(rec['route']) + ", stuck for " + str(rec['stuck_time']) + " minutes")

print "commutes home form work:"
for rec in commutes:
    if rec['route'][0] == 'work':
        print_rec(rec)

print "commutes to work:"
for rec in commutes:
    if rec['route'][0] == 'home':
        print_rec(rec)

print str(warning_count) + " warnings out of " + str(stream.count()) + " records (" + str(limit) + " limit)"
