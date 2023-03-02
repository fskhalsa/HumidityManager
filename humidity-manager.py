#!/usr/bin/python3

# (C) 2023 - Fateh Singh Khalsa
# Application for Managing Reptile Enclosure Humidity #
# - Uses SensorPush API to check humidity from sensor in enclosure
# - Uses VeSync API to toggle a smart outlet connected to a misting pump
# - Misting trigger humidity taken from SensorPush sensor's lower limit

import os
import sys
import logging

from dotenv import load_dotenv
from pysensorpush import PySensorPush
from pyvesync import VeSync
import time

#system constants
MONITORING_SENSOR_NAME = 'Delilah Vivarium - Hot Side'
MISTING_PUMP_OUTLET_NAME = 'Vivarium Mister'

#system defaults
HUMIDITY_MONITORING_FREQUENCY = 300     # check humidity every 5 minutes
HUMIDITY_TRIGGER_OFFSET = 0             # trigger misting as soon as humidity drops below lower limit
MISTING_RUNTIME = 5                     # run misting pump for 5 seconds (accounts for delay in outlet switching - actually ends up being ~3 seconds)
MISTING_TIMEOUT_PERIOD = 600            # don't trigger misting for another 10 minutes after being triggered

#don't change
MISTING_LAST_TRIGGERED = None

def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # info handler for logging humidity management history to file
    infoHandler = logging.FileHandler('logs/humidity-manager-log.log')
    infoFormatter = logging.Formatter('%(asctime)s - %(message)s', '%a, %b %d, %Y @ %H:%M:%S')
    infoHandler.setLevel(logging.INFO)
    infoHandler.setFormatter(infoFormatter)

    # error handler for logging warnings and errors to console
    errorHandler = logging.StreamHandler()
    errorFormatter = logging.Formatter('%(levelname)s: %(name)s - %(asctime)s - %(message)s')
    errorHandler.setLevel(logging.WARNING)
    errorHandler.setFormatter(errorFormatter)

    logging.basicConfig(handlers=[infoHandler, errorHandler], force=True)

def setup():
    #TODO: setup rotating log files, to create new log file on each run (https://stackoverflow.com/questions/44635896/how-to-create-a-new-log-file-every-time-the-application-runs)
    #load api credentials from .env
    load_dotenv()

    #setup logging
    setup_logger()

    #init logging
    logging.warning(f'\nBeginning humidity management.\nWill check humidity of \'{MONITORING_SENSOR_NAME}\' every {HUMIDITY_MONITORING_FREQUENCY//60} minutes, and enable \'{MISTING_PUMP_OUTLET_NAME}\' if necessary.\n\nHistory:')

def toggle_vesync_outlet(misting_runtime):
    #get vesync credentials
    VS_USER = os.getenv('HM_VESYNC_USER', None)
    VS_PASSWORD = os.getenv('HM_VESYNC_PASSWORD', None)

    if (VS_USER == None) or (VS_PASSWORD == None):
        logging.error("ERROR! Must define env variables HM_VESYNC_USER and HM_VESYNC_PASSWORD")
        raise SystemExit

    #setup outlet manager
    manager = VeSync(VS_USER, VS_PASSWORD)
    manager.login()
    manager.update()

    #get outlet, and toggle on for misting_runtime
    misting_pump_outlet = next(outlet for outlet in manager.outlets if outlet.device_name == MISTING_PUMP_OUTLET_NAME)
    misting_pump_outlet.turn_on()
    time.sleep(misting_runtime)
    misting_pump_outlet.turn_off()

def trigger_misting(current_humidity, humidity_min, misting_runtime):
    logging.info(f'Humidity at {current_humidity}, below lower limit of {humidity_min}. Enabling Misting for {misting_runtime} seconds.')
    toggle_vesync_outlet(misting_runtime)
    MISTING_LAST_TRIGGERED = time.time()

