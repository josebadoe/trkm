
import argparse
import activityio as aio
import sys, os
import gpxpy, gpxpy.gpx
from gpxpy import gpxfield
from . import sequencer
import math
import datetime

# print("11 fields: %r" % (gpxpy.gpx.GPXTrackPoint.gpx_11_fields,))
# gpxpy.gpx.GPXTrackPoint.gpx_11_fields = [
#     *gpxpy.gpx.GPXTrackPoint.gpx_11_fields,
#     gpxfield.GPXField('speed', type=gpxfield.FLOAT_TYPE)
# ]

class GPXWriter:
    def __init__(self, sequencer, options, multiplier=1):
        self.seq = sequencer
        self.options = options
        self.multiplier = multiplier

    def write(self, output_file):
        gpx = gpxpy.gpx.GPX()
        gpx.creator = "TrackMerge"
        trk = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(trk)
        seg = gpxpy.gpx.GPXTrackSegment()
        trk.segments.append(seg)

        ptcnt = 0
        for t in self.seq:
            ptcnt += 1
            if self.options.progress and ptcnt % 27 == 0:
                print("\r%8d" % ptcnt, end="")
                sys.stdout.flush()
            ext = {}
            lat = getattr(t, 'lat', None)
            lon = getattr(t, 'lon', None)
            alt = getattr(t, 'alt', None)
            spd = getattr(t, 'speed', None)
            if spd:
                spd = spd * self.multiplier
            pt = gpxpy.gpx.GPXTrackPoint(latitude=lat,
                                         longitude=lon,
                                         elevation=alt,
                                         time=t.time,
                                         speed=spd)
            if t.hr != None:
                ext['gpxtpx:hr'] = int(round(t.hr))
            if t.cadence != None:
                ext['gpxtpx:cad'] = int(round(t.cadence))
            if t.temperature != None:
                ext['gpxtpx:atemp'] = int(round(t.temperature))
            if spd != None:
                ext['gpxtpx:speed'] = spd
            if ext:
                pt.extensions = { 'gpxtpx:TrackPointExtension': self.dict_to_xml(ext) }
            seg.points.append(pt)
        print("%8d" % ptcnt)

        self.write_gpx(output_file, gpx)


    def dict_to_xml(self, tab):
        r = ""
        for k in sorted(tab.keys(), reverse=True):
            v = tab[k]
        # for (k, v) in tab.items():
            if type(v) == dict:
                s = dict_to_xml(v)
            else:
                s = str(v)
            r += "<%s>%s</%s>" % (k, s, k)
        return r


    def write_gpx(self, output_file, gpx):
        version='1.1'
        v = '1/1'
        xml_attributes = {
            'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'xmlns': 'http://www.topografix.com/GPX/%s' % v,
            'xmlns:gpxtpx': 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1',
            'xsi:schemaLocation': 'http://www.topografix.com/GPX/%s http://www.topografix.com/GPX/%s/gpx.xsd' % (v, v) }
        #gpxfield.GPXField('speed', type=gpxfield.FLOAT_TYPE) ]
        content = gpxfield.gpx_fields_to_xml(gpx, 'gpx', version=version,
                                             custom_attributes=xml_attributes)
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + content.strip() + "\n"

        f = open(output_file, 'w')
        f.write(xml)

        f.close()


