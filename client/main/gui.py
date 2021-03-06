# -*- coding: utf-8 -*
import gtk
import hildon
import gui_map
import time
import sys
import pango
from shared.data import get_session, create_tables
from shared.data.defs import *
from shared import rpc, packet
from datetime import datetime
import data_storage
#from video import GTK_Main
#from video2 import GTK_Maine
from datetime import datetime
import gobject


def create_menuButton(bild,label):
    buttonBox = gtk.HBox(False, spacing=1)
    button = gtk.Button()
    label = gtk.Label(label)
    buff = gtk.gdk.PixbufAnimation(bild)
    image = gtk.Image()
    image.set_from_animation(buff)
    image.show()
    label.show()
    buttonBox.pack_start(image, expand=False, fill=False, padding=5)
    buttonBox.pack_start(label, expand=False, fill=False, padding=5)
    button.add(buttonBox)
    button.show_all()
    button.set_size_request(296, 60)
    return button

class Page(gtk.VBox):
    def __init__(self, name, gui, width="half", spacing=1, homogeneous=False):
        super(gtk.VBox, self).__init__(homogeneous=homogeneous, spacing=spacing)
        if width == "half":
            self.size_request = (300,300)
        elif width == "full":
            self.size_request = (600,300)
        self.page_name = name
        self.show()
        self.gui = gui

    def map_dblclick(self, coordx, coordy):
        pass
        #print "got dblclick i Page! coords: %s, %s" % (coordx,coordy)
    def on_show(self):
        pass
        #print "visar sida %s" % self.page_name

class MenuPage(Page):
    def hille_e_tjock(self, widget, data=None):
        print "tjockade pÃ¥ hille"
        session = get_session()
        poiPacket = str(packet.Packet("poi",id = "", poi_type = u"brand", name = "Vallarondellen", coordx = "15.5680", coordy = "58.4100"))
        #rpc.send("qos", "add_packet", packet=poiPacket)
        gobject.timeout_add(0, rpc.send, "qos", "add_packet", {"packet":poiPacket})
        #alarm = str(packet.Packet("alarm", id = "", type = "skogsbrand", name = "Vallarondellen", timestamp = time.time(), poi_id = "", contact_person = "", contact_number = "", other = ""))
        #print rpc.send("qos", "add_packet", packet=alarm)

    #Kanske behÃ¶vs flyttas till ett mer logiskt stÃ¤lle!
    def add_poi(self, pack):
        print "hihi add_poi"
        pack = packet.Packet.from_str(str(pack))
        session = get_session()
        loginfo = pack.data
        try:
            poi = session.query(POI).filter(POI.unique_id == pack.data["unique_id"]).one()
        except:
            poi = POI()
            poi.created = pack.timestamp
            poi.unique_id = pack.data["unique_id"]
        poi.name = pack.data["name"]
        poi.changed = datetime.fromtimestamp(pack.data["changed"])
        poi.coordx = pack.data["coordx"]
        poi.coordy = pack.data["coordy"]
        poi.type = session.query(POIType).filter(POIType.name==pack.data["poi_type"]).one()
        session.add(poi)
        session.commit()
        self.gui._map.add_object(poi.id, "poi", poi.name, 
                data_storage.MapObject({
                    "longitude":poi.coordx,"latitude":poi.coordy},
                    poi.type.image))
        #for poi in session.query(POI).filter(POI.name == name):
        #    self.gui._map.add_object(poi.id, "poi", poi.name, 
        #            data_storage.MapObject({
        #                "longitude":poi.coordx,"latitude":poi.coordy},
        #                poi.type.image))
        self.gui._map.redraw()

    def __init__(self, gui):
        super(MenuPage, self).__init__("menu", gui)
        self.size_request = (300,300)
        # CREATE BUTTONS
        objButton = create_menuButton("static/ikoner/map.png","Objekt")
        setButton = create_menuButton("static/ikoner/cog.png","InstÃ¤llningar")
        conButton = create_menuButton("static/ikoner/book_addresses.png","Kontakter")
        misButton = create_menuButton("static/ikoner/book.png","Uppdrag")
        jonasButton = create_menuButton("static/ikoner/JonasInGlases.png","Jonas")
        objButton.connect("clicked", self.gui.switch_page, "object")
        misButton.connect("clicked", self.gui.switch_page, "mission")
        setButton.connect("clicked", self.gui.switch_page, "settings")
        conButton.connect("clicked", self.gui.switch_page, "contact")
        jonasButton.connect("clicked", self.hille_e_tjock)

        vMenuBox = gtk.VBox(False,0)
        vMenuBox.pack_start(objButton, False, True, padding=2)
        vMenuBox.pack_start(misButton, False, True, padding=2)
        vMenuBox.pack_start(conButton, False, True, padding=2)
        vMenuBox.pack_start(setButton, False, True, padding=2)
        vMenuBox.pack_start(jonasButton, False, True, padding=2)
        self.pack_start(vMenuBox, False, False, padding=0)

        self.show()
        vMenuBox.show()
        rpc.register("add_poi", self.add_poi)

class SettingsPage(Page):

    def __init__(self, gui):
        super(SettingsPage, self).__init__("settings", gui, width="full")
        self.size_request = (300,300)
        button = create_menuButton("static/ikoner/arrow_left.png", "Tillbaka")
        button.connect("clicked", self.gui.switch_page, "menu")
        self.pack_start(button, False, False, padding=2)

        self.show_all()

