#!/usr/bin/env python

# stdlib imports
import os
from datetime import datetime, timedelta
import re

# third party imports
import numpy as np
from scipy import constants

# local
from gmprocess.stationstream import StationStream
from gmprocess.stationtrace import StationTrace, PROCESS_LEVELS
from gmprocess.io.seedname import (get_channel_name,
                                   get_units_type,
                                   is_channel_north)


TIMEFMT1 = '%Y/%m/%d %H:%M:%S.%f'
TIMEFMT2 = '%Y/%m/%d %H:%M:%S'
FLOATRE = "[-+]?[0-9]*\.?[0-9]+"
INTRE = "[-+]?[0-9]*"

# 20/07/2017 22:30:58.000000
TIME_RE = '[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}\.?[0-9]*'

HEADER_LINES = 88
HEADER_PLUS_COMMENT = 103
ALL_HEADERS = 109

COLWIDTH = 12
NCOLS = 3

SOURCE = 'Seismic Network of the NorthEastern Mexico'
SOURCE_FORMAT = 'UNAM'
NETWORK = 'MG'

MARKER = 'ARCHIVO ESTANDAR DE ACELERACION'


def is_unam(filename):
    try:
        with open(filename, 'rt') as myfile:
            header = [next(myfile) for x in range(7)]
    except Exception:
        return False
    if MARKER in header[6]:
        return True

    return False


def read_unam(filename):
    """Read the Mexican UNAM strong motion data format.

    Args:
        filename (str): path to UNAM data file.

    Returns:
        list: Sequence of one StationStream object containing 3
        StationTrace objects.
    """

    channels = _read_header(filename)
    npts = channels[0]['npts']
    all_data = np.genfromtxt(filename, skip_header=ALL_HEADERS, max_rows=npts)
    trace1 = StationTrace(data=all_data[:, 0], header=channels[0])
    trace2 = StationTrace(data=all_data[:, 1], header=channels[1])
    trace3 = StationTrace(data=all_data[:, 2], header=channels[2])

    # tell the trace that data has already been converted to physical units
    response = {'input_units': 'counts', 'output_units': 'cm/s^2'}
    trace1.setProvenance('remove_response', response)
    trace2.setProvenance('remove_response', response)
    trace3.setProvenance('remove_response', response)

    stream = StationStream(traces=[trace1, trace2, trace3])
    return [stream]


