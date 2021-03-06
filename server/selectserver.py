# -*- coding: utf-8 -*
import socket, threading, sys, select, struct, time
from Queue import Queue
from os import popen
from shared import buffrify, packet
from shared.data.serverdb import get_session, create_tables
from shared.data.serverdb.defs import *
from shared.settings import HOST_IP, HOST_PORT
import logging 
from util import require_login
from datetime import datetime


 
print "gör session"
session = get_session()
print "gör tables"
create_tables()
units = session.query(Unit).all()
if "exempeldata" in sys.argv and len(units) == 0:
    
    #POIType
    sjukhus = POIType(u"sjukhus1", "static/ikoner/sjukhus.png")
    hinder = POIType(u"hinder", "static/ikoner/cancel.png")
    session.add(sjukhus)
    session.add(hinder)

    #Lägger till alla poi's
    sjuk = POI(15.6001709, 58.40633172, u"Sjukhus", sjukhus, datetime.now(), datetime.now(), 501)
    session.add(sjuk)

    #UnitTypes
    ambulans = UnitType(u"Ambulans1", "static/ikoner/ambulans.png")
    brandbil = UnitType(u"Brandbild1", "static/ikoner/brandbil.png")
    jonas = UnitType(u"jonas","static/ikoner/JonasInGlases.png")
    session.add(ambulans)
    session.add(brandbil)
    session.add(jonas)

    #skapar units
    session.add(Unit(u"Ambulans ett", ambulans, 15.5829, 58.4093, datetime.now(), False))
    session.add(Unit(u"Ambulans två", ambulans, 15.57806, 58.40579, datetime.now(), False))
    session.add(Unit(u"Brandbil", brandbil, 15.5729, 58.40193, datetime.now(), False))
    session.add(Unit(u"Fotgängare", jonas, 15.5720, 58.4026, datetime.now(), False))
    #skapar en POI-type
    #self, coordx, coordy, id, name, sub_type, timestamp"

    #skapar användare
    session.add(User(u"jonas",u"mittlosen"))
    session.add(User(u"jon", u"supersecurepassword"))
    session.add(User(u"a",u"a"))
    session.commit()

else:
    # kolla att man har nått i databasen
    num_types = len(units)
    if not num_types:
        logging.warn(u"du har inget i databasen. kör"+\
                u"'./start main exempeldata' för o dra in lite exempeldata.")
    elif "exempeldata" in sys.argv:
        logging.warn(u"du försökte exempeldata, men hade redan saker i"+\
                u"databasen. ta bort den först för att tömma.")

class Connection(object):
    
    pingtime = 15
 
    def __init__(self, socket, addr):
        self.addr, self.port = addr
        self.socket = socket
        self.id = socket.fileno()
        self.out_queue = Queue()
        self.out_buffer = ""
        self.in_queue = Queue()
        self.in_buffer = ""
        self.timestamp = time.time()
        self.timepinged = 0
        self.user = None
        self.unitname = None

client_sockets = {}
connections = {}
clientrequests = {}

def get_unique_id():
    # todo: se till att den här verkligen e unik :p
    import random
    return int(str(random.randint(0,100000)) + "1")

@require_login
def get_map_updates(connection, pack):
    p = packet.Packet.from_str(pack)
    print "lollar: %s" % p.data
clientrequests["get_map_updates"] = get_map_updates
 
def pong(connection, pack):
    connection.timestamp = time.time()
    connection.timepinged = 0
clientrequests["pong"] = pong

@require_login
def request_updates(connection, pack):
    # hitta alla pois ja har, dra bort alla som har samma eller senare
    # changed.
    print "client_pois: %s" % pack.data["status"]["POI"].keys()
    client_pois = pack.data["status"]["POI"]
    status = pack.data["status"]
    to_send = []
    for poi in session.query(POI).all():
        should_send = False
        print "servern har %s, ändrad %s" % (poi.unique_id, poi.changed)
        if str(poi.unique_id) in client_pois.keys():
            client_poi_changed = datetime.fromtimestamp(float(client_pois[str(poi.unique_id)]))
            print u"client har den också!! me datan %s" % client_poi_changed
            if client_poi_changed >= poi.changed:
                print "klienten e nyare/samma."
                # TODO: be klienten om uppdaterade
            else:
                to_send.append(poi)
                should_send = True
                print "servern e nyare."
        else:
            should_send = True
        if should_send:
            p = packet.Packet("poi_response", poi_type=poi.type.name,
                    name=poi.name, changed=float(poi.changed.strftime("%s")),
                    coordy=poi.coordy, coordx=poi.coordx, unique_id=poi.unique_id)
            connection.out_queue.put(p)
            #datan ser ut som FÖLJER: { u'poi_type': u'sjukhus1', u'name': u'mm', 'created': 1260273998.0, 'changed': 1260273998.0, u'coordy': u'58.4070476', u'id': u'', 'unique_id': 257491, u'coordx': u'15.5693523'}

                
