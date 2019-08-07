import gpxdata
import math
from .zipper import ZipperWrapper

class InterpolatorPointWrapper:
    def __init__(self, point, lst, name=None, time=None, real=True):
        self.point = point
        self.lst = lst
        self.name = name or point.name
        self.time = time or point.time
        self.collected = {}
        self.real = real

    def __getattr__(self, key):
        if self.real:
            v = self.getattr_local(key)
            if v is not None:
                v0 = (self, v)
            else:
                v0 = None
            v1 = None
        else:
            v0 = self.getattr(key, direction=-1)
        if v0 and v0[1] == None:
            v0 = None
        if v0 and v0[0] == self:
            return v0[1]
        else:
            v1 = self.getattr(key, direction=1)
            if v1 and v1[1] == None:
                v1 = None
        if v0 and v1:
            tdelta_t = (v1[0].time - v0[0].time).seconds
            tdelta_c = (self.time - v0[0].time).seconds
            if False and key in ['lat', 'lon']:
                ratio = tdelta_c / tdelta_t
                (lat, lon) = gpxdata.Util.interpolate(v0[0].lat, v0[0].lon,
                                                      v1[0].lat, v1[0].lon,
                                                      ratio)
                if key == 'lat':
                    return lat
                else:
                    return lon
            else:
                v = v0[1] + (v1[1] - v0[1]) / tdelta_t * tdelta_c
                return v
        elif v0:
            return v0[1]
        elif v1:
            return v1[1]
        else:
            return None

    def getattr(self, key, direction=0, force=False):
        if (key, direction) in self.collected:
            return self.collected[(key, direction)]
        if force:
            v = None
        else:
            v = self.getattr_local(key)
        if v != None:
            self.collected[(key, direction)] = (self, v)
            return (self, v)
        elif direction != 0:
            pt = self.lst.neighbor(self, direction)
            while pt != None:
                v = pt.getattr(key)
                if v != None:
                    self.collected[(key, direction)] = v
                    return v
                else:
                    pt = self.lst.neighbor(pt, direction)
        self.collected[(key, direction)] = (self, None)
        return None

    def getattr_local(self, key):
        if key in self.__dict__:
            v = self.__dict__[key]
        elif key in type(self).__dict__:
            v = type(self).__dict__[key]
        elif self.point != None:
            v = getattr(self.point, key)
            if v != None and not math.isnan(v):
                setattr(self, key, v)
            else:
                v = None
        else:
            v = None
        return v


class Deduplicator(ZipperWrapper):
    def __init__(self, name, points, lst, time=None):
        super().__init__(name, points)
        self.lst = lst
        self.time = time or points[0].time
        self.collected = {}

    def getattr(self, key, direction=0, force=False):
        if (key, direction) in self.collected:
            return self.collected[(key, direction)]
        if force:
            v = None
        else:
            v = getattr(self, key)
        if v != None:
            self.collected[(key, direction)] = (self, v)
            return (self, v)
        elif direction != 0:
            pt = self.lst.neighbor(self, direction)
            while pt != None:
                v = pt.getattr(key)
                if v != None:
                    self.collected[(key, direction)] = v
                    return v
                else:
                    pt = self.lst.neighbor(pt, direction)
        self.collected[(key, direction)] = (self, None)
        return None


class Interpolator:
    def __init__(self, sequencer):
        self.by_time_idx = dict()
        self.last_used_time = None
        self.last_used_time_idx = None
        self.points = []
        self.sequencer = iter(sequencer)
        #self.name = sequencer.name + ':ipt'

    def __getitem__(self, k):
        return self.get(k)[0]

    def get(self, k, return_empty=True):
        """Returns (point, found_flag)
        """
        if type(k) == int:
            try:
                while len(self.points) <= k:
                    self.load_next()
            except StopIteration:
                pass
            return (self.points[k], True)
        else: # timestamp
            if k in self.by_time_idx:
                return (self.points[self.by_time_idx[k]], True)
            if self.last_used_time and self.last_used_time <= k:
                i = self.last_used_time_idx
            else:
                i = 0
            first_match = None
            # print("Getting %s" % (k,))
            while True:
                if i >= len(self.points) or self.points[i].time > k:
                    if first_match and first_match == i - 1:
                        # print("  true:A %s" % (k, ))
                        return (self.points[first_match], True)
                    elif first_match is not None:
                        # repeated timestamps
                        pt = Deduplicator("ddp", self.points[first_match:i], self, time=k)
                        self.points[first_match:i] = [pt]
                        self.last_used_time = k
                        self.last_used_time_idx = i
                        # print("  true:B %s" % (k, ))
                        return (pt, True)
                    else:
                        if return_empty:
                            pt = InterpolatorPointWrapper(None, self, name=self.name, time=k, real=False)
                            self.points[i:i] = [pt]
                        else:
                            pt = None
                        # #print("Inserting %r at %r in %s" % (pt.time, i, self.name))
                        # print("  false:C %s, %r" % (k, pt.distance if pt else None))
                        return (pt, False)
                elif self.points[i].time == k:
                    self.by_time_idx[self.points[i].time] = i
                    if first_match == None:
                        first_match = i
                i += 1

    def load_next(self):
        if self.sequencer == None:
            raise StopIteration
        try:
            pt = next(self.sequencer)
            self.name = pt.name + ':ipt'
            #print("JAAAA %r" % pt.time)
        except StopIteration:
            self.sequencer = None
            raise
        if self.points and self.points[-1].time == pt.time:
            self.points[-1] = InterpolatorPointWrapper(pt, self)
        else:
            self.points.append(InterpolatorPointWrapper(pt, self))

    def first(self):
        return self[0]

    def neighbor(self, point, step=1):
        for i in range(0, len(self.points)):
            if self.points[i] == point:
                if i + step < 0:
                    return None
                try:
                    return self[i+step]
                except IndexError:
                    return None
        return None
