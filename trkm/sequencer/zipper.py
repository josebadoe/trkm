import statistics
import numbers
import math

class ZipperWrapper:
    def __init__(self, name, points, bases=[]):
        self.name = name
        self.points = points
        self.bases = bases
        ptts = list(map(lambda pt: pt.time, filter(lambda pt: pt is not None, points)))
        if ptts:
            self.time = min(ptts)
        else:
            self.time = None

    def __getattr__(self, key):
        if key in self.__dict__:
            return self.__dict__[key]
        elif key in type(self).__dict__:
            return type(self).__dict__[key]
        else:
            l0 = []
            for (idx, p) in enumerate(self.points):
                if p:
                    # if key == 'distance':
                    #     print("WILL GET DIST")
                    v = getattr(p, key)
                    if (v is not None
                        and idx < len(self.bases)
                        and key in self.bases[idx]):
                        v += self.bases[idx][key]
                    if v is not None:
                        l0.append(v)
            if l0 and not isinstance(l0[0], numbers.Number):
                raise ValueError("%s is not a number in %s" % (key, self.name))
            l = list(filter(lambda v: not math.isnan(v), l0))
            # if key == 'distance':
            #     print("DIST: %r" % l)
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
        self.bases = []
        self.prev_found = [ False ] * len(interpolators)
        self._prev = None
        for i in range(0, len(interpolators)):
            self.bases.append(dict())

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
        for (idx, i) in enumerate(self.interpolators):
            if i == None:
                continue
            p, found = i.get(self.time, return_empty=False)
            first = found and not self.prev_found[idx]
            if first:
                self.prev_found[idx] = found
            if name:
                name += "-" + (p.name if found else "NONE")
            else:
                name = p.name if found else "NONE"
            r.append(p)
            if first and self._prev:
                self.bases[idx]['distance'] = self._prev.distance
                print("\nFirst and bases: %r" % self.bases)
        w = ZipperWrapper(name, r, self.bases)
        self._prev = w
        self.points.append(w)
