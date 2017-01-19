# Track Merge: Merge GPS-recorded tracks

Merge overlapping tracks recorded by multiple GPS units in any format supported by [activityio](https://github.com/jmackie4/activityio) (tested with FIT, TCX and GPX), averaging the paths and interpolating missing data points where needed. The resulting track is stored in GPX format as a collection of trackpoints with Garmin extensions.

This is an early version, kind of a proof of concept full of simplistic algorithms. It was intended to be used with bicyle-specific GPS units and tracks, so the only known and used extensions are heart rate and temperature for now. The generated GPX file was tested with [Strava](http://strava.com) and found to be uploadable with all data recognized and accepted.

## Installation

```shell
pip install -r requirements.txt
zip -9r whatever trkm/ __main__.py
python whatever
```

## Usage

Just run it once and read the instructions.