class ContactPage(Page):

    def add_contactlist(self, pack):
        pack = packet.Packet.from_str(pack)
        self.contacts = {}
        for user in pack.data["users"]:
            self.contacts[user[0]] = user[1]
        self.combo.get_model().clear()
        for user in self.contacts:
            self.combo.append_text(user)
            
    def on_show(self): 
        contact_send = str(packet.Packet("contact_req"))
        #rpc.send("qos", "add_packet", packet=contact_send)
        gobject.timeout_add(0, rpc.send, "qos", "add_packet", {"packet":contact_send})
        
    def __init__(self, gui):
        #super(ContactPage, self).__init__("contact", gui, width="full")
        super(ContactPage, self).__init__("contact", gui, width="full")
        self.contacts = {}
        self.size_request = (300,300)
        self.vbox1 = gtk.VBox()
        self.combo = gtk.combo_box_new_text()

        #self.combo innehåller alla kontakter som finns i self.contacts {(user,ip)} 
        
        backButton = create_menuButton("static/ikoner/arrow_left.png", "Tillbaka")
        newButton = create_menuButton("static/ikoner/phone.png", "Ring")
        videoButton = create_menuButton("static/ikoner/JonasInGlases.png", "Video")
        backButton.connect("clicked", self.gui.switch_page, "menu")
        videoButton.connect("clicked", self.videoCall)
        newButton.connect("clicked", self.voiceCall)
        label = gtk.Label("Välj Kontakt:")


        self.vbox1.pack_start(label, False, True, padding=2)
        self.vbox1.pack_start(self.combo,False,False,10)

        self.vbox1.pack_start(newButton, False, True, padding=2)
        self.vbox1.pack_start(videoButton, False, True, padding=2)
        self.vbox1.pack_start(backButton, False, True, padding=2)
        self.pack_start(self.vbox1,False,True,0)


        self.show_all()
        rpc.register("add_contactlist", self.add_contactlist)

    #def videoCall(self, widget, data=None):
    def videoCall(self, w):
        self.gui.rightBook.set_size_request(600,300)
        userip = self.combo.get_active_text()
        ip = self.contacts[userip]
        self.vbox1.hide()
        #print "user ip: ", ip
        #GTK_Main().video(ip)
        
    #def voiceCall(self, widget, data=None):
    def voiceCall(self, w):
        self.gui.rightBook.set_size_request(600,300)
        userip = self.combo.get_active_text()
        ip = self.contacts[userip]
        self.vbox1.hide()
        print "user ip: ", ip
        #GTK_Maine().video(ip)
        #video.Stream("Video", ip, "7331")
        #rpc.send("A-w-e-s-o-m-e O", ipaddr = ip)
        
class MissionPage(Page):
  
    def __init__(self, gui):
        self.size_request = (300,300)

        super(MissionPage, self).__init__("mission", gui, homogeneous=False,spacing=0)
        showMissionButton = create_menuButton("static/ikoner/book.png","Uppdragsinfo")
        newMissionButton = create_menuButton("static/ikoner/book_add.png","Lagg till")
        deleteMissionButton = create_menuButton("static/ikoner/book_delete.png","Ta bort")
        backButton = create_menuButton("static/ikoner/arrow_left.png","Tillbaka")
        
        backButton.connect("clicked", self.gui.switch_page, "menu")
        showMissionButton.connect("clicked", self.gui.switch_page, "showMission")
        newMissionButton.connect("clicked", self.gui.switch_page, "addMission")
        deleteMissionButton.connect("clicked", self.gui.switch_page, "removeMission")
        self.pack_start(showMissionButton, False, False, padding=2)
        self.pack_start(newMissionButton, False, False, padding=2)
        self.pack_start(deleteMissionButton, False, False, padding=2)
        self.pack_start(backButton, False, False, padding=2)

        self.show_all()

class AddMissionPage(Page):

    def __init__(self, gui):
        super(AddMissionPage, self).__init__("addMission", gui, homogeneous=False,
                spacing=0)
        self.size_request = (300,300)
        self.unit = None

            
        hbox1 = gtk.HBox()
        vbox1 = gtk.VBox()
        self.vbox2 = gtk.VBox()
        nameLabel = gtk.Label("Namn:")
        self.nameEntry = gtk.Entry()
        infoLabel = gtk.Label("Info:")
        self.infoEntry = gtk.Entry()
        poiLabel = gtk.Label("POI:")
        self.poiEntry = gtk.Entry()
        poiButton = gtk.Button("Lägg Till")
        self.combo = gtk.Combo()
        self.poiList = []
        self.combo.set_popdown_strings(self.poiList)
        self.poiEntry.set_text("Välj en POI")

        self.infoView = gtk.TextView(buffer=None)
        self.infoView.set_wrap_mode(gtk.WRAP_WORD)
        infoLabel2 = gtk.Label("Info:")
        self.infoView.set_size_request(300,200)

        vbox1.set_size_request(300,300)
        vbox1.pack_start(nameLabel, False, False,0)
        vbox1.pack_start(self.nameEntry, False, False,0)
        vbox1.pack_start(infoLabel, False, False,0)
        vbox1.pack_start(self.infoEntry, False, False,0)
        vbox1.pack_start(poiLabel, False, False,0)
        vbox1.pack_start(self.poiEntry, False, False,0)
        vbox1.pack_start(poiButton, False, False,0)
        vbox1.pack_start(self.combo,False,False,10)
        #vbox1.pack_start(okButton, False, False,0)
        
        
        saveButton = create_menuButton("static/ikoner/disk.png","Spara")
        saveButton.connect("clicked", self.save, None)
        backButton = create_menuButton("static/ikoner/arrow_undo.png","Avbryt")
        self.showDetails = create_menuButton("static/ikoner/resultset_first.png","Visa Detaljer")
        self.hideDetails = create_menuButton("static/ikoner/resultset_last.png","G�m Detaljer")
        backButton.connect("clicked", self.gui.switch_page, "mission")
        #okButton.connect("clicked", dbupdate_press_callback, None)
        poiButton.connect("clicked", self.add_poi, None)
        self.showDetails.connect("clicked", self.details, "show")
        self.hideDetails.connect("clicked", self.details, "hide")
        
        hbox2 = gtk.HBox()
        hbox2.pack_start(backButton, True, True, padding=2)
        hbox2.pack_start(saveButton, True, True, padding=2)
        vbox1.pack_start(hbox2,False,False,2)
        vbox1.pack_start(self.showDetails,False,False,2)
        vbox1.pack_start(self.hideDetails,False,False,2)
        self.vbox2.pack_start(infoLabel2,False,False,0)
        self.vbox2.pack_start(self.infoView,False,False,0)
        
        hbox1.pack_start(vbox1, False, False, 2)
        hbox1.pack_start(self.vbox2, False, False, 2)
        self.pack_start(hbox1,False,False,0)

        self.show_all()
        self.vbox2.hide()
        self.hideDetails.hide()
        rpc.register("add_mission", self.add_mission)
        
    def save(self, button, widget=None):
        session = get_session()
        name = unicode(self.nameEntry.get_text())
        info = unicode(self.infoEntry.get_text())
        # the poi to use is the first one I guess :p
        poi = self.poiList[0]
        mission_save = str(packet.Packet("mission_save", name=name,\
                                desc=info, poi=poi.unique_id ))
        gobject.timeout_add(0, rpc.send, "qos", "add_packet", {"packet":mission_save})
          
    def add_poi(self, button, widget=None):
        sess = get_session()
        unit = sess.query(POI).filter(POI.id==self.unit["id"]).one()
        print "uni: %s" % unit
        self.poiList.append(unit)
        self.combo.set_popdown_strings([x.name for x in self.poiList])
        self.poiEntry.set_text("Välj en POI")
        self.unit = None     

    def update(self, unit):
        self.unit = unit
        self.poiEntry.set_text(str(self.unit["name"]))
               
    def on_show(self):
        # simulera en "göm detaljer"
        print "skön lr"
        self.poiList = []
        self.combo.set_popdown_strings([x.name for x in self.poiList])
        self.details(None, "hide")
        self.poiEntry.set_text("Välj en POI")
        
    def details(self, button, state, widget=None):
        if state == "show":
            self.gui.rightBook.set_size_request(600,300)
            self.vbox2.show()
            self.showDetails.hide()
            self.hideDetails.show()
        elif state == "hide":
            self.gui.rightBook.set_size_request(300,300)
            self.vbox2.hide()
            self.showDetails.show()
            self.hideDetails.hide()
    
    def add_mission(self, pack):
        print "add_mission"
        pack = packet.Packet.from_str(str(pack))
        session = get_session()
        data = pack.data
        miss = Mission(data["name"], data["created"], data["changed"])
        miss.status = data["status"]
        miss.desc = data["desc"]
        poi = session.query(POI).filter(POI.unique_id==data["poi"]).one()
        miss.poi = poi
        miss.unique_id = data["unique_id"]
        session.add(miss)
        session.commit()
            