class TCXWriter:
    def __init__(self, sequencer, options, multiplier=1):
        self.seq = sequencer
        self.options = options
        self.multiplier = multiplier

    def write(self, output_file):
        tcx = None
        lap = None
        trk = None
        start_time = None
        end_time = None
        total_distance = 0
        max_speed = 0
        prev_time = None
        ptcnt = 0
        for t in self.seq:
            if t.time is None:
                continue
            ptcnt += 1
            if self.options.progress and ptcnt % 27 == 0:
                #print("\r%8d - %8.2f" % (ptcnt, t.distance), end="")
                print(t.time)
                sys.stdout.flush()
            if tcx is None:
                (tcx, lap, trk) = self.setup_tcx(t.time)
                start_time = t.time

            prev_time = end_time
            end_time = t.time
            if t.distance:
                total_distance = t.distance

            trkpt = tcx.createElement("Trackpoint")
            trk.appendChild(trkpt)
            tm = t.time - (t.time.utcoffset() or datetime.timedelta())
            self.add_text_elt(tcx, trkpt, "Time",
                              tm.strftime("%Y-%m-%dT%H:%M:%SZ"))

            lat = getattr(t, 'lat', None)
            lon = getattr(t, 'lon', None)
            alt = getattr(t, 'alt', None)
            if lat and lon:
                pos = tcx.createElement("Position")
                self.add_text_elt(tcx, pos, "LatitudeDegrees", lat)
                self.add_text_elt(tcx, pos, "LongitudeDegrees", lon)
                trkpt.appendChild(pos)
            if alt:
                self.add_text_elt(tcx, trkpt, "AltitudeMeters", "55.8")


            if t.hr != None:
                hr = tcx.createElement("HeartRateBpm")
                trkpt.appendChild(hr)
                self.add_text_elt(tcx, hr, "Value", int(t.hr))
            if t.cadence != None:
                self.add_text_elt(tcx, trkpt, "Cadence", int(round(t.cadence)))
            self.add_text_elt(tcx, trkpt,
                              "DistanceMeters",
                              "%.2f" % (total_distance * self.multiplier))

            spd = getattr(t, 'speed', None)
            if spd is not None:
                max_speed = max(spd * self.multiplier, max_speed)
                ext = tcx.createElement("Extensions")
                trkpt.appendChild(ext)
                tpx = tcx.createElement("TPX")
                tpx.setAttribute("xmlns",
                                 "http://www.garmin.com/xmlschemas/ActivityExtension/v2")
                ext.appendChild(tpx)
                self.add_text_elt(tcx, tpx, "Speed", round(spd, 1))
                #       <Watts>0</Watts>


        self.add_text_elt(tcx, lap, "DistanceMeters",
                          "%.2f" % (total_distance * self.multiplier))
        self.add_text_elt(tcx, lap, "Calories", 0)
        self.add_text_elt(tcx, lap, "TriggerMethod", "Manual")
        #self.add_text_elt(tcx, lap, "MaximumSpeed", max_speed)
        # <AverageHeartRateBpm>
        #  <Value>158</Value>
        # </AverageHeartRateBpm>
        # <MaximumHeartRateBpm>
        #  <Value>195</Value>
        # </MaximumHeartRateBpm>
        # <Intensity>Active</Intensity>
        # <Cadence>61</Cadence>
        # <TriggerMethod>Manual</TriggerMethod>
        with open(output_file, "wt") as writer:
            tcx.writexml(writer, newl="\n", addindent=" ", encoding="UTF-8")

        # gpx.creator = "TrackMerge"
        # trk = gpxpy.gpx.GPXTrack()
        # gpx.tracks.append(trk)
        # seg = gpxpy.gpx.GPXTrackSegment()
        # trk.segments.append(seg)

        # ptcnt = 0
        # for t in self.zip:
        #     ptcnt += 1
        #     if ptcnt % 27 == 0:
        #         print("\r%8d" % ptcnt, end="")
        #         sys.stdout.flush()
        #     ext = {}
        #     lat = getattr(t, 'lat', None)
        #     lon = getattr(t, 'lon', None)
        #     alt = getattr(t, 'alt', None)
        #     spd = getattr(t, 'speed', None)
        #     if spd:
        #         print(spd, spd * math.pi)
        #         spd = spd * math.pi
        #     pt = gpxpy.gpx.GPXTrackPoint(latitude=lat,
        #                                  longitude=lon,
        #                                  elevation=alt,
        #                                  time=t.time,
        #                                  speed=spd)
        #     if t.hr != None:
        #         ext['gpxtpx:hr'] = int(round(t.hr))
        #     if t.cad != None:
        #         ext['gpxtpx:cad'] = int(round(t.cad))
        #     if t.temperature != None:
        #         ext['gpxtpx:atemp'] = int(round(t.temperature))
        #     if spd != None:
        #         ext['gpxtpx:speed'] = spd
        #     if ext:
        #         pt.extensions = { 'gpxtpx:TrackPointExtension': self.dict_to_xml(ext) }
        #     seg.points.append(pt)
        # print("%8d" % ptcnt)

        # self.write_gpx(output_file, gpx)

    def add_text_elt(self, doc, parent, name, value):
        elt = doc.createElement(name)
        elt.appendChild(doc.createTextNode(str(value)))
        parent.appendChild(elt)
        return elt

    def setup_tcx(self, start_time):
        from xml.dom.minidom import Document
        start_time -= start_time.utcoffset() or datetime.timedelta()
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        tcx = Document()
        root = tcx.createElement("TrainingCenterDatabase")
        root.setAttribute(
            "xsi:schemaLocation",
            "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd")
        root.setAttribute(
            "xmlns:ns5",
            "http://www.garmin.com/xmlschemas/ActivityGoals/v1")
        root.setAttribute(
            "xmlns:ns3",
            "http://www.garmin.com/xmlschemas/ActivityExtension/v2")
        root.setAttribute(
            "xmlns:ns2",
            "http://www.garmin.com/xmlschemas/UserProfile/v2")
        root.setAttribute(
            "xmlns",
            "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2")
        root.setAttribute(
            "xmlns:xsi",
            "http://www.w3.org/2001/XMLSchema-instance")
        # root.setAttribute("xmlns:ns2", "http://www.garmin.com/xmlschemas/UserProfile/v2")
        # root.setAttribute("xmlns:ns3",
        #                   "http://www.garmin.com/xmlschemas/ActivityExtension/v2")
        # root.setAttribute("xmlns:ns5", "http://www.garmin.com/xmlm")
        tcx.appendChild(root)
        acts = tcx.createElement("Activities")
        root.appendChild(acts)
        act = tcx.createElement("Activity")
        act.setAttribute("Sport", "Biking")
        acts.appendChild(act)

        self.add_text_elt(tcx, act, "Id", start_time_str)

        lap = tcx.createElement("Lap")
        lap.setAttribute("StartTime", start_time_str)
        act.appendChild(lap)

        trk = tcx.createElement("Track")
        lap.appendChild(trk)

        return (tcx, lap, trk)


