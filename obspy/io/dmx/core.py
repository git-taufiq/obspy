"""
INGV DMX bindings to ObsPy core module.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from future.builtins import *  # NOQA
from future.utils import native_str

from tempfile import SpooledTemporaryFile

import numpy as np

from obspy import Stream, Trace, UTCDateTime
from obspy.core.util.attribdict import AttribDict


descript_trace_dtypes = np.dtype([(native_str("network"), native_str("4S")),
                                  (native_str("st_name"), native_str("5S")),
                                  (native_str("component"), native_str("1S")),
                                  (native_str("insstype"), np.int16),
                                  (native_str("begintime"), np.double),
                                  (native_str("localtime"), np.int16),
                                  (native_str("datatype"), native_str("1S")),
                                  (native_str("descriptor"), native_str("1S")),
                                  (native_str("digi_by"), np.int16),
                                  (native_str("processed"), np.int16),
                                  (native_str("length"), np.int32),
                                  (native_str("rate"), np.float32),
                                  (native_str("mindata"), np.float32),
                                  (native_str("maxdata"), np.float32),
                                  (native_str("avenoise"), np.float32),
                                  (native_str("numclip"), np.int32),
                                  (native_str("timecorrect"), np.double),
                                  (native_str("rate_correct"), np.float32),
                                  ])

structtag_dtypes = np.dtype([(native_str("sinc"), native_str("1S")),
                             (native_str("machine"), native_str("1S")),
                             (native_str("id_struct"), np.int16),
                             (native_str("len_struct"), np.int32),
                             (native_str("len_data"), np.int32)])

types = {"s": ("uint16", "H", 2), "q": ("int16", "h", 2),
         "u": ("uint16", "H", 2), "i": ("int16", "h", 2),
         "2": ("int32", "i", 4), "l": ("int32", "i", 4),
         "r": ("uint16", "H", 2), "f": ("float32", "f", 4),
         "d": ("float64", "d", 8)}


def readstructtag(fid):
    y = AttribDict()
    data = np.fromfile(fid, structtag_dtypes, 1)
    for (key, (fmt, size)) in structtag_dtypes.fields.items():
        if str(fmt).count("S") != 0:
            y[key] = data[key][0].decode('UTF-8')
        else:
            y[key] = data[key][0]
    return y


def readdescripttrace(fid):
    y = AttribDict()

    data = np.fromfile(fid, descript_trace_dtypes, 1)

    for (key, (fmt, size)) in descript_trace_dtypes.fields.items():
        if str(fmt).count("S") != 0:
            y[key] = data[key][0].decode('UTF-8')
        else:
            y[key] = data[key][0]

    return y


def readdata(fid, n, t):
    target = types[t]
    return np.fromfile(fid, np.dtype(target[0]), n)


def _is_dmx(filename):
    try:
        with open(filename, "rb") as fid:
            while fid.read(12):  # we require at least 1 full structtag
                fid.seek(-12, 1)
                structtag = readstructtag(fid)
                if structtag.id_struct == 7:
                    descripttrace = readdescripttrace(fid)
                    UTCDateTime(descripttrace.begintime)
                    return True
                else:
                    fid.seek(
                        int(structtag.len_struct) + int(structtag.len_data), 1)

    except Exception:
        return False
    return True


def _read_dmx(filename, **kwargs):
    station = kwargs.get("station", None)

    traces = []
    with open(filename, "rb") as fid:
        content = fid.read()

    with SpooledTemporaryFile(mode='w+b') as fid:
        fid.write(content)
        fid.seek(0)

        while fid.read(12):  # we require at least 1 full structtag
            fid.seek(-12, 1)
            structtag = readstructtag(fid)
            if structtag.id_struct == 7:
                descripttrace = readdescripttrace(fid)
                if station is None or descripttrace.st_name.strip() == station:
                    data = readdata(fid, descripttrace.length,
                                    descripttrace.datatype)
                    tr = Trace(data=np.asarray(data))
                    tr.stats.network = descripttrace.network.strip()
                    tr.stats.station = descripttrace.st_name.strip()
                    tr.stats.channel = descripttrace.component
                    tr.stats.sampling_rate = descripttrace.rate
                    tr.stats.starttime = UTCDateTime(descripttrace.begintime)
                    tr.stats.dmx = AttribDict({"descripttrace": descripttrace,
                                               "structtag": structtag})
                    traces.append(tr)
                else:
                    fid.seek(int(structtag.len_data), 1)
            else:
                fid.seek(
                    int(structtag.len_struct) + int(structtag.len_data), 1)

    st = Stream(traces=traces)
    return st


if __name__ == '__main__':
    import doctest
    doctest.testmod(exclude_empty=True)