class RemoveMissionPage(Page):

    def __init__(self, gui):
        super(RemoveMissionPage, self).__init__("removeMission", gui, homogeneous=False,
                spacing=0)
        self.size_request = (300,300)
        nameLabel = gtk.Label("Uppdrag:")
        self.selectBox = gtk.combo_box_new_text()
        testList = ["Operation: Save the Whale", "Nuke Accident", "Brand i Sk�ggetorp"]
        # TESTLIST SKA ERS?TTAS MED DATABAS-DATA
        self.pack_start(nameLabel, False, False,0)
        self.pack_start(self.selectBox, False, False,0)
        
        deleteButton = create_menuButton("static/ikoner/book_delete.png","Ta bort")
        deleteButton.connect("clicked", self.remove_item, None)
        backButton = create_menuButton("static/ikoner/arrow_undo.png","Avbryt")
        backButton.connect("clicked", self.gui.switch_page, "mission")
        
        hbox1 = gtk.HBox()
        hbox1.pack_start(backButton, True, True, padding=2)
        hbox1.pack_start(deleteButton, True, True, padding=2)
        self.pack_start(hbox1, False, False, 2)
        self.show_all()
        
        #GÖR SÅ ATT SERVERN TAR BORT OCKSÅ!
    def remove_item(self, button, widget=None):
        text = self.selectBox.get_active_text()
        id = ""
        for letter in text:
            if letter == ":":
                break
            id = id+letter
        session = get_session()
        for mission in session.query(Mission).filter(Mission.id==int(id)):
            print mission.name
            session.delete(mission)
            session.commit()
        self.delete_mission()
        
    def on_show(self):
        self.delete_mission()

    def delete_mission(self):
        self.selectBox.get_model().clear()
        session = get_session()
        for mission in session.query(Mission):
            text = str(mission.id)+ ": "+mission.name 
            self.selectBox.append_text(text)
            
        

class ObjectPage(Page):
    def checkNew(self, button, widget=None):
        self.gui._pages["addObject"].details(None, None, "show")
        self.gui.switch_page("addObject")

    def __init__(self, gui):
        super(ObjectPage, self).__init__("object", gui, homogeneous=False,
                spacing=0)
        self.size_request = (300,300)
        newButton = create_menuButton("static/ikoner/map_add.png",
                "Lagg till")
        deleteButton = create_menuButton("static/ikoner/map_delete.png","Ta bort")
        backButton = create_menuButton("static/ikoner/arrow_left.png","Tillbaka")

        backButton.connect("clicked", self.gui.switch_page, "menu")
        newButton.connect("clicked", self.checkNew, None)
        deleteButton.connect("clicked", self.gui.switch_page, "removeObject")
        self.pack_start(newButton, False, False, padding=2)
        self.pack_start(deleteButton, False, False, padding=2)
        self.pack_start(backButton, False, False, padding=2)

        self.show_all()
        
