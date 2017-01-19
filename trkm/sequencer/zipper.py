import statistics
import numbers
import math

class ZipperWrapper:
    def __init__(self, name, points):
        self.name = name
        self.points = points
        self.time = points[0].time

    def __getattr__(self, key):
        if key in self.__dict__:
            return self.__dict__[key]
        elif key in type(self).__dict__:
            return type(self).__dict__[key]
        else:
            l0 = list(filter(lambda v: v != None,
                             map(lambda p: getattr(p, key),
                                 self.points)))
            if l0 and not isinstance(l0[0], numbers.Number):
                raise ValueError("%s is not a number in %s" % (key, self.name))
            l = list(filter(lambda v: not math.isnan(v), l0))
            if l:
                v = statistics.mean(l)
                setattr(self, key, v)
            else:
                v = None
            return v


class Zipper:
    def __init__(self, *interpolators):
        self.interpolators = interpolators
        self.time = None
        self.points = []

    def __getitem__(self, k):
        try:
            while len(self.points) <= k:
                self.prep_next()
        except StopIteration:
            pass
        return self.points[k]

    def next_entry(self):
        if self.time == None:
            t = None
            for (idx, i) in enumerate(self.interpolators):
                if i == None:
                    continue
                p = i.first()
                if p == None:
                    self.interpolators[idx] = None
                if t == None or p.time < t:
                    t = p.time
            self.time = t
            #print("First:", self.time)
        else:
            t = None
            for i in self.interpolators:
                if i == None:
                    continue
                p = i.neighbor(i[self.time], 1)
                if p and (t == None or p.time < t):
                    t = p.time
            self.time = t
            #print("Next:", self.time)
        return self.time


    def prep_next(self):
        if not self.next_entry():
            raise StopIteration
        r = []
        name = ""
        for i in self.interpolators:
            if i == None:
                continue
            p = i[self.time]
            if name:
                name += "-" + p.name
            else:
                name = p.name
            r.append(p)
        self.points.append(ZipperWrapper(name, r))