clientrequests["request_updates"] = request_updates

@require_login
def contact_send(connection, pack):
    print "du e fan king på contact_send i servern"
    responsepacket = packet.Packet("contact_resp")
    responsepacket.data["users"] = []
    for conn in connections.values():
        user = conn.user
        ip = conn.addr
        if user is not None:
            responsepacket.data["users"].append((user, ip))
    connection.out_queue.put(responsepacket)
clientrequests["contact_req"] = contact_send

def mission(connection, pack):
    mission_data = pack.data
        #mission_save = str(packet.Packet("mission_save", name=name,\
        #                        desc=info, poi=poi.unique_id ))
    mission_data["created"] = float(datetime.now().strftime("%s"))
    mission_data["changed"] = float(datetime.now().strftime("%s"))
    mission_data["unique_id"] = get_unique_id()
    mission_data["status"] = "active"
    print "fick ett mission, infos: %s" % mission_data
    s = get_session()
    try: 
        poi = s.query(POI).filter(POI.unique_id==mission_data["poi"]).one()
    except:
        logging.error("servern hade inte den POI:en.")
        return
    print "Poi: %s" % poi
    miss = Mission(mission_data["name"], mission_data["created"], mission_data["changed"])
    miss.status = mission_data["status"]
    miss.desc = mission_data["desc"]
    miss.unique_id = mission_data["unique_id"]
    miss.poi = poi
    s.add(miss)
    s.commit()

    mission_response = packet.Packet("mission_response")
    mission_response.data = mission_data
    for connection in connections.values():
        connection.out_queue.put(mission_response)
    #connection.out_queue.put(mission_response)
clientrequests["mission_save"] = mission

def login(connection, pack):
    global to_be_removed
    print "Du är inne i login acceptor"
    session.query(User).all()
    loginfo = pack.data
    username = loginfo["username"]
    password = loginfo["password"]
    unitname = loginfo["unitname"]
    connection.unitname = unitname
    login_response = packet.Packet("login_response", login="False")
    for users in session.query(User).filter(User.name == username):
        if password == users.password:
            login_response = packet.Packet("login_response", login="True")
            # kolla om usern redan var inloggad
            # ta isf bort den "gamla"
            print "loggade in som %s" % username
            for old_id, old_conn in connections.iteritems():
                if old_conn.user == username and \
                        old_conn.id != connection.id:
                    to_be_removed.append(old_id)
                    print "redan inloggad på annan connection tar bort."
            connection.user = username
        else:
            login_response = packet.Packet("login_response", login="False")
    connection.out_queue.put(login_response)
clientrequests["login"] = login
 
#DETTA ÄR HELT JÄVLA KASST! GRUPP 2 SUGER DASE
#def alarm(connection, pack):
#    connection.timestamp = time.time()
#    connection.timepinged = 0
#    id = pack.data["id"]
#    name = pack.data["name"]
#    timestamp = pack.data["timestamp"]
#    sub_type = pack.data["sub_type"]
#    poi_id = pack.data["poi_id"]
#    contact_person = pack.data["contact_person"]
#    contact_number = pack.data["contact_number"]
#    other = pack.data["other"]
#    if id == "":
#        pack.data["id"]=get_id()
#    alarm_response = packet.Packet("alarm_response")
#    alarm_response.data = pack.data
#    for connection in connections.values():
#        connection.out_queue.put(alarm_response)
#clientrequests["alarm"] = alarm

def unit_update(connection, pack):
    unit_response = packet.Packet("unit_response")
    unit_response.data = pack.data
    for conn in connections.values():
        if conn != connection:
            print "Du försökte ändra nån annans coordinat"
            conn.out_queue.put(unit_response)
clientrequests["unit_update"] = unit_update