class AddObjectPage(Page):

    def __init__(self, gui):
        super(AddObjectPage, self).__init__("addObject", gui, homogeneous=False,
                spacing=0)
        self.size_request = (300,300)

        
        hbox1 = gtk.HBox()
        vbox1 = gtk.VBox()
        self.vbox2 = gtk.VBox()
        nameLabel = gtk.Label("Namn:")
        self.nameEntry = gtk.Entry()
        typeLabel = gtk.Label("Typ:")
        self.poi_type_selector = gtk.combo_box_new_text()
        #typeLabel = gtk.Label("Typ:")
        #self.typeEntry = gtk.Entry()
        infoLabel = gtk.Label("Information:")
        infoEntry = gtk.Entry()
        self.pos_label = gtk.Label("Position:")
        self.pos_plz_click = gtk.Label("(klicka på kartan):")
        self.xEntry = gtk.Entry()
        self.xEntry.set_editable(False)
        self.yEntry = gtk.Entry()
        self.yEntry.set_editable(False)
        
        self.infoView = gtk.TextView(buffer=None)
        self.infoView.set_wrap_mode(gtk.WRAP_WORD)
        infoLabel = gtk.Label("Info:")
        self.infoView.set_size_request(300,200)

        vbox1.set_size_request(300,300)
        vbox1.pack_start(nameLabel, False, False,0)
        vbox1.pack_start(self.nameEntry, False, False,0)
        vbox1.pack_start(typeLabel, False, False,0)
        vbox1.pack_start(self.poi_type_selector, False, False,0)
        vbox1.pack_start(self.pos_label, False, False,0)
        vbox1.pack_start(self.pos_plz_click, False, False,0)
        vbox1.pack_start(self.xEntry, False, False,0)
        vbox1.pack_start(self.yEntry, False, False,0)
        
        saveButton = create_menuButton("static/ikoner/disk.png","Spara")
        backButton = create_menuButton("static/ikoner/arrow_undo.png","Avbryt")
        self.showDetails = create_menuButton("static/ikoner/resultset_first.png","Visa Detaljer")
        self.hideDetails = create_menuButton("static/ikoner/resultset_last.png","G�m Detaljer")

        backButton.connect("clicked", self.gui.switch_page, "object")

        self.showDetails.connect("clicked", self.details, "show")
        self.hideDetails.connect("clicked", self.details, "hide")
        saveButton.connect("clicked", self.send_object)
        
        session = get_session()
        
        poi_type_index = 0
        default_poi_type_index = 0
        for poi_type in session.query(POIType).order_by(POIType.name):
            if poi_type.name == u"övrigt":
                default_poi_type_index = poi_type_index
            poi_type_index = poi_type_index + 1
            self.poi_type_selector.append_text(poi_type.name)
            
        self.poi_type_selector.set_active(default_poi_type_index)
        
        hbox2 = gtk.HBox()
        hbox2.pack_start(backButton, True, True, padding=2)
        hbox2.pack_start(saveButton, True, True, padding=2)
        
        vbox1.pack_start(hbox2, False, False, 2)
        vbox1.pack_start(self.showDetails,False,False,2)
        vbox1.pack_start(self.hideDetails,False,False,2)
        hbox1.pack_start(vbox1,True,True,2)
        self.vbox2.pack_start(infoLabel,False,False,0)
        self.vbox2.pack_start(self.infoView,False,False,0)
        hbox1.pack_start(self.vbox2,False,False,0)
        self.pack_start(hbox1,False,False,0)
        self.show_all()
        self.vbox2.hide()
        self.xEntry.hide()
        self.yEntry.hide()
        self.hideDetails.hide()

    def send_object(self, button):
        #lägg till så man kan fixa in type
        print self.poi_type_selector.get_active_text()
        poi = str(packet.Packet("poi",id = "", poi_type = unicode(self.poi_type_selector.get_active_text()), name = self.nameEntry.get_text(), coordx = self.xEntry.get_text(), coordy = self.yEntry.get_text()))
        
        #rpc.send("qos", "add_packet", packet=poi)
        gobject.timeout_add(0, rpc.send, "qos", "add_packet", {"packet":poi})
    
    def map_dblclick(self, coordx, coordy):
        print "Jon bajsar!"
        self.xEntry.show()
        self.yEntry.show()
        self.pos_plz_click.hide()
        self.xEntry.set_text(str(coordx))
        self.yEntry.set_text(str(coordy))

    def on_show(self):
        # simulera en "göm detaljer"
        self.details(None, "hide")
        self.xEntry.hide()
        self.yEntry.hide()
        self.pos_plz_click.show()
        
    def details(self, button, state, widget=None):
        if state == "show":
            self.gui.rightBook.set_size_request(600,300)
            self.vbox2.show()
            self.showDetails.hide()
            self.hideDetails.show()
        elif state == "hide":
            self.gui.rightBook.set_size_request(300,300)

            self.vbox2.hide()
            self.showDetails.show()
            self.hideDetails.hide()

class ShowObjectPage(Page):
    def checkNew(self, button, widget=None):
        self.gui._pages["showObject"].details(None, None, "show")
        self.gui.switch_page("showObject")

    def __init__(self, gui):
        
        super(ShowObjectPage, self).__init__("showObject", gui,
homogeneous=False,
                spacing=0)
        
        
        hbox1 = gtk.HBox(False, 0)
        hbox2 = gtk.HBox(False, 0)
        hbox3 = gtk.HBox(False, 0)
        hbox4 = gtk.HBox(False, 0)
        self.image = gtk.Image()
        self.image.set_from_file(None)
        newButton = create_menuButton("static/ikoner/map_add.png",
                "Lagg till")
        self.label = gtk.Label("Brandbil")
        self.idLabel = gtk.Label("ID: ")
        self.xLabel = gtk.Label("x:")
        self.yLabel = gtk.Label("y:")
        self.changedLabel = gtk.Label("Last Changed:")
        self.changedLabel2 = gtk.Label("Last Changed:")
        hbox1.pack_start(self.image, False, False, padding=15)
        hbox1.pack_start(self.label, False, False, padding=2)

        
       #vbox1.pack_start(self.idLabel, False, False, padding=2)
       #vbox1.pack_start(self.changedLabel, False, False, padding=2)
        #hbox1.pack_start(vbox1, False, False, padding=2)
        self.pack_start(hbox1, False, False, padding=2)
        self.pack_start(self.xLabel, False, False, padding=2)
        self.pack_start(self.yLabel, False, False, padding=2)
        self.pack_start(self.changedLabel2, False, False, padding=2)
        self.pack_start(self.changedLabel, False, False, padding=2)
        self.show_all()
        
    def update(self,unit):
        session = get_session()
        if unit["type"] == "units":
            for units in session.query(Unit).filter(Unit.id==unit["id"]):
                self.label.set_text(str(units.name))
                self.image.set_from_file(units.type.image)
                self.idLabel.set_text("ID: " + str(units.id))
                self.xLabel.set_text("coord X: " + str(units.coordx))
                self.yLabel.set_text("coord Y: " + str(units.coordy))
                self.changedLabel.set_text("Senast Ändrad: " + str(units.time_changed))
                self.xLabel.modify_font(pango.FontDescription("Verdana"));
                session.commit()
                
        elif unit["type"] == "poi":
            for poi in session.query(POI).filter(POI.id==unit["id"]):
                self.label.set_text(str(poi.name))
                self.image.set_from_file(poi.type.image)
                self.idLabel.set_text("ID: " + str(poi.id))
                self.xLabel.set_text("coord X: " + str(poi.coordx))
                self.yLabel.set_text("coord Y: " + str(poi.coordy))
                self.changedLabel.set_text("Senast Ändrad: " + str(poi.time_changed))