def _read_header(filename):
    # read in first 88 lines
    with open(filename, 'rt') as myfile:
        header = [next(myfile) for x in range(HEADER_LINES)]

    header_dict = {}
    lastkey = ''
    for line in header:
        if not len(line.strip()):
            continue
        if ':' in line:
            colidx = line.find(':')
            key = line[0:colidx].strip()
            value = line[colidx + 1:].strip()
            if not len(key):
                key = lastkey + '$'
            lastkey = key
            header_dict[key] = value

    # create a list of dictionaries for channel spec
    channels = [{}, {}, {}]
    channels[0]['standard'] = {}
    channels[1]['standard'] = {}
    channels[2]['standard'] = {}

    station = header_dict['CLAVE DE LA ESTACION']
    channels[0]['station'] = station
    channels[1]['station'] = station
    channels[2]['station'] = station

    channels[0]['network'] = NETWORK
    channels[1]['network'] = NETWORK
    channels[2]['network'] = NETWORK

    # unam provides the start *time* of the record, but not the date.
    # it is up to us to determine whether midnight has occurred between
    # eq time and record start time.

    # the hour/min/sec of trigger time
    (rhour,
     rminute,
     rsecond) = header_dict['HORA DE LA PRIMERA MUESTRA (GMT)'].split(':')
    dtsecs = (int(rhour) * 3600) + (int(rminute) * 60) + (float(rsecond))
    startdt = timedelta(seconds=dtsecs)
    eqdatestr = header_dict['FECHA DEL SISMO [GMT]']
    eqdate = datetime.strptime(eqdatestr, '%Y/%m/%d')
    # the hour, minute and second of origin
    eqtimestr = header_dict['HORA EPICENTRO (GMT)']
    try:
        eqtime = datetime.strptime('%s %s' % (eqdatestr, eqtimestr), TIMEFMT1)
    except ValueError:
        eqtime = datetime.strptime('%s %s' % (eqdatestr, eqtimestr), TIMEFMT2)

    starttime = eqdate + startdt
    if starttime < eqtime:
        starttime = eqdate + timedelta(days=1) + startdt

    channels[0]['starttime'] = starttime
    channels[1]['starttime'] = starttime
    channels[2]['starttime'] = starttime

    # get record durations for each channel
    durstr = header_dict['DURACION DEL REGISTRO (s), C1-C6'].lstrip('/')
    durations = [float(dur) for dur in durstr.split('/')]

    channels[0]['duration'] = durations[0]
    channels[1]['duration'] = durations[1]
    channels[2]['duration'] = durations[2]

    # get deltas
    delta_strings = header_dict['INTERVALO DE MUESTREO, C1-C6 (s)'].split('/')
    deltas = [float(delta) for delta in delta_strings[1:]]
    channels[0]['delta'] = deltas[0]
    channels[1]['delta'] = deltas[1]
    channels[2]['delta'] = deltas[2]

    # get sampling rates
    channels[0]['sampling_rate'] = 1 / deltas[0]
    channels[1]['sampling_rate'] = 1 / deltas[1]
    channels[2]['sampling_rate'] = 1 / deltas[2]

    # get channel orientations
    azstrings = header_dict['ORIENTACION C1-C6 (rumbo;orientacion)'].split('/')
    az1, az1_vert = _get_azimuth(azstrings[1])
    az2, az2_vert = _get_azimuth(azstrings[2])
    az3, az3_vert = _get_azimuth(azstrings[3])
    channels[0]['standard']['horizontal_orientation'] = az1
    channels[1]['standard']['horizontal_orientation'] = az2
    channels[2]['standard']['horizontal_orientation'] = az3
    az1_north = is_channel_north(az1)
    az2_north = is_channel_north(az2)
    az3_north = is_channel_north(az3)
    channels[0]['channel'] = get_channel_name(channels[0]['sampling_rate'],
                                              True,
                                              az1_vert,
                                              az1_north)
    channels[1]['channel'] = get_channel_name(channels[1]['sampling_rate'],
                                              True,
                                              az2_vert,
                                              az2_north)
    channels[2]['channel'] = get_channel_name(channels[2]['sampling_rate'],
                                              True,
                                              az3_vert,
                                              az3_north)

    # get channel npts
    npts_strings = header_dict['NUM. TOTAL DE MUESTRAS, C1-C6'].split('/')
    npts_list = [float(npts) for npts in npts_strings[1:]]
    channels[0]['npts'] = npts_list[0]
    channels[1]['npts'] = npts_list[1]
    channels[2]['npts'] = npts_list[2]

    # locations
    channels[0]['location'] = '--'
    channels[1]['location'] = '--'
    channels[1]['location'] = '--'

    # get station coordinates
    coord1 = header_dict['COORDENADAS DE LA ESTACION']
    coord2 = header_dict['COORDENADAS DE LA ESTACION$']
    if 'LAT' in coord1:
        latitude = float(re.search(FLOATRE, coord1).group())
        longitude = float(re.search(FLOATRE, coord2).group())
        if coord1.strip().endswith('S'):
            latitude *= -1
        if coord2.strip().endswith('W'):
            longitude *= -1
    else:
        latitude = re.search(FLOATRE, coord2)
        longitude = re.search(FLOATRE, coord1)
        if coord1.strip().endswith('W'):
            longitude *= -1
        if coord2.strip().endswith('S'):
            latitude *= -1
    elevation = float(header_dict['ALTITUD (msnm)'])
    cdict = {'latitude': latitude,
             'longitude': longitude,
             'elevation': elevation}
    channels[0]['coordinates'] = cdict
    channels[1]['coordinates'] = cdict
    channels[2]['coordinates'] = cdict

    # fill in other standard stuff
    channels[0]['standard']['units_type'] = 'acc'
    channels[1]['standard']['units_type'] = 'acc'
    channels[2]['standard']['units_type'] = 'acc'

    channels[0]['standard']['source_format'] = SOURCE_FORMAT
    channels[1]['standard']['source_format'] = SOURCE_FORMAT
    channels[2]['standard']['source_format'] = SOURCE_FORMAT

    channels[0]['standard']['instrument'] = header_dict['MODELO DEL ACELEROGRAFO']
    channels[1]['standard']['instrument'] = header_dict['MODELO DEL ACELEROGRAFO']
    channels[2]['standard']['instrument'] = header_dict['MODELO DEL ACELEROGRAFO']

    channels[0]['standard']['sensor_serial_number'] = header_dict['NUMERO DE SERIE DEL ACELEROGRAFO']
    channels[1]['standard']['sensor_serial_number'] = header_dict['NUMERO DE SERIE DEL ACELEROGRAFO']
    channels[2]['standard']['sensor_serial_number'] = header_dict['NUMERO DE SERIE DEL ACELEROGRAFO']

    channels[0]['standard']['process_level'] = PROCESS_LEVELS['V1']
    channels[1]['standard']['process_level'] = PROCESS_LEVELS['V1']
    channels[2]['standard']['process_level'] = PROCESS_LEVELS['V1']

    channels[0]['standard']['process_time'] = ''
    channels[1]['standard']['process_time'] = ''
    channels[2]['standard']['process_time'] = ''

    channels[0]['standard']['station_name'] = header_dict['NOMBRE DE LA ESTACION']
    channels[1]['standard']['station_name'] = header_dict['NOMBRE DE LA ESTACION']
    channels[2]['standard']['station_name'] = header_dict['NOMBRE DE LA ESTACION']

    channels[0]['standard']['structure_type'] = ''
    channels[1]['standard']['structure_type'] = ''
    channels[2]['standard']['structure_type'] = ''

    channels[0]['standard']['corner_frequency'] = np.nan
    channels[1]['standard']['corner_frequency'] = np.nan
    channels[2]['standard']['corner_frequency'] = np.nan

    channels[0]['standard']['units'] = 'cm/s/s'
    channels[1]['standard']['units'] = 'cm/s/s'
    channels[2]['standard']['units'] = 'cm/s/s'

    periods = _get_periods(header_dict['FREC. NAT. DE SENSORES, C1-C6, (Hz)'])
    channels[0]['standard']['instrument_period'] = periods[0]
    channels[1]['standard']['instrument_period'] = periods[1]
    channels[2]['standard']['instrument_period'] = periods[2]

    dampings = _get_dampings(header_dict['AMORTIGUAMIENTO DE SENSORES, C1-C6'])
    channels[0]['standard']['instrument_damping'] = dampings[0]
    channels[1]['standard']['instrument_damping'] = dampings[1]
    channels[2]['standard']['instrument_damping'] = dampings[2]

    with open(filename, 'rt') as myfile:
        header = [next(myfile) for x in range(HEADER_PLUS_COMMENT)]
    clines = header[89:102]
    comments = ' '.join(clines).strip()
    channels[0]['standard']['comments'] = comments
    channels[1]['standard']['comments'] = comments
    channels[2]['standard']['comments'] = comments

    head, tail = os.path.split(filename)
    source_file = tail or os.path.basename(head)
    channels[0]['standard']['source_file'] = source_file
    channels[1]['standard']['source_file'] = source_file
    channels[2]['standard']['source_file'] = source_file

    channels[0]['standard']['source'] = SOURCE
    channels[1]['standard']['source'] = SOURCE
    channels[2]['standard']['source'] = SOURCE

    decfactor = float(header_dict['FACTOR DE DECIMACION'])
    channels[0]['standard']['instrument_sensitivity'] = decfactor
    channels[1]['standard']['instrument_sensitivity'] = decfactor
    channels[2]['standard']['instrument_sensitivity'] = decfactor

    return channels


def _get_dampings(dampstr):
    damp_strings = dampstr.split('/')[1:]
    dampings = []
    for dampstr in damp_strings:
        damp_match = re.search(FLOATRE, dampstr.strip())
        if damp_match is None:
            dampings.append(np.nan)
            continue
        damping = float(damp_match.group())
        dampings.append(damping)
    return dampings


def _get_periods(freqstr):
    freq_strings = freqstr.split('/')[1:]
    periods = []
    for freqstr in freq_strings:
        freq_match = re.search(FLOATRE, freqstr.strip())
        if freq_match is None:
            periods.append(np.nan)
            continue
        freq = float(freq_match.group())
        periods.append(1 / freq)
    return periods


def _get_azimuth(azstring):
    azimuth = 0.0
    isvert = False
    if 'V' in azstring:
        azimuth = 0.0
        isvert = True
    else:
        azimuth = float(re.search('[0-9]+', azstring).group())
        # why doesn't line below work?
        # azimuth = re.search(INTRE, azstring).group()
    return (azimuth, isvert)
