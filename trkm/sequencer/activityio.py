
import activityio as aio
import math

class AIOWrapper:
    def __init__(self, name, df, idx, last=None):
        self.name = name
        self._df = df
        self._t = df.ix[idx]
        self._last = last
        print("AIOWR %r, %r, %r, %r" % (idx, df.start + df.ix[idx].name, df.start, df.ix[idx].name))
    def hasattr(self, key):
        try:
            v = self.__getattr__(key)
            return True
        except AttributeError:
            return False

    def __getattr__(self, key):
        if key in self.__dict__:
            return self.__dict__[key]
        elif key in type(self).__dict__:
            if isinstance(type(self).__dict__[key], property):
                p = type(self).__dict__[key]
                return p.__get__(self, None)
            return type(self).__dict__[key]
        elif key in self._df.columns:
            return getattr(self._t, key)
        else:
            raise AttributeError(key)
    @property
    def hr(self):
        if 'hr' in self._df.columns:
            return self._t.hr
        elif 'value' in self._df.columns:
            # <HeartRateBpm xsi:type="HeartRateInBeatsPerMinute_t">
            #   <Value>99</Value>
            # </HeartRateBpm>
            return self._t.value
    @property
    def time(self):
        return self._df.start + self._t.name
    @property
    def distance(self):
        if 'dist' in self._df.columns:
            if math.isnan(self._t.dist):
                return None
            else:
                return self._t.dist
        else:
            return 0
    @property
    def temperature(self):
        try:
            return self.temp
        except AttributeError:
            return None

    @property
    def cadence(self):
        if 'cad' in self._df.columns:
            return self._t.cad
        else:
            return None

    @property
    def speed(self):
        if 'speed' in self._df.columns:
            return self._t.speed
        else:
            return None
            # """ returns km/h """
            # if self._last:
            #     dist = self.distance - self._last.distance
            #     tdelta = self.time - self._last.time
            # elif self._df.start:
            #     dist = self.distance
            #     tdelta = self.time - self._df.start
            #     print("Nyerga", self._df.start, tdelta, dist)
            #     return -99.9
            # else:
            #     return 0.0
            # if tdelta.seconds == 0:
            #     return 0
            # else:
            #     return dist * 3600 / tdelta.seconds / 1000


class AIO:
    def __init__(self, name, df):
        self.name = name
        self._df = df

    def all(self):
        last = None
        for idx in range(1, self._df.shape[0]):
            v = AIOWrapper(self.name, self._df, idx, last)
            if last and v.time < last.time:
                continue
            last = v
            yield v

    def __iter__(self):
        self._g = self.all()
        return self

    def __next__(self):
        return next(self._g)