class ShowMissionPage(Page):
    def __init__(self, gui):
        
        super(ShowMissionPage, self).__init__("showMission", gui, 
                homogeneous=False, spacing=0)

        # TODO: fixa så d här inte failar på missions me samma namn!
        s = get_session()
        self.missionList = [x.name for x in s.query(Mission).all()]
        self.combo = gtk.combo_box_new_text()
        self.combo.get_model().clear()
        for user in self.missionList:
            self.combo.append_text(user)

        hbox1 = gtk.HBox(False, 0)
        hbox2 = gtk.HBox(False, 0)
        hbox3 = gtk.HBox(False, 0)
        hbox4 = gtk.HBox(False, 0)
        self.label = gtk.Label("navn")

        self.doButton = gtk.Button()
        self.doButton.add(gtk.Label(">>"))
        self.doButton.show_all()
        self.doButton.connect("clicked", self.buttonPushed, None)

        self.image = gtk.Image()
        self.image.set_from_file(None)
        self.idLabel = gtk.Label("ID: ")
        self.poi = gtk.Label("Plats: ")
        self.status = gtk.Label("Status: ")
        self.desc = gtk.Label("Beskrivning: ")
        #hbox1.pack_start(self.label, False, False, padding=2)
        #hbox1.pack_start(self.idLabel, False, False, padding=2)
        #hbox1.pack_start(self.poi, False, False, padding=2)
        #hbox1.pack_start(self.status, False, False, padding=2)
        #hbox1.pack_start(self.desc, False, False, padding=2)
        hbox1.pack_start(self.image, False, False, padding=15)
        hbox1.pack_start(self.label, False, False, padding=2)
        
        #vbox1.pack_start(self.idLabel, False, False, padding=2)
        #vbox1.pack_start(self.changedLabel, False, False, padding=2)
        #hbox1.pack_start(vbox1, False, False, padding=2)
        hbox2.pack_start(self.combo, False, False, padding=2)
        hbox2.pack_start(self.doButton, False, False, padding=2)
        self.pack_start(hbox2, False, False, padding=2)
        self.pack_start(hbox1, False, False, padding=2)
        self.pack_start(self.poi, False, False, padding=2)
        self.pack_start(self.idLabel, False, False, padding=2)
        self.pack_start(self.status, False, False, padding=2)
        self.pack_start(self.desc, False, False, padding=2)
        self.show_all()


    def buttonPushed(self, whatev, lulz):
        s = get_session()
        miss = s.query(Mission).filter(Mission.name==self.combo.get_active_text())[0]
        self.update(miss)

    def on_show(self):
        s = get_session()
        self.missionList = [x.name for x in s.query(Mission).all()]
        self.combo.get_model().clear()
        for user in self.missionList:
            self.combo.append_text(user)
        self.update()
        
    def update(self, mission=None):
        if mission is None:
            session = get_session()
            mission = session.query(Mission)[0]

        self.image.set_from_file(mission.poi.type.image)
        self.label.set_text(str(mission.name))
        self.idLabel.set_text("ID: " + str(mission.unique_id))
        self.poi.set_text("Plats: " + str(mission.poi.name))
        self.status.set_text("Status: " + str(mission.status))
        self.desc.set_text("Beskrivning: " + str(mission.desc))
        