def manage_humidity():
    #get sensorpush credentials
    SP_USER = os.getenv('HM_SENSORPUSH_USER', None)
    SP_PASSWORD = os.getenv('HM_SENSORPUSH_PASSWORD', None)

    if (SP_USER == None) or (SP_PASSWORD == None):
        logging.error("ERROR! Must define env variables HM_SENSORPUSH_USER and HM_SENSORPUSH_PASSWORD")
        raise SystemExit

    #get sensor data
    sensorpush = PySensorPush(SP_USER, SP_PASSWORD)

    # gateways = sensorpush.gateways
    sensors = sensorpush.sensors
    samples = sensorpush.samples(1) # just take one sample, as we only need the latest (current) sensor data

    #testing data
    # gateways = {'Home Gateway': {'name': 'Home Gateway', 'last_alert': '2021-02-17T10:39:55.000Z', 'last_seen': '2021-03-17T22:54:07.000Z', 'version': '1.1.3(23)', 'message': None, 'paired': True}}
    # sensors = {'51240.10175551081307848351': {'calibration': {'humidity': 0, 'temperature': 0}, 'address': 'E7:61:AF:9F:1D:98', 'name': '1 - Delilah Enclosure - Hot Side', 'active': True, 'deviceId': '51240', 'alerts': {'temperature': {'enabled': True, 'max': 98, 'min': 82}, 'humidity': {'enabled': True, 'max': 65, 'min': 50}}, 'rssi': -82, 'id': '51240.10175551081307848351', 'battery_voltage': 3.08}, '53572.3511479435122959721': {'calibration': {'humidity': 0, 'temperature': 0}, 'address': 'FA:D5:D7:8E:2D:53', 'name': '2 - Delilah Enclosure - Cool Side', 'active': True, 'deviceId': '53572', 'alerts': {'temperature': {'enabled': True, 'max': 85, 'min': 75}, 'humidity': {'enabled': True, 'max': 65, 'min': 50}}, 'rssi': -76, 'id': '53572.3511479435122959721', 'battery_voltage': 2.9}}
    # samples = {'last_time': '2021-03-17T22:57:22.000Z', 'sensors': {'51240.10175551081307848351': [{'observed': '2021-03-17T22:57:22.000Z', 'temperature': 80, 'humidity': 63.9}], '53572.3511479435122959721': [{'observed': '2021-03-17T22:57:03.000Z', 'temperature': 79.6, 'humidity': 43.7}]}, 'truncated': False, 'status': 'OK', 'total_samples': 2, 'total_sensors': 2}

    #get sensor humidity settings
    sensor_id = None
    sensor_info = None
    for s_id, s_info in sensors.items():
        if s_info['name'] == MONITORING_SENSOR_NAME:
            sensor_id = s_id
            sensor_info = s_info
    sensor_humidity_info = sensor_info['alerts']['humidity']

    humidity_range_enabled = sensor_humidity_info['enabled']
    humidity_min = sensor_humidity_info['min']
    
    #check if misting should be triggered, and trigger if so
    current_humidity = samples['sensors'][sensor_id][0]['humidity']
    misting_timeout_active = time.time() < MISTING_LAST_TRIGGERED + MISTING_TIMEOUT_PERIOD if MISTING_LAST_TRIGGERED != None else False

    if humidity_range_enabled == True and current_humidity + HUMIDITY_TRIGGER_OFFSET < humidity_min and not misting_timeout_active:
        trigger_misting(current_humidity, humidity_min, MISTING_RUNTIME)
    elif humidity_range_enabled != True:
        logging.error('Humidity range not enabled on sensor. Please set a minimum humidity limit on your SensorPush sensor.')
    elif current_humidity + HUMIDITY_TRIGGER_OFFSET >= humidity_min:
        logging.info(f'Humidity at {current_humidity}, above lower limit of {humidity_min}. No misting necessary.')
    elif misting_timeout_active:
        logging.info(f'Misting last occurred {time.time() - MISTING_LAST_TRIGGERED} seconds ago. Not enabling misting, to allow humidity time to adjust.')

#main
def main():
    setup()

    #check and manage humidity every HUMIDITY_MONITORING_FREQUENCY seconds
    humidity_last_managed = None
    while True:
        if humidity_last_managed == None or time.time() > humidity_last_managed + HUMIDITY_MONITORING_FREQUENCY:
            manage_humidity()
            humidity_last_managed = time.time()

if __name__ == "__main__":
    main()
