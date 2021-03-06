# -*- coding: utf-8 -*-
import time
import gtk
import tilenames
#import map.map_xml_reader
#import map
#from map.mapdata import *
#from datetime import datetime

class MapWidget(gtk.DrawingArea):
    db = None
    sign = False

    bounds = {"min_latitude":0,
                "max_latitude":0,
                "min_longitude":0,
                "max_longitude":0}

    def __init__(self, lat, long):
        gtk.DrawingArea.__init__(self)
        gtk.Box.__init__(self)
        #mapxml = map.map_xml_reader.MapXML("map/data/map.xml")
        #self.mapdata = map.mapdata.MapData(mapxml.name, mapxml.levels)
        # queue_draw() ärvs från klassen gtk.DrawingArea
        # modellen anropar redraw när något ändras så att vyn uppdateras
        #self.mapdata.redraw_function = self.queue_draw
        self.focus = (float(lat), float(long))
        self.pos = {"x":0, "y":0}
        self.cols = 0
        self.rows = 0
        self.movement_from = {"x": 0, "y":0}
        self.allow_movement = False
        self.last_movement_timestamp = 0.0
        self.zoom_level = 15
        self.set_size_request(640, 480)

        #self.gps_x = self.mapdata.focus["longitude"]
        #self.gps_y = self.mapdata.focus["latitude"]
        #self.origin_position = self.mapdata.focus

        # events ;O
        self.set_flags(gtk.CAN_FOCUS)
        self.connect("expose_event", self.handle_expose_event)

        self.connect("button_press_event", self.handle_button_press_event)
        
        self.connect("button_release_event", self.handle_button_release_event)
        self.connect("motion_notify_event", self.handle_motion_notify_event)
#        self.connect("key_press_event", self.handle_key_press_event)
        self.set_events(gtk.gdk.BUTTON_PRESS_MASK |
                        gtk.gdk.BUTTON_RELEASE_MASK |
                        gtk.gdk.EXPOSURE_MASK |
                        gtk.gdk.LEAVE_NOTIFY_MASK |
                        gtk.gdk.POINTER_MOTION_MASK |
                        gtk.gdk.POINTER_MOTION_HINT_MASK)
                         #|                        gtk.gdk.KEY_PRESS_MASK)
        # add all current objects in db to map
        self.add_all_mapobjects()
        
    def add_all_mapobjects(self):
        '''
        Add all objects from the database to the dict with objects to draw.
        '''
        """
        mapobjectdata = self.db.get_all_mapobjects()
        for data in mapobjectdata:
            if data.__class__ == shared.data.UnitData:
                self.mapdata.objects[data.id] = Unit(data)
            elif data.__class__ == shared.data.POIData:
                self.mapdata.objects[data.id] = POI(data)
        self.queue_draw()
        """

    def add_map_object(self, database, data):
        """
        if data.__class__ == shared.data.UnitData:
            self.mapdata.objects[data.id] = Unit(data)
        elif data.__class__ == shared.data.POIData:
            self.mapdata.objects[data.id] = POI(data)  
        elif data.__class__ == shared.data.Alarm:
            self.mapdata.objects[data.poi.id] = POI(data.poi)  
        elif data.__class__ == shared.data.MissionData:
            self.mapdata.objects[data.poi.id] = POI(data.poi)
        self.queue_draw()
        """
        
    def change_map_object(self, database, data):
        """
        self.add_map_object(database,data)
        """

    def delete_map_object(self, database, data):
        """
        if data.__class__ == shared.data.Alarm:
            if data.poi.id in self.mapdata.objects.keys():
                del self.mapdata.objects[data.poi.id]  
        elif data.__class__ == shared.data.MissionData:
            if data.poi.id in self.mapdata.objects.keys():
                del self.mapdata.objects[data.poi.id]
        else:
            if data.id in self.mapdata.objects.keys():
                del self.mapdata.objects[data.id]

        self.queue_draw()
        """

    def zoom(self, change):
        # Frigör minnet genom att ladda ur alla tiles för föregående nivå
#        level = self.mapdata.get_level(self.zoom_level)
#        level.unload_tiles("all")
      
        if change == "+":
            if self.zoom_level < 3:
                self.zoom_level += 1
        else:
            if self.zoom_level > 1:
                self.zoom_level -= 1

        # Ritar ny nivå
        self.queue_draw()

