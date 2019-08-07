import configparser
import sys
from datetime import datetime, timedelta
import statistics, random

class RecordWrapper:
    def __init__(self, name, time, idx, data):
        self.name = name
        self.time = time
        self._idx = idx
        self._data = data

    @property
    def hr(self):
        return self._data['hr']

    @property
    def distance(self):
        return self._data['total_distance']

    @property
    def speed(self):
        return self._data['speed']

    @property
    def cadence(self):
        return self._data['cadence']

    @property
    def temperature(self):
        return None


class Fragment:
    def __init__(self, length, start, end, min=None, max=None, starting_at=None):
        self._length = length
        if start < 0:
            raise Exception("Start %f" % start)
        if end < 0:
            raise Exception("End %f" % end)
        self.starting_at = starting_at or 0
        self._start = start
        self._end = end
        self._min = min
        self._max = max
        self._parts = None
        self._step = None

    def init_cache(self):
        if self._parts is None:
            if self._step is None:
                self._step = (self._end - self._start) / len(self)

    def __getitem__(self, at):
        if at < 0:
            at += len(self)

        if self._parts is None:
            self.init_cache()
            v = self._start + self._step * at
            if self._min is not None:
                v = max(v, self._min)
            if self._max is not None:
                v = min(v, self._max)
            return v

        (elt, at, _) = self.element_at(at)
        if elt is not None:
            return elt[at]

        return self[-1]

    def element_at(self, at):
        if self._parts is None:
            return (None, None, None)
        for (i, elt) in enumerate(self._parts):
            if at < len(elt):
                return (elt, at, i)
            else:
                at -= len(elt)
        return (None, None, None)

    def __len__(self):
        if self._parts:
            return sum(map(len, self._parts))
        else:
            return self._length


    def divide(self, at, displacement=0, absolute=None):
        if at == 0:
            if absolute is not None:
                self._start == absolute
            else:
                self._start += displacement
        elif at == self._length:
            if absolute is not None:
                self._end == absolute
            else:
                self._end += displacement
        elif self._parts is None:
            if absolute is not None:
                p = absolute
            else:
                step = (self._end - self._start) / len(self)
                p = self._start + step * at + displacement
            self._parts = [
                Fragment(at, self._start, p,
                         min=self._min, max=self._max,
                         starting_at = self.starting_at),
                Fragment(self._length - at, p, self._end,
                         min=self._min, max=self._max,
                         starting_at = self.starting_at + at)
            ]
        else:
            (elt, at, i) = self.element_at(at)
            if elt and at != 0:
                elt.divide(at, displacement, absolute)
                # if at == 0 and i > 0:
                #     self._parts[i-1].divide(len(self._parts[i-1]), displacement, absolute)

    def force(self, starting_at, length, value):
        if starting_at > self._length:
            pass
        elif starting_at <= 0 and length >= self._length:
            self._start = value
            self._end = value
            self._parts = None
            self._step = None
        else:
            length = min(length, self._length - starting_at)
            (s_elt, s_at, _) = self.element_at(starting_at)
            if s_elt is None:
                self.divide(starting_at)
            (e_elt, e_at, _) = self.element_at(starting_at + length)
            if e_elt is None:
                self.divide(starting_at + length)

            for elt in self._parts:
                if starting_at < len(elt):
                    l = min(length, len(elt) - starting_at)
                    elt.force(starting_at, l, 0)
                    if l >= length:
                        break
                    length -= l
                    starting_at = 0
                else:
                    starting_at -= len(elt)



    def __repr__(self):
        if self._parts is None:
            return ("Fragment[%r:%ds, %.2f, %.2f]"
                    % (self.starting_at, self._length, self._start, self._end))
        else:
            return ("Fragments %r:%ds[%s]"
                    % (self.starting_at, len(self), ", ".join(map(repr, self._parts))))



