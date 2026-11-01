"""MQTT client connection and authentication helpers"""

import os
from threading import Event
from uuid import uuid4
import paho.mqtt.client as mqtt  # type: ignore[reportMissingImports]


# MQTT broker hostname and port
HOST = os.getenv('MQTT_HOST', 'broker')
PORT = 1883


def make_client(on_message=None):
    """Create an MQTT client using department credentials"""

    # retrieves username and password from environment variables
    username = os.environ['MQTT_USERNAME']
    password = os.environ['MQTT_PASSWORD']

    # create an MQTT client with unique client ID
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f'{username}-{uuid4().hex[:12]}',
        protocol=mqtt.MQTTv5,
    )

    # assign username and password
    client.username_pw_set(username, password)

    # assign function to handle incoming messages
    if on_message is not None:
        client.on_message = on_message

    return client


def connect_client(client, timeout=12):
    """Connect an MQTT client to the broker"""

    # used to signal when the broker responds to the connection
    ready = Event()

    # stores connection errors returned by the broker
    status = {'error': None}

    # preserves the existing connection callback (if any) so it can be called later
    existing_callback = client.on_connect

    def on_connect(c, userdata, flags, reason_code, properties):
        """Handle the broker's connection response"""

        # checks if the broker rejected the connection
        if reason_code.is_failure:
            status['error'] = f'Broker rejected client: {reason_code}'

        # runs the original callback if connection was successful
        elif existing_callback:
            existing_callback(
                c, userdata, flags, reason_code, properties
            )

        # signals that the connection response has been received
        ready.set()

    # assigns the connection callback to the client
    client.on_connect = on_connect

    # connects to the MQTT broker
    client.connect(HOST, PORT, keepalive=30)

    # begins processing MQTT messages in the background
    client.loop_start()

    # waits for broker to respond
    if not ready.wait(timeout):
        raise TimeoutError('MQTT connection timed out')

    # raises an error if the broker rejects the connection
    if status['error']:
        raise ConnectionError(status['error'])


    return client
