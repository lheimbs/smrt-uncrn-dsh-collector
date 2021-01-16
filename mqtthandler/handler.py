#!/usr/bin/env python3
# coding=utf-8

import sys
import time
import logging
import socket
import subprocess
import random
import paho.mqtt.client as mqtt
from datetime import datetime

from mqtthandler.config import config
from mqtthandler.PipeLogging import LogPipe
from mqtthandler.random_data import random_publish
import mqtthandler.sql as sql

from mqtthandler.callbacks import (
    temp_message_to_db,
    handle_rf_transmission,
    handle_battery_level,
    handle_probes,
    handle_states,
    handle_tablet_charging
)

STATUS_TOPIC = "mqtt/smrt-uncrn-cllctr/status"
logger = logging.getLogger('mqtt_handler')


def connect(client, brokers=None, port=None):
    if not brokers:
        brokers = ['localhost', 'lennyspi.local', '192.168.1.201', '192.168.1.205']
    if not port:
        port = 8883

    for host in brokers:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logger.debug(f"Try connection to broker {host} on port {port}.")
        if sock.connect_ex((host, port)) == 0:
            try:
                client.connect(host, port, 60)
                logger.info(f"Connected to broker on host {host}.")
                client.will_set(STATUS_TOPIC, "offline")
                break
            except ConnectionRefusedError:
                logger.warning("Broker refused connection. Are host/port correct?")
            except socket.gaierror:
                logger.warning("Connection to broker failed. Hostname is probably not valid.")
            except TimeoutError:
                logger.warning("Connecting to broker timed out.")
    else:
        logger.error("Could not connect to broker.")
        return None
    return client


def on_connect(client, userdata, flags, rc):
    topic = '#'
    client.subscribe(topic)
    logger.info(f"Subscribed to topic '{topic}'.")
    client.publish(STATUS_TOPIC, "online")
    logger.debug("Published online status")


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode("utf-8")

    logger.debug(f"'on_message' called: topic='{topic}', msg='{payload}'.")

    if topic == 'trash':
        logger.info("Message is trash. Discarding")
    else:
        sql.add_mqtt_to_db(datetime.now(), topic, payload, msg.qos, msg.retain)


def add_mqtt_callbacks(client):
    client.on_connect = on_connect
    client.on_message = on_message

    client.message_callback_add("room/data", temp_message_to_db)
    client.message_callback_add("room/data/rf/recieve", handle_rf_transmission)
    client.message_callback_add("tablet/shield/battery", handle_battery_level)
    client.message_callback_add("tablet/shield/charging", handle_tablet_charging)
    client.message_callback_add("mqtt/probes", handle_probes)
    client.message_callback_add("mqtt/+/status", handle_states)


def main():
    logger.debug(f"CONFIG: {str(config)[27:-2]}")
    logger.debug(f"DATABASE_URI: {config.SQLALCHEMY_DATABASE_URI}")
    logger.debug(f"MQTT_SERVER: {config.MQTT_SERVER}:{config.MQTT_PORT}")

    client = mqtt.Client()
    broker = None

    mqtt_logger = logging.getLogger('client')
    mqtt_logger.setLevel(logging.INFO)
    client.enable_logger(logger=mqtt_logger)

    add_mqtt_callbacks(client)

    # connect to broker
    if config.OFFLINE and config.MQTT_SERVER == 'localhost':
        logger.info("Using local development broker.")

        sys.stdout = LogPipe(logging.DEBUG, 'local_broker')
        sys.stderr = LogPipe(logging.INFO, 'local_broker')

        broker = subprocess.Popen(
            ['mosquitto', '-p', str(config.MQTT_PORT)],
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        logger.debug(f"Starting development broker locally. PID: {broker.pid}.")
        time.sleep(1)

        client = connect(client, (config.MQTT_SERVER,), config.MQTT_PORT)
    else:
        client = connect(client)

    start_time = time.time()
    try:
        if config.OFFLINE and config.MQTT_SERVER == 'localhost':
            rand_time = random.randint(3, 9)
            choice = 'roomdata'
            client.loop_start()

        while client:
            if config.OFFLINE and config.MQTT_SERVER == 'localhost':
                if time.time() % rand_time == 0:
                    choice = random_publish(choice, config.MQTT_PORT)
                    rand_time = random.randint(10, 90)
                elif time.time() - start_time >= 60:
                    random_publish('roomdata', config.MQTT_PORT)
                    start_time = time.time()
            else:
                if start_time % 3600 == 0:
                    client.publish(STATUS_TOPIC, "online")
                client.loop()

    except KeyboardInterrupt:
        logger.info("Script stopped through Keyboard Interrupt")
        if config.DEBUG:
            client.loop_stop()
    finally:
        logger.info("Disconnecting client from broker.")
        if client and client.is_connected:
            client.disconnect()
        if broker:
            # close the file handlers properly
            sys.stdout.close()
            sys.stdout = sys.__stdout__
            sys.stderr.close()
            sys.stderr = sys.__stderr__
            broker.terminate()