class Options:
    def __init__(self, lst):
        self.opts = dict()
        for e in lst:
            parts = e.split('=', 1)
            name = parts[0]
            if len(parts) > 1:
                value = parts[1]
            else:
                value = "1"
            self.opts[name] = value
    def get_int(self, name):
        s = self.opts.get(name, None)
        if s is not None:
            return int(s)
        else:
            return 0
    def get_float(self, name):
        s = self.opts.get(name, None)
        if s is not None:
            return float(s)
        else:
            return 0
    def get_bool(self, name):
        s = self.opts.get(name, None)
        if s is not None:
            return not not int(s)
        else:
            return False


class TrackMerge:

    def main():
        parser = argparse.ArgumentParser(description="GPS track merge")
        parser.add_argument("-f", "--format", metavar="FORMAT",
                            help="Output file format, may be GPX or TCX",
                            dest="format", default="GPX")
        parser.add_argument("-m", "--multiplier", metavar="N",
                            help="Constant to multiply speed and distance values with, "
                            "like PI or a floating point value, for cases like when you "
                            "used diameter in place of circumference on roller training.",
                            dest="multiplier", default=1)
        parser.add_argument("-c", "--cleanup",
                            help="Check and clean up common some data errors",
                            dest="cleanup", default=False, action="store_true")
        parser.add_argument("-o", "--cleanup-option", metavar="NAME=VALUE",
                            help="Set cleanup options: MaxSpeed=<kmh>",
                            dest="cleanup_opts", action="append")
        parser.add_argument("-v", "--verbose",
                            help="Show processing details",
                            dest="verbose", default=False, action="store_true")
        parser.add_argument("-p", "--progress",
                            help="Show progress info",
                            dest="progress", default=False, action="store_true")
        parser.add_argument("input_files", metavar="TRACK", nargs="*",
                            help="Input file to process. One of these formats: "
                            "Garmin TCX (.tcx), FIT or Flexible and Interoperable "
                            "Data Transfer (.fit), or GPS Exchange Format (.gpx)")
        parser.add_argument("output_file", metavar="OUTPUT.gpx",
                            help="The merged track is always in GPX format with "
                            "Garmin extensions")

        args = parser.parse_args()
        if args.format.upper() == "GPX":
            writer = GPXWriter
        elif args.format.upper() == "TCX":
            writer = TCXWriter
        else:
            raise Exception("Format '%s' not recognized" % args.format)
        if args.multiplier == "PI":
            m = math.pi
        else:
            m = float(args.multiplier)

        TrackMerge(args, m).merge(writer, args.output_file)


    def __init__(self, options, multiplier=1):
        self.sequencers = []
        self.options = options
        self.multiplier = multiplier
        for file_name in self.options.input_files:
            if os.path.splitext(file_name)[1] == '.ini':
                seq = sequencer.Faker(file_name)
            else:
                data = aio.read(file_name)
                seq = sequencer.AIO(file_name, data)
            ipt = sequencer.Interpolator(seq)
            self.sequencers.append(ipt)
        self.seq = sequencer.Zipper(*self.sequencers)
        if options.cleanup:
            if self.options.verbose:
                cleanup_opts = Options(self.options.cleanup_opts + ["verbose=1"])
            else:
                cleanup_opts = Options(self.options.cleanup_opts)
            self.seq = sequencer.Cleanup(self.seq, cleanup_opts)


    def merge(self, writer, output_file=None):
        if not output_file:
            output_file = self.options.output_file
        writer(self.seq, self.options, multiplier=self.multiplier).write(output_file)
