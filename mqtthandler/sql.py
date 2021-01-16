#!/usr/bin/env python3

# from sqlalchemy import exc

# from dashboard.app import app, db      # noqa: E402
# from models.Mqtt import Mqtt      # noqa: E402
# from models.State import State      # noqa: E402
# from models.RfData import RfData      # noqa: E402
# from models.RoomData import RoomData      # noqa: E402
# from models.Tablet import TabletBattery      # noqa: E402
# from models.ProbeRequest import ProbeRequest      # noqa: E402

import logging
logger = logging.getLogger()

from .db_init import Mqtt, State, RfData, RoomData, TabletBattery, db_session, connect_db
from .detached import detachify
from .mac_vendor import get_mac_vendor

def add_mqtt_to_db(time, topic, payload, qos, retain):
    new_data = Mqtt(
        date=time,
        topic=topic,
        payload=payload,
        qos=qos,
        retain=retain
    )
    with db_session() as session:
        session.add(new_data)
    # try:
    #     db.session.add(new_data)
    #     db.session.commit()
    # except exc.SQLAlchemyError as e:
    #     app.logger.error(e)
    #     db.session.rollback()


def add_room_data_to_db(date_time, temperature, humidity, brightness, pressure, altitude):
    new_data = RoomData(
        date=date_time,
        temperature=temperature,
        humidity=humidity,
        brightness=brightness,
        pressure=pressure,
        altitude=altitude
    )
    with db_session() as session:
        session.add(new_data)


def add_rf_data_to_db(curr_time, decimal, length, binary, pulse_length, protocol):
    new_data = RfData(
        date=curr_time,
        decimal=decimal,
        bits=length,
        binary=binary,
        pulse_length=pulse_length,
        protocol=protocol
    )
    with db_session() as session:
        session.add(new_data)


def add_tablet_battery_level(curr_time, n_level):
    new_data = TabletBattery(
        date=curr_time,
        level=n_level,
    )
    with db_session() as session:
        session.add(new_data)


@detachify
def add_probe_request(time, macaddress, ssid, rssi, **kwargs):
    _, _, _, _, _, ProbeRequest, db_session = connect_db()
    if 'make' in kwargs.keys() and kwargs['make']:
        make = kwargs['make']
    else:
        logger.debug("MAC vendor is missing.")
        with db_session() as session:
            make = session.query(ProbeRequest.make).filter(ProbeRequest.macaddress == macaddress).first()
            if make and make[0]:
                make = make[0]
            else:
                logger.info(f"No known mac vendor for mac '{macaddress}'. Searching the internet.")
                make = get_mac_vendor(macaddress)

    new_data = ProbeRequest(
        date=time,
        macaddress=macaddress,
        make=make,
        ssid=ssid,
        rssi=rssi,
    )
    logger.info(f"Add proberequest <ProbeRequest date={time}, macaddress={macaddress}, make={make}, ssid={ssid}, rssi={rssi}> to database.")
    with db_session() as session:
        session.add(new_data)


def add_state_to_db(time, device, state):
    new_data = State(
        date=time,
        device=device,
        state=state,
    )
    with db_session() as session:
        session.add(new_data)
