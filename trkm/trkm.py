
import argparse
import activityio as aio
import sys
import gpxpy, gpxpy.gpx, gpxpy.gpxfield
from . import sequencer

class TrackMerge:

    def main():
        parser = argparse.ArgumentParser(description="GPS track merge")
        parser.add_argument("input_files", metavar="TRACK", nargs="*",
                            help="Input file to process. One of these formats: "
                            "Garmin TCX (.tcx), FIT or Flexible and Interoperable "
                            "Data Transfer (.fit), or GPS Exchange Format (.gpx)")
        parser.add_argument("output_file", metavar="OUTPUT.gpx",
                            help="The merged track is always in GPX format with "
                            "Garmin extensions")

        args = parser.parse_args()
        TrackMerge(args.input_files).merge(args.output_file)


    def __init__(self, input_files):
        self.sequencers = []
        for file_name in input_files:
            data = aio.read(file_name)
            seq = sequencer.AIO(file_name, data)
            ipt = sequencer.Interpolator(seq)
            self.sequencers.append(ipt)
        self.zip = sequencer.Zipper(*self.sequencers)


    def merge(self, output_file):
        gpx = gpxpy.gpx.GPX()
        gpx.creator = "TrackMerge"
        trk = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(trk)
        seg = gpxpy.gpx.GPXTrackSegment()
        trk.segments.append(seg)

        ptcnt = 0
        for t in self.zip:
            ptcnt += 1
            if ptcnt % 27 == 0:
                print("\r%8d" % ptcnt, end="")
                sys.stdout.flush()
            ext = {}
            if t.hr != None:
                ext['gpxtpx:hr'] = int(round(t.hr))
            if t.temperature != None:
                ext['gpxtpx:atemp'] = int(round(t.temperature))
            pt = gpxpy.gpx.GPXTrackPoint(t.lat, t.lon, t.alt, t.time)
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
        content = gpxpy.gpxfield.gpx_fields_to_xml(gpx, 'gpx', version=version,
                                                   custom_attributes=xml_attributes)
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + content.strip() + "\n"

        f = open(output_file, 'w')
        f.write(xml)

        f.close()