#    def handle_key_press_event(self, widget, event):
#        pass

    # Hanterar rörelse av kartbilden
    def handle_button_press_event(self, widget, event):
        self.movement_from["x"] = event.x
        self.movement_from["y"] = event.y
        self.origin_position = self.focus
        self.last_movement_timestamp = time.time()
        #self.set_clicked_coord(widget, event)
        #self.draw_clicked_pos(widget, event)
        #result = self.draw_marked_object(widget, event)
        
        #if result:
        self.allow_movement = True
        return True

    def handle_button_release_event(self, widget, event):
        self.allow_movement = False
        return True

    def handle_motion_notify_event(self, widget, event):
        if self.allow_movement:
            if event.is_hint:
                x, y, state = event.window.get_pointer()
            else:
                x = event.x
                y = event.y
                state = event.state

            # Genom tidskontroll undviker vi oavsiktlig rörelse av kartan,
            # t ex ifall någon råkar nudda skärmen med ett finger eller liknande.
            if time.time() > self.last_movement_timestamp + 0.1:
                deltax = self.movement_from["x"] - x
                deltay = self.movement_from["y"] - y
                print deltax, deltay
                #self.mapdata.set_focus(self.origin_position["longitude"] + lon,
                                       #self.origin_position["latitude"] - lat)
                self.movement_from["x"] = x
                self.movement_from["y"] = y

                # Ritar om kartan
                self.focus = (self.focus[0] + deltay*self.tileheight_deg/256, deltax*self.tilewidth_deg/256 + self.focus[1])
                #self.focus = (self.focus[0] + 0.01, self.focus[1]+0.01)
                self.queue_draw()

        return True

    def handle_expose_event(self, widget, event):
        self.context = widget.window.cairo_create()

        # Regionen vi ska rita på
        self.context.rectangle(event.area.x,
                               event.area.y,
                               event.area.width,
                               event.area.height)
        self.context.clip()
        self.draw()

        return False

    def draw(self):
        def draw_tile_box(x, y):
            edges = tilenames.tileEdges(x, y, self.zoom_level)
            #print edges
            offsetlat = edges[0]-focus[0]
            offsetlong = edges[1]-focus[1]
            self.tileheight_deg = edges[2]-edges[0]

            self.context.rectangle(
                    offsetlong / self.tilewidth_deg * 256,
                    offsetlat / self.tileheight_deg * 256,
                    256,
                    256)
            self.context.fill()

            self.context.move_to(
                    offsetlong / self.tilewidth_deg * 256 + 128,
                    offsetlat / self.tileheight_deg * 256 + 128)
            self.context.set_source_rgb(0, 0, 0)
            self.context.set_font_size(12)
            self.context.show_text("%s, %s" % (x, y))

        (x, y, w, h) = self.get_allocation()
        focus = self.focus
        self.context.translate(w/2, h/2)
        x, y = tilenames.tileXY(focus[0], focus[1], self.zoom_level)
        self.tilewidth_deg = 360.0/tilenames.numTiles(self.zoom_level)
        #tileheight_deg = 180.0/tilenames.numTiles(self.zoom_level)
        #print self.focus
        #print x, y

        self.context.set_source_rgb(0, 0, 1)
        draw_tile_box(x, y)
        self.context.set_source_rgb(1, 0, 1)
        draw_tile_box(x-1, y)
        self.context.set_source_rgb(1, 0, 0)
        draw_tile_box(x+1, y)
        self.context.set_source_rgb(0, 0, 0)
        draw_tile_box(x, y+1)
        self.context.set_source_rgb(0, 1, 0)
        draw_tile_box(x, y-1)

        """
        # Hämtar alla tiles för en nivå
        level = self.mapdata.get_level(self.zoom_level)
        # Plockar ur de tiles vi söker från nivån
        tiles, cols, rows = level.get_tiles(self.mapdata.focus)
        self.cols = cols
        self.rows = rows

        self.bounds["min_longitude"] = tiles[0].bounds["min_longitude"]
        self.bounds["min_latitude"] = tiles[0].bounds["min_latitude"]
        self.bounds["max_longitude"] = tiles[-1].bounds["max_longitude"]
        self.bounds["max_latitude"] = tiles[-1].bounds["max_latitude"]

        # Ritar kartan
        for tile in tiles:
            #img = tile.get_picture()
            x, y = self.gps_to_pixel(tile.bounds["min_longitude"],
                                     tile.bounds["min_latitude"])
            tile.picture.draw(self.context, x, y)

        # Ritar ut eventuella objekt

        objects = self.mapdata.objects
            
        for item in objects:
            x, y = self.gps_to_pixel(objects[item].map_object_data.coords[0],
                                     objects[item].map_object_data.coords[1])
            if objects[item].map_object_data.name == config.client.name:
                objects[item].picture.is_me = True

            if x != 0 and y != 0:
                objects[item].picture.draw(self.context, x, y)
        """


    def gps_to_pixel(self, lon, lat):
        cols = self.cols
        rows = self.rows
        width = self.bounds["max_longitude"] - self.bounds["min_longitude"]
        height = self.bounds["min_latitude"] - self.bounds["max_latitude"]
      
        # Ger i procent var vi befinner oss på width och height
        where_lon = (lon - self.bounds["min_longitude"]) / width
        where_lat = (self.bounds["min_latitude"] - lat) / height
      
        # Ger i procent var focus befinner sig på width och height
        where_focus_lon = (self.mapdata.focus["longitude"] - \
                           self.bounds["min_longitude"]) / width
        where_focus_lat = (self.bounds["min_latitude"] - \
                           self.mapdata.focus["latitude"]) / height
      
        # Placerar origo i skärmens centrum
        rect = self.get_allocation()
        x = rect.width / 2.0
        y = rect.height / 2.0
      	
        # Räknar ut position:
        x += (where_lon - where_focus_lon) * (cols * 300.0)
        y += (where_lat - where_focus_lat) * (rows * 160.0)
      
        return [round(x), round(y)]
   
    def pixel_to_gps(self, movement_x, movement_y):
        # Hämtar alla tiles för en nivå
        level = self.mapdata.get_level(self.zoom_level)
        # Plockar ur de tiles vi söker från nivån
        tiles, cols, rows = level.get_tiles(self.mapdata.focus)

        # Gps per pixlar
        width = self.bounds["max_longitude"] - self.bounds["min_longitude"]
        height = self.bounds["min_latitude"] - self.bounds["max_latitude"]
        gps_per_pix_width = width / (cols * 300)
        gps_per_pix_height = height / (rows * 160)

        # Observera att kartans GPS-koordinatsystem börjar i vänstra nedre
        # hörnet, medan cairo börjar i vänstra övre hörnet! På grund av detta
        # inverterar vi värdet vi räknar fram så båda koordinatsystemen
        # överensstämmer.
        return [gps_per_pix_width * movement_x,
                gps_per_pix_height * movement_y]
        
    def set_clicked_coord(self, widget, event):
        r = self.get_allocation()        
        x, y, state = event.window.get_pointer()
        (lon,lat) = self.pixel_to_gps(x,y)        
        (m,n) = self.pixel_to_gps(r.width/2, r.height/2)
        self.gps_x = self.origin_position["longitude"] - m + lon
        self.gps_y = self.origin_position["latitude"] + n - lat

    def draw_sign(self):  
        poi_data = shared.data.POIData(self.gps_x, self.gps_y, "sign", datetime.now(), shared.data.POIType.flag)
        self.mapdata.objects["add-sign"] = POI(poi_data)
        self.queue_draw()
        
    def remove_sign(self):
        try:
            del self.mapdata.objects["add-sign"]
            self.queue_draw()  
        except:
            pass
    
    def get_clicked_bounds(self, event):
        '''
        Find out in which bounds to look for objects to mark.
        @param event: the click event.
        '''
        r = self.get_allocation()
        x, y, state = event.window.get_pointer()
        min_x = x-16
        max_x = x+16
        min_y = y-16
        max_y = y+16
        (lon,lat) = self.pixel_to_gps(min_x,min_y)
        (m,n) = self.pixel_to_gps(r.width/2, r.height/2)
        min_gps_x = self.origin_position["longitude"] - m + lon
        min_gps_y = self.origin_position["latitude"] + n - lat
        (lon,lat) = self.pixel_to_gps(max_x,max_y)
        (m,n) = self.pixel_to_gps(r.width/2, r.height/2)
        max_gps_x = self.origin_position["longitude"] - m + lon
        max_gps_y = self.origin_position["latitude"] + n - lat
        return (min_gps_x, min_gps_y, max_gps_x, max_gps_y)

    def draw_marked_object(self, widget, event):
        self.allow_movement = False
        # get the bounds to look for objects to mark in
        min_gps_x, min_gps_y, max_gps_x, max_gps_y = self.get_clicked_bounds(event)
        # check if any mapobject was clicked
        found = False # only mark one object
        for obj in self.mapdata.objects.values():
            data = obj.map_object_data
#            if data.name == config.client.name:
#                obj.picture.is_me = True
            if (data.coordx >= min_gps_x and 
                data.coordx <= max_gps_x and 
                data.coordy >= max_gps_y and
                data.coordy <= min_gps_y and 
                not data.name == "sign" and
                not found):
                if obj.picture.marked:
                    clicked_object = data
                    for a in self.db.get_all_alarms():
                        if data.id == a.poi.id:
                            clicked_object = a
                    for m in self.db.get_all_missions():
                        if data.id == m.poi.id:
                            clicked_object = m
                    # tell clientgui to show the correct view if something cool was clicked!
                    self.emit("object-clicked", clicked_object)
                else:
                    obj.picture.marked = True
                found = True
            else:
                obj.picture.marked = False
        self.queue_draw()
        if found:
            return False
        return True

    def draw_clicked_pos(self, widget, event):
        # if sign should be drawn, do it!
        if self.sign:
            self.draw_sign()