class Gui(hildon.Program):
    _map = None
    _map_change_zoom = None
    def require_login(self):
        # TODO: snyggare:
        # den här räknar me att login e på sista sidan
        # och TVINGAR inget.
        print "Show login"
        self.show_login()
        #last_page = self.view.get_n_pages()
        #self.view.set_current_page(last_page-1)

    def on_window_state_change(self, widget, event, *args):
        if event.new_window_state & gtk.gdk.WINDOW_STATE_FULLSCREEN:
            self.window_in_fullscreen = True
        else:
            self.window_in_fullscreen = False

    def on_key_press(self, widget, event, *args):
        # Ifall "fullscreen"-knappen på handdatorn har aktiverats.
        if event.keyval == gtk.keysyms.F6:
            if self.window_in_fullscreen:
                self.window.unfullscreen()
            else:
                self.window.fullscreen()
        # Pil vänster, byter vy
        elif event.keyval == 65361:
            if (self.view.get_current_page() != 0):
                self.view.prev_page()
        # Pil höger, byter vy
        elif event.keyval == 65363:
            if (self.view.get_current_page() != 1):
                self.view.next_page()
        # Zoom -    
        elif event.keyval == 65477:
            self._map_change_zoom("-")
        # Zoom +
        elif event.keyval == 65476:
            self._map_change_zoom("+")
    # __INIT__------------------
    #       Description: the INIT funktion...
    def __init__(self, map):
        # Initierar hildon (GUI-biblioteket för N810)
        hildon.Program.__init__(self)

        # Sparar handdatorns karta.
        self._map = map

        # Skapar programmets fönster
        self.window = hildon.Window()
        # Någon storlek så att PyGTK inte klagar
        self.window.set_size_request(200, 200)
        # Funktion som körs när prorammet ska stängas av
        self.window.connect("destroy", self.menu_exit)
        self.add_window(self.window)

        self._pages = {}
        self._pages["menu"] = MenuPage(self)
        self._pages["mission"] = MissionPage(self)
        self._pages["settings"] = SettingsPage(self)
        self._pages["contact"] = ContactPage(self)
        self._pages["addMission"] = AddMissionPage(self)
        self._pages["removeMission"] = RemoveMissionPage(self)
        self._pages["object"] = ObjectPage(self)
        self._pages["addObject"] = AddObjectPage(self)
        self._pages["showObject"] = ShowObjectPage(self)
        self._pages["showMission"] = ShowMissionPage(self)

        # Möjliggör fullscreen-läge
        self.window.connect("key-press-event", self.on_key_press)
        self.window.connect("window-state-event", self.on_window_state_change)
        # Programmet är inte i fullscreen-läge från början.
        self.window_in_fullscreen = False
        


        self.view = gtk.Notebook()
        self.view.set_show_tabs(False)
        self.view.set_show_border(False)
        self.view.insert_page(self.create_map_view())
        self.view.insert_page(self.create_settings_view())
        #self.view.insert_page(self.create_login_view())

        # Lägger in vyn i fönstret
        self.window.add(self.view)

        # Skapar menyn
        self.window.set_menu(self.create_menu())
        
        rpc.register("access", self.access)
        #Visar login-dialog
        self.show_login()
        
        rpc.register("require_login", self.require_login)
    
    def switch_page(self, page_name, widget=None):
        # if widget is supplied, it actually contains page_name, so swap!
        if widget is not None:
            page_name = widget
        # kör "on_show" på sidan som ska visas
        self._pages[page_name].on_show()
        num = self.rightBook.page_num(self._pages[page_name])
        self.rightBook.set_size_request(*self._pages[page_name].size_request)
        self.rightBook.set_current_page(num)

    def map_dblclick(self, coordx, coordy):
        active_page = self.rightBook.get_nth_page(self.rightBook.get_current_page())
        active_page.map_dblclick(coordx, coordy)

    def show_object(self, unit):
        currentPage = self.rightBook.get_current_page()
        if currentPage is not 4:
            if unit["type"] == "units" or unit["type"] == "poi":
                self.switch_page("showObject")
                self.openButton.hide()
                self.closeButton.show()
                self.vbox1.show()
                active_page = self.rightBook.get_nth_page(self.rightBook.get_current_page())
                active_page.update(unit)
        elif currentPage is 4 and unit["type"] is "poi":
            print "NAJS"
            active_page = self.rightBook.get_nth_page(self.rightBook.get_current_page())
            active_page.update(unit)
        
    def create_map_view(self):

            
        def openButton_press_callback(button, widget, data=None):
            self.openButton.hide()
            self.closeButton.show()
            self.vbox1.show()
            self.switch_page("menu")

        def closeButton_press_callback(button, widget, data=None):
            self.openButton.show()
            self.closeButton.hide()
            self.vbox1.hide()
            return

        def show_mission(self, widget, data=None):
            menuBox.hide()
            return
        def side_bar_clicked(self, data, widget=None):
            print "inne"
            if data == "+":
                map.change_zoom("+")
            else:
                map.change_zoom("-")
            return True

        def create_barButton(bild):
            buttonBox = gtk.HBox(False, spacing=1)
            button = gtk.Button()
            buff = gtk.gdk.PixbufAnimation(bild)
            image = gtk.Image()
            image.set_from_animation(buff)
            image.show()
            buttonBox.pack_start(image, expand=False, fill=False, padding=5)
            button.add(buttonBox)
            button.show_all()
            button.set_size_request(60, 40)
            return button

        hbox1 = gtk.HBox(False, 1)
        hbox2 = gtk.HBox(False, 1)
        vboxMenu = gtk.VBox(False, 1)
        self.vbox1 = gtk.VBox(False, 1)
        map = gui_map.Map(self._map, self)