@require_login
def poi(connection, pack):
    #lägg i databas
    id = pack.data["id"]
    name = pack.data["name"]
    timestamp = pack.timestamp

    poi_type_name = pack.data["poi_type"]
    coordx = pack.data["coordx"]
    coordy = pack.data["coordy"]
    if coordx == "" or coordy == "":
        logging.warn("fick en add poi med tomma lat och lon :S")
        return
    pack.data["unique_id"] = get_unique_id()
    pack.data["changed"] = float(pack.timestamp.strftime("%s"))
    pack.data["created"] = float(pack.timestamp.strftime("%s"))
    session.query(POI).all()
    loginfo = pack.data
    hej = u"Hej"
    print hej
    print poi_type_name
    print "Innan foren"
    poi_type = session.query(POIType).filter(POIType.name==u"sjukhus1")[0]
    for poi_types in session.query(POIType).filter(POIType.name==poi_type_name):
        print "Kom in i foren"
        poi_type = poi_types
    session.add(POI(coordx, coordy, name, poi_type, timestamp, timestamp, unique_id=pack.data["unique_id"]))
    session.commit()
    poi_response = packet.Packet("poi_response")
    poi_response.data = pack.data
    print "datan ser ut som FÖLJER: %s" % poi_response.data
    for connection in connections.values():
        connection.out_queue.put(poi_response)
clientrequests["poi"] = poi

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, struct.pack("i",1))
print "Binder servern till %s" % HOST_IP[0]
s.bind((HOST_IP[0], HOST_PORT))
s.setblocking(0)
s.settimeout(0)
s.listen(5)

to_be_removed = []
 
print "Server igång på %s:%s" % (HOST_IP[0], HOST_PORT)
while True:
    try:
        time.sleep(0.1)
        acceptor = select.select([s,], [s,], [s,], 0)[0]
        if acceptor:
            newsocket, addr = s.accept()
            client_sockets[newsocket.fileno()] = newsocket
            connections[newsocket.fileno()] = Connection(newsocket, addr)
 
            print "new connected %s: %s, %s" % (newsocket.fileno(), newsocket, addr)
            print client_sockets
 
        read_list, write_list, error_list = select.select(
            client_sockets.values(),
            client_sockets.values(),
            client_sockets.values(), 0)

        to_be_removed = []
 
        for sock in read_list:
            # TODO: fixa in_buffern :p
            # och in_queue
            connection = connections[sock.fileno()]
            #print "läsa från %s" % sock.fileno()
            read = sock.recv(1024)
            if read != "":
                connection.in_buffer += read
                can_split = buffrify.split_buffer(connection.in_buffer)
                if can_split is not None:
                    connection.in_buffer = can_split[1]
                    read = can_split[0]
                    pack = packet.Packet.from_str(read)
                    print "laggar till %s=>%s" % (pack.type, str(pack.data))
                    if pack.type in clientrequests:
                        clientrequests[pack.type](connection, pack)
            else:
                to_be_removed.append(sock.fileno())
 
 
        for sock in write_list:
            connection = connections[sock.fileno()]
 
            if connection.out_buffer == "" and \
                not connection.out_queue.empty():
                #print "skriver till %s (%s)" % (connection.id, connection.user)
                abba = connection.out_queue.get()
                connection.out_buffer = buffrify.create_pack(str(abba))
 
            if connection.out_buffer != "":
                sent = sock.send(connection.out_buffer)
                if sent != len(connection.out_buffer):
                    connection.out_buffer = connections[sock.fileno()].out_buffer[sent:]
                else:
                    connections[sock.fileno()].out_buffer = ""
 
        for sock in error_list:
            print "fel på %s" % sock.fileno()
 
        # logics
        for fileno, connection in connections.iteritems():
            if time.time()-connection.timestamp > connection.pingtime:
                connection.timestamp = time.time()
                if connection.timepinged == 3:
                    print "You tried to connect to klient:" , connection.socket.fileno() , \
                            "three times you will now remove that client"
                    connection.timepinged == 0
                    to_be_removed.append(connection.socket.fileno())
                else:
                    connection.timepinged = connection.timepinged + 1
                    ping = packet.Packet("ping")
                    connection.out_queue.put(ping)
 
        for id in to_be_removed:
            connections[id].socket.close()
            client_sockets[id].close()
            del connections[id]
            del client_sockets[id]
 
    except KeyboardInterrupt:
        s.shutdown(socket.SHUT_RDWR)
        s.close()
        for sock in client_sockets.values():
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
    except socket.error:
        s.shutdown(socket.SHUT_RDWR)
        s.close()
        for sock in client_sockets.values():
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