class Faker:
    def __init__(self, name):
        self.name = name
        self.config = configparser.ConfigParser(interpolation=None, strict=True,
                                                empty_lines_in_values=True)
        self.config.read(self.name)

    def parse_range(self, s, parser=int):
        l = list(map(parser, s.split(',')))
        return (l[0], l[-1])

    def error(self, msg):
        print(msg)
        sys.exit(1)

    def displacement(self, val, lo, hi):
        return random.triangular(lo, hi, val) - val

    def displace_midpoint(self, route, start, end, bounds, displacement_reduction):
        if end - start < self.min_frag_len:
            return
        at = int(random.triangular(start, end, (start + end) / 2))
        v = route[at]
        lo = v - bounds
        hi = v + bounds
        route.divide(at, self.displacement(v, lo, hi))
        new_bounds = bounds * displacement_reduction
        self.displace_midpoint(route, start, at, new_bounds, displacement_reduction)
        self.displace_midpoint(route, at, end, new_bounds, displacement_reduction)

    def add_pause(self, route, at, lead_in, length, lead_out):
        start = max(0, at - int(length / 2))
        end = min(len(route), start + length)

        p1 = start
        p2 = end

        leadin_start = max(0, start - lead_in)
        leadout_end = min(end + lead_out, len(route))

        x_start_v = route[leadin_start]
        x_end_v = route[leadout_end]

        if start > 0:
            p1 = leadin_start
            route.divide(leadin_start, absolute=x_start_v)

        if end < len(route):
            p2 = leadout_end
            route.divide(leadout_end, absolute=x_end_v)

        if start > 0:
            route.divide(start, 0)
        else:
            leadin_start = None

        if end < len(route):
            route.divide(end, absolute=0)
            route.divide(leadout_end)
        else:
            leadout_end = None

        # for i in range(p1, p2+1):
        #     print("Pause of %d going at %d: %r" % (length, i, route[i]))
        route.force(start, length, 0)
        # for i in range(p1, p2+1):
        #     print("Pause of %d went at %d: %r" % (length, i, route[i]))

        return route


    def print_route(self, route):
        for n in range(0, len(route)):
            print("%5d: %.2f" % (n, route[n]))

    # def squash(self, route, correction_factor, c_med, c_min, c_max, w_med, w_min, w_max):
    #     # keeping shape
    #     f_lo = (w_med - w_min) / ((c_med - c_min) * correction_factor)
    #     f_hi = (w_max - w_med) / ((c_max - c_med) * correction_factor)
    #     for (i, v) in enumerate(route):
    #         if v < c_med:
    #             route[i] = c_med - ((c_med - v) * f_lo)
    #         elif v > c_med:
    #             route[i] = c_med + ((v - c_med) * f_hi)
    #     return route


    def route(self, length, avg_speed, speed_range, pauses=[]):
        base = 1000
        displacement_bounds = 500
        decay_power = 1
        displacement_reduction = 1 / (2 ** decay_power)
        hi = base + displacement_bounds
        lo = base - displacement_bounds
        start = 1000 + self.displacement(1000, lo, hi)
        end = 1000 + self.displacement(1000, lo, hi)
        route = Fragment(length, start, end)
        self.displace_midpoint(route, 0, length,
                               displacement_bounds,
                               displacement_reduction)

        pp = sorted(map(lambda _: int(random.weibullvariate(length, 1.5)), pauses))
        #print("BEFORE-APU: %r" % route)
        for (i, p) in enumerate(pp):
            self.add_pause(route, p, length=pauses[i], lead_in=2, lead_out=2)
        #print("AFTER-APU: %r" % route)



        r0 = list(map(lambda i: route[i], range(0, length)))
        min_v = min(r0)
        max_v = max(r0)
        m = statistics.mean(r0)

        f = avg_speed / m
        # if min_v * f < speed_range[0] or max_v * f > speed_range[1]:
        #     r0 = self.squash(r0, f, m, min_v, max_v, avg_speed, *speed_range)
        #     m2 = statistics.mean(r0)
        #     print("Squashed, m0: %r, m2: %r" % (m, m2))
        #r = list(map(lambda s: min(speed_range[1], max(speed_range[0], s * f)), r0))
        #mr = statistics.mean(r)
        #print("Cut, m0: %r, m2: %r" % (m, mr))


        return [ min(max(s * f, speed_range[0]),
                     speed_range[1]) if s
                 else 0
                 for s in r0 ]



    def all(self):
        cfg = self.config['training']
        cadence_range = self.parse_range(cfg['cadence'])
        speed_range = self.parse_range(cfg['speed'], parser=float)
        time_range = self.parse_range(cfg['time'],
                                      parser=(lambda s:
                                              datetime.strptime(s.strip(),
                                                                '%Y-%m-%d %H:%M:%S%z')))
        base_hr = int(cfg['base_heart_rate'])
        hr_range = self.parse_range(cfg['heart_rate'])
        hr_effect_lasting = int(cfg['hr_effect_lasting'])
        hr_effect_delay = int(cfg['hr_effect_delay'])
        hr_factor0 = (hr_range[0] - base_hr) / (cadence_range[0])
        hr_factor = (hr_range[1] - hr_range[0]) / (cadence_range[1] - cadence_range[0])

        pauses = list(map(int, cfg['pauses'].split(',')))
        # from km to meters
        total_distance = float(cfg['distance']) * 1000

        total_time = (time_range[1] - time_range[0]).seconds
        avg_speed = (total_distance / 1000) / (total_time / 3600)

        cadence_acc_factor = (
            (cadence_range[1] - cadence_range[0])
            / (speed_range[1] - speed_range[0]))

        if not speed_range[0] <= avg_speed <= speed_range[1]:
            self.error("Required average speed %f is not in permitted range %f - %f"
                       % (avg_speed, *speed_range))

        self.min_frag_len = 5 # seconds

        route = self.route(total_time, avg_speed, speed_range, pauses)

        distance_so_far = 0
        hr_effect = hr_effect_delay + hr_effect_lasting
        cadence_log = [ 0 ] * hr_effect

        prev_t = 0
        for t in range(0, total_time):
            speed = route[t]
            dist = speed * 1000 / 3600 * (t - prev_t)
            cadence = (cadence_range[0]
                       + (speed - speed_range[0]) * cadence_acc_factor)
            cadence_log = cadence_log[1:] + [ cadence ]
            cm = statistics.mean(cadence_log[0:hr_effect_lasting])
            if cm >= cadence_range[0]:
                hr = hr_range[0] + (cm - cadence_range[0]) * hr_factor
            else:
                hr = base_hr + hr_factor0 * cm
            distance_so_far += dist
            hr = round(hr)
            cadence = round(cadence)
            # print("At %d, speed: %.2f, dist: %.2f, total dist: %.2f, cadence: %.2f, cm: %.2f, hr: %.2f"
            #       % (t, speed, dist, distance_so_far, cadence, cm, hr))

            data = {
                'hr': hr,
                'total_distance': distance_so_far,
                'speed': speed,
                'cadence': cadence
            }
            prev_t = t
            yield RecordWrapper(self.name,
                                time_range[0] + timedelta(seconds=t), t, data)


    def __iter__(self):
        self._g = self.all()
        return self

    def __next__(self):
        return next(self._g)