#SIDEBAR TEST
        login = create_barButton("static/ikoner/sidebar/key.png")
        zoomIn = create_barButton("static/ikoner/sidebar/magnifier_zoom_in.png")
        
        zoomOut=create_barButton("static/ikoner/sidebar/magnifier_zoom_out.png")
        zoomFull = create_barButton("static/ikoner/sidebar/map_magnify.png")

        onlineButton = create_barButton("static/ikoner/status_online.png")  
        onlineImage = gtk.Image()
        onlineImage.set_from_file("static/ikoner/status_offline.png")
        
        zoomIn.connect("clicked", side_bar_clicked, "+")
        zoomOut.connect("clicked", side_bar_clicked, "-")
        zoomFull.connect("clicked", closeButton_press_callback, None)
        vboxMenu.pack_start(zoomIn,False,True, 3)
        vboxMenu.pack_start(zoomFull,False,True, 3)
        vboxMenu.pack_start(zoomOut,False,True, 3)
        vboxMenu.pack_end(login,False,True, 3)
        vboxMenu.pack_end(onlineImage,False,True, 3)
        vboxMenu.show_all()
        #SHOW / HIDE buttons----------------------
        self.openButton = gtk.Button()
        buff5 = gtk.gdk.PixbufAnimation("static/ikoner/resultset_first.png")
        openArrow = gtk.Image()
        openArrow.set_from_animation(buff5)
        openArrow.show()
        login.connect("clicked", self.handle_menu_items, 2)
        self.openButton.connect("clicked", openButton_press_callback, None)
        
        self.closeButton = gtk.Button()
        buff6 = gtk.gdk.PixbufAnimation("static/ikoner/resultset_last.png")
        closeArrow = gtk.Image()
        closeArrow.set_from_animation(buff6)
        closeArrow.show()
        
        self.closeButton.connect("clicked", closeButton_press_callback, None)
        self.openButton.add(openArrow)
        self.openButton.show()
        openArrow.show()
        self.closeButton.add(closeArrow)
        self.closeButton.hide()
        closeArrow.show()
        
        # MENUBOX-----------------------
        rightBook = gtk.Notebook()
        missionBox = gtk.VBox(False,1)
        for page in self._pages.values():
            rightBook.insert_page(page)
        rightBook.set_show_tabs(False)
        rightBook.set_show_border(False)
        rightBook.show()
        self.rightBook = rightBook
        
        # MISSIONBOX-----------------------

        hbox1.pack_start(vboxMenu, expand=False, fill=False, padding=3)
        hbox1.pack_start(map, expand=True, fill=True, padding=0)
        hbox1.pack_start(hbox2, expand=False, fill=False, padding=0)
        hbox2.pack_start(self.openButton, expand=False, fill=False, padding=0)
        hbox2.pack_start(self.closeButton, expand=False, fill=False, padding=0)
        hbox2.pack_start(self.vbox1, False, False, 0)
        
        self.vbox1.pack_start(rightBook, False, False, padding=0)
        
        hbox1.show()
        hbox2.show()
        map.show()
        # Sparar undan funktionen som möjliggör zoomning
        self._map_change_zoom = map.change_zoom
        
        return hbox1

    def create_login_view(self):
        def dbcheck_press_callback(button, widget, data=None):   
            #Detta behövs inte här, men kanske inte fungerar på andra stället
            #session = get_session()
            #create_tables()        
            #session.bind
            #session.query(User).all()
            self.user = unicode(userText.get_text())
            self.pw = unicode(passText.get_text())
            self.unit_name = unicode(self.combo.get_active_text())
            login = str(packet.Packet("login", username=self.user, password=self.pw, unitname=self.unit_name))
            #print rpc.send("qos", "add_packet", packet=login)
            gobject.timeout_add(0, rpc.send, "qos", "add_packet", {"packet":login})

        hboxOUT  = gtk.HBox(homogeneous=False, spacing=1)
        vbox1 = gtk.VBox(homogeneous=False, spacing=1)
        hbox1 = gtk.HBox(homogeneous=False, spacing=1)
        hbox2 = gtk.HBox(homogeneous=False, spacing=1)
        self.combo = gtk.combo_box_new_text()
        
        session = get_session()
        
        ambulans = UnitType(u"Ambulans1", "static/ikoner/ambulans.png")

        self.combo.append_text(("Ingen unit"))
        self.combo.set_active(0)

        for unit in session.query(Unit).order_by(Unit.name):
            self.combo.append_text(unit.name)
            print "Det du har är: ", unit.name
 
        userText = gtk.Entry(max=0)
        userLabel = gtk.Label("Användare")
        passText = gtk.Entry(max=0)
        passLabel = gtk.Label("Lösenord")
        okButton = gtk.Button("Login")
        okButton.set_size_request(70, 50)
        okButton.connect("clicked", dbcheck_press_callback, None)
        statusLabel = gtk.Label("No status")
        unittypeLabel = gtk.Label("Context")
        
        vbox1.pack_start(hbox1, expand=False, fill=False, padding=1)
        vbox1.pack_start(hbox2, expand=False, fill=False, padding=1)
        vbox1.pack_start(okButton, expand=False, fill=False, padding=1)
        hbox1.pack_start(userText, expand=False, fill=False, padding=1)
        hbox1.pack_start(userLabel, expand=False, fill=False, padding=1)
        hbox2.pack_start(passText, expand=False, fill=False, padding=1)
        hbox2.pack_start(passLabel, expand=False, fill=False, padding=1)
        vbox1.pack_start(statusLabel, expand=False, fill=False, padding=1)
        vbox1.pack_start(unittypeLabel, expand=False, fill=False, padding=1)
        vbox1.pack_start(self.combo, expand=False, fill=False, padding=1)
        hboxOUT.pack_start(vbox1, expand=True, fill=False, padding=1)
        
        userText.show()
        userLabel.show()
        unittypeLabel.show()
        passText.show()
        passLabel.show()
        okButton.show()
        statusLabel.show()
        hbox1.show()
        hbox2.show()
        vbox1.show()
        hboxOUT.show()
        self.combo.show()
        #Skapar rpc

        def receive_updates(val):
            print "recv yeah %s" %val
        
        def access(bol):
            print "körde första!"
            if bol:
                statusLabel.set_label("Access granted")
                unit = self.combo.get_active_text()
                #Kollar om user redan finns
                insession = True
                for users in session.query(User):
                    if users.type:
                        users.type.is_self = False
                    if users.name == self.user:
                        insession = False
                        current_user = users
                        break
                    else:
                        insession = True
                if insession:
                    print "Skapar användare"
                    current_user = User(self.user,self.pw)
                    session.add(current_user)
                    session.commit()
                #ändrar users unit
                for units in session.query(Unit).filter_by(name=unit):
                    current_user.type = units
                    current_user.type.is_self = True
                    session.commit()
                # begär uppdateringar från servern
                status = {}
                status["POI"] = dict([(p.unique_id, p.changed.strftime("%s")) \
                        for p in session.query(POI).all()])
                print status
                p = str(packet.Packet("request_updates", status=status))
                gobject.timeout_add(0, rpc.send, "qos", "add_packet", {"packet": p})
            else:
                statusLabel.set_label("Access denied")
       
        rpc.register("access", access)
        return hboxOUT


    def access(self, bol):
        print "ja körde visst andra :S"
        if bol:
            print "Access"
            self.status_label.set_label("Status: Access Granted!")
            #Kollar om user redan finns
            insession = True
            session = get_session()
            for users in session.query(User):
                if users.type:
                    users.type.is_self = False
                if users.name == self.user:
                    insession = False
                    current_user = users
                    break
                else:
                    insession = True
            if insession:
                print "Skapar användare"
                current_user = User(self.user,self.pw)
                session.add(current_user)
                session.commit()
            #�ndrar users unit
            for units in session.query(Unit).filter_by(name=self.unit_name):
                current_user.type = units
                current_user.type.is_self = True
                session.commit()
            self.access_granted = True
            # begär uppdateringar från servern
            status = {}
            status["POI"] = dict([(p.unique_id, p.changed.strftime("%s")) \
                    for p in session.query(POI).all()])
            print status
            p = str(packet.Packet("request_updates", status=status))
            gobject.timeout_add(0, rpc.send, "qos", "add_packet", {"packet": p})
            self.window.show()
            self.view.show()
            self.login_window.destroy()
        else:
            print "Denied"
            self.status_label.set_label("Status: Fel användarnamn eller lösenord")

    def show_login(self):
        def dbcheck_press_callback(widget):   
            self.user = unicode(user_text.get_text())
            self.pw = unicode(pass_text.get_text())
            self.unit_name = unicode(self.unit_type_selector.get_active_text())
            print self.user
            print self.pw
            print self.unit_name
            login = str(packet.Packet("login",
            username=self.user,
            password=self.pw,
            unitname=self.unit_name))
            self.status_label.set_label("Status: Kontaktar Servern...")
            #rpc.send("qos", "add_packet", packet=login)
            gobject.timeout_add(0, rpc.send, "qos", "add_packet", {"packet":login})
        def skip_mode(widget):
            self.login_window.destroy()
            self.window.show()
            self.view.show()
        self.view.hide()
        self.login_window = hildon.Window()
        self.login_window.set_transient_for(self.window)
        self.login_window.set_modal(True)

        user_text = gtk.Entry(max=0)
        user_label = gtk.Label("Användarnamn")
        user_box = gtk.HBox(spacing=1)
        user_box.pack_start(user_label, expand=False, fill=False, padding=1)
        user_box.pack_start(user_text, expand=False, fill=False, padding=1) 
        pass_text = gtk.Entry(max=0)
        pass_text.set_invisible_char("*")
        pass_text.set_visibility(False)
        pass_label = gtk.Label("Lösenord")
        pass_box = gtk.HBox(spacing=0)
        pass_box.pack_start(pass_label, expand=False, fill=False, padding=1)
        pass_box.pack_start(pass_text, expand=False, fill=False, padding=1)

        self.unit_type_selector = gtk.combo_box_new_text()
        session = get_session()
        for unit in session.query(Unit).order_by(Unit.name):
            self.unit_type_selector.append_text(unit.name)
        self.unit_type_selector.set_active(3) 
        self.status_label = gtk.Label("Status:")
        
        insert_box = gtk.VBox(spacing=0)

        insert_box.pack_start(user_box)
        insert_box.pack_start(pass_box)
        insert_box.pack_start(self.unit_type_selector)
        insert_box.pack_start(self.status_label)

        button_box = gtk.HBox(spacing=0)
        login_button = create_menuButton("static/ikoner/disk.png",
                                            "Logga in")
        skip_button = create_menuButton("static/ikoner/disk.png",
                                            "Jag orkar inte")
        login_button.connect("clicked", dbcheck_press_callback)
        skip_button.connect("clicked", skip_mode)
        exit_button = create_menuButton("static/ikoner/arrow_undo.png",
                                            "Avsluta")
        exit_button.connect("clicked", sys.exit)
        button_box.pack_start(login_button)
        button_box.pack_end(exit_button)
        button_box.pack_end(skip_button)

        window_box = gtk.VBox(spacing=0)
        window_box.pack_start(insert_box)
        window_box.pack_end(button_box)


        self.login_window.add(window_box)
        self.login_window.show_all()
        self.add_window(self.login_window)

    def create_settings_view(self):
        frame = gtk.Frame("Inställningar")
        frame.set_border_width(5)

        # Skicka GPS-koordinater till basen?
        hbox2 = gtk.HBox(homogeneous=False, spacing=0)
        lblSkickaGPSKoordinater = gtk.Label("Skicka GPS koordinater till basen")
        lblSkickaGPSKoordinater.set_justify(gtk.JUSTIFY_LEFT)
        chkSkickaGPSKoordinater = gtk.CheckButton("Ja")
        #chkSkickaGPSKoordinater.connect("toggled", self.chkSkickaGPSKoordinater_callback)
        hbox2.pack_start(lblSkickaGPSKoordinater, True, True, 5)
        hbox2.pack_start(chkSkickaGPSKoordinater, False, False, 5)

        # Skapar knappen som sparar inställningarna
        btnSpara = gtk.Button("Spara!")
        btnSpara.connect("clicked", self.handle_menu_items, 0)

        vbox = gtk.VBox(homogeneous=False, spacing=0)
        #vbox.pack_start(hbox1, False, False, 0)
        vbox.pack_start(hbox2, False, False, 5)
        vbox.pack_start(btnSpara, False, False, 5)

        frame.add(vbox)
        frame.show_all()
        return frame


    def create_menu(self):
        # Skapar tre stycken meny-inlägg.
        menuItemKarta = gtk.MenuItem("Karta")
        menuItemInstallningar = gtk.MenuItem("Inställningar")
        menuItemSeparator = gtk.SeparatorMenuItem()
        menuItemExit = gtk.MenuItem("Exit")

        menuItemKarta.connect("activate", self.handle_menu_items, 0)
        menuItemInstallningar.connect("activate", self.handle_menu_items, 1)
        menuItemExit.connect("activate", self.menu_exit)
        # Skapar en meny som vi lägger in dessa inlägg i.
        menu = gtk.Menu()
        menu.append(menuItemKarta)
        menu.append(menuItemInstallningar)
        menu.append(menuItemSeparator)
        menu.append(menuItemExit)

        return menu
    # vÃ¤rden frÃ¥n en markering i en lista. Skicka in listan och kolumnen du
    # vill ha ut vÃ¤rdet ifrÃ¥n sÃ¥ skÃ¶ter funktionen resten. FÃ¶rsta kolumnen Ã¤r 0,
    # andra 1 osv. 
    def get_value_from_treeview(self, treeview, column):
        # LÃ¤s mer om vad row innehÃ¥ller hÃ¤r (gtk.TreeSelection.get_selected_row):
        # http://www.pygtk.org/pygtk2reference/class-gtktreeselection.html
        row = treeview.get_selection().get_selected_rows()
      
        if len(row[1]) > 0:
            # row innehÃ¥ller en tuple med (ListStore(s), path(s))
            # Vi plockar ut fÃ¶rsta vÃ¤rdet i paths. Eftersom vi enbart tillÃ¥ter
            # anvÃ¤ndaren att markera en rad i taget kommer det alltid bara finnas
            # ett vÃ¤rde i paths.
            path = row[1][0]
          
            # HÃ¤mtar modellen fÃ¶r treeview
            treemodel = treeview.get_model()
          
            # Returnerar vÃ¤rdet
            return treemodel.get_value(treemodel.get_iter(path), column)
        else:
            return None

    def handle_menu_items(self, widget, num):
        self.view.set_current_page(num)

    def menu_exit(self, widget, data=None):
        # StÃ¤nger net GUI:t.
        gtk.main_quit()

    def run(self):
        gtk.main()
