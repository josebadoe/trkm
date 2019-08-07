import configparser
import sys
from datetime import datetime, timedelta
import statistics, random


# class RecordWrapper:
#     def __init__(self, name, time, idx, data):
#         self.name = name
#         self.time = time
#         self._idx = idx
#         self._data = data

#     @property
#     def hr(self):
#         return self._data['hr']

#     @property
#     def distance(self):
#         return self._data['total_distance']

#     @property
#     def speed(self):
#         return self._data['speed']

#     @property
#     def cadence(self):
#         return self._data['cadence']

#     @property
#     def temperature(self):
#         return None


class RecordWrapper:
    def wrap(rec):
        if isinstance(rec, RecordWrapper):
            return rec
        else:
            return RecordWrapper(rec)

    def __init__(self, rec):
        object.__setattr__(self, 'rec', rec)
        object.__setattr__(self, 'override', dict())

    def __getattr__(self, key):
        if key in self.override:
            return self.override[key]
        else:
            return getattr(self.rec, key)

    def __setattr__(self, key, value):
        self.override[key] = value


class Cleanup:
    def __init__(self, sequencer, options):
        self.options = options
        self.sequencer = sequencer
        self.max_speed = options.get_float("MaxSpeed") or 50

    def __iter__(self):
        #self.seq = iter(self.sequencer)
        self.seq = list(self.sequencer)
        self.idx = 0
        self.last_r = None
        self.distance_diff_accumulated = 0
        while self.idx < len(self.seq):
            self.seq[self.idx] = self.prepare(self.seq[self.idx])
            self.idx += 1
        self.smooth()
        self.cleanup()
        return iter(self.seq)

    # def __next__(self):
    #     while self.idx < len(self.seq):
    #         r = self.cleanup(self.seq[self.idx])
    #         self.seq[self.idx] = r
    #         self.idx += 1
    #         return r
    #     raise StopIteration

        # r = next(self.seq)
        # r = self.cleanup(r)
        # return r

    def active_time_str(self, i):
        active_time = self.seq[i].time - self.seq[0].time
        return ("%02d:%02d:%02d"
                % (active_time.seconds // 3600,
                   (active_time.seconds % 3600) // 60,
                   active_time.seconds % 60))


    def prepare(self, r):
        r = RecordWrapper.wrap(r)
        return r

    def recorded_speed(self, i):
        r = self.seq[i]
        return r.speed * 60 * 60 / 1000

    def set_recorded_speed(self, i, spd):
        self.seq[i].speed = spd * 1000 / 3600

    def time_delta(self, i):
        if i == 0:
            return 0
        last_r = self.seq[i-1]
        r = self.seq[i]
        td = r.time - last_r.time
        return td.total_seconds()

    def delta_dist(self, i):
        if i >= len(self.seq):
            return 0
        elif i > 0:
            return self[i].distance - self[i-1].distance
        else:
            return self[i].distance

    def calculated_speed(self, i):
        if i <= 0:
            return 0
        last_r = self.seq[i-1]
        r = self.seq[i]

        a = last_r.distance
        b = r.distance
        td = r.time - last_r.time

        return (b - a) / td.total_seconds() * 60 * 60 / 1000


    def next_ri(self, i):
        if i+1 < len(self.seq):
            return i+1
        else:
            return None

    def cadence(self, i):
        return self.seq[i].cadence

    def avg_spd_by_cad(self, start, cnt_before, cnt_after):
        lst = []
        i = start
        n = 0
        while i >= 0 and n < cnt_before:
            if self[i].cadence != 0:
                spd = self.calculated_speed(i)
                if spd > 0 and spd <= self.max_speed:
                    lst.append(spd / self[i].cadence)
                    n += 1
            i -= 1
        i = start+1
        n = 0
        while i < len(self.seq) and n < cnt_after:
            if self[i].cadence != 0:
                spd = self.calculated_speed(i)
                if spd <= self.max_speed:
                    lst.append(spd / self[i].cadence)
                    n += 1
            i += 1
        if lst:
            return (statistics.mean(lst), statistics.stdev(lst))
        else:
            return (0, 0)

    def nearby(self, a, b, range=1.0):
        return abs(a - b) < range

    def __getitem__(self, i):
        return self.seq[i]

    def find_estimation_start(self, v, end_i, decimals=2, diff=None, pct_diff=None):
        v = round(v, decimals)
        if pct_diff is not None:
            diff = v * (pct_diff / 100)
        est_start = end_i
        for i in range(end_i, -1, -1):
            if diff is not None:
                if abs(self.delta_dist(i) - v) > diff:
                    break
            else:
                if round(self.delta_dist(i), decimals) != v:
                    break
            est_start = i
        return est_start

    def compare_delta_dist(self, v, start_i, end_i, decimals=2, diff=None, pct_diff=None):
        v = round(v, decimals)
        if pct_diff is not None:
            diff = v * (pct_diff / 100)
        for i in range(start_i, end_i+1):
            if diff is not None:
                if abs(self.delta_dist(i) - v) > diff:
                    return False
            else:
                if round(self.delta_dist(i), decimals) != v:
                    return False
        return True


    def distribute_distance(self, start_i, end_i,
                            distance, cadence, total_time, usable_time,
                            max_step=10):
        step = distance / total_time
        last_i = max(start_i-1, 0)
        distance_p = self[last_i].distance
        for i in range(start_i, end_i+1):
            td = self.time_delta(i)
            if td > max_step:
                self[i].distance = distance_p
                continue
            self[i].distance = distance_p + step * td
            self[i].cadence = cadence
            distance_p = self[i].distance
            last_i = i


    def usable_time(self, start_i, end_i, max_step=10):
        total = 0
        for i in range(start_i, end_i+1):
            td = self.time_delta(i)
            if td <= max_step:
                total += td
        return total

    def show(self, prefix, start_i, end_i=None):
        if not self.options.get_bool("verbose"):
            return
        if end_i is None:
            end_i = start_i
        for i in range(start_i, end_i+1):
            r = self.seq[i]
            print("%s %3d %s: t=%d, dd=%.2f, cad=%.2f, rspd=%.2f -- cspd=%.2f, total_d=%.2f" % (
                prefix, i, self.active_time_str(i), self.time_delta(i),
                self.delta_dist(i), r.cadence, self.recorded_speed(i),
                self.calculated_speed(i), r.distance))

    def smooth(self):
        i = -1
        start_0 = None
        end_0 = None
        pause = []
        while i+1 < len(self.seq):
            i += 1
            r = self.seq[i]
            self.show("Smooth", i)
            if r.cadence == 0:
                if start_0 is None:
                    start_0 = i
                end_0 = i
            else:
                if start_0 is not None:
                    pause.append((start_0, end_0))
                    start_0 = None
                    end_0 = None

        for (start_0, end_0) in pause:
            if self.options.get_bool("verbose"):
                print("Step: %3d - %3d" % (start_0, end_0))
            nri = self.next_ri(end_0)
            delta_dist = self.delta_dist(nri)
            if self.compare_delta_dist(delta_dist, start_0, end_0, pct_diff=10):
                start_0 = self.find_estimation_start(delta_dist, start_0, pct_diff=10)
                if start_0 == 0:
                    start_dist = 0
                    start_t = self[0].time
                else:
                    start_dist = self[start_0-1].distance
                    start_t = self[start_0-1].time

                if end_0 < len(self.seq):
                    end_dist = self[end_0+1].distance
                    cadence = self[end_0+1].cadence
                    end_t = self[end_0+1].time
                else:
                    end_dist = self[end_0].distance
                    cadence = self[end_0].cadence
                    end_t = self[end_0].time

                distributable = end_dist - start_dist
                usable_time = self.usable_time(start_0, end_0)
                total_time = usable_time #(end_t - start_t).total_seconds()
                if self.options.get_bool("verbose"):
                    print("  Distribute: %.2f %.2f" % (distributable, usable_time))
                self.show("    Smoothing", start_0, end_0)
                self.distribute_distance(start_0, end_0,
                                         distributable, cadence,
                                         total_time, usable_time)
                self.show("    Smoothed", start_0, end_0)


    def cleanup(self, max_step=10):
        pina = []
        for i in range(0, len(self.seq)):
            spd = self.calculated_speed(i)
            rec_spd = self.recorded_speed(i)
            if self.time_delta(i) > max_step and self[i].cadence == 0:
                self.set_recorded_speed(i, 0)
            elif (spd > self.max_speed or rec_spd > self.max_speed):
                (avg_cad, var) = self.avg_spd_by_cad(i, 10, 10)
                mix = random.triangular(-var, var)
                nc = round(self[i].cadence + self[i].cadence * mix)
                # print("HUHA %d, %.2f, %.2f, %.2f - ~%.2f, *%.2f, %.2f, %.2f" % (i, avg_cad, self[i].cadence, self[i].cadence * avg_cad, var, mix, nc, nc * avg_cad))
                self[i].cadence = nc
                pina.append(nc)
                self.set_recorded_speed(i, self[i].cadence * avg_cad)
            else:
                self.set_recorded_speed(i, max(rec_spd, spd))

        distance = self[0].distance
        for i in range(0, len(self.seq)):
            t = self.time_delta(i)
            step = self.recorded_speed(i) * t / 3600 * 1000
            self[i].distance = distance + step
            distance = self[i].distance

        self.show("  Cleaned up", 0, len(self.seq)-1)
