"""Handle manual production updates and group leader authentication"""

import argparse
from getpass import getpass
import json
import os
from queue import Empty, Queue
import time

from app.model import (
    GLO, GROUP_LEADERS, DEPARTMENTS, make_event, topic_for
)
from app.mqtt import connect_client, make_client


# production changes that only authorised group leaders can release
PROTECTED = (
    'PRODUCTION_SCHEDULE_UPDATED',
    'BATCH_CHANGE',
    'PRODUCTION_RESUMED'
)


def authenticate_for(action):
    """Checks the account used to send a production update"""

    # request a username, if one has not been provided
    if not os.getenv('MQTT_USERNAME'):
        os.environ['MQTT_USERNAME'] = input(
            'MQTT username (group_leader_1 or group_leader_2): '
        ).strip()

    # request the password without displaying it on the screen
    if not os.getenv('MQTT_PASSWORD'):
        os.environ['MQTT_PASSWORD'] = getpass(
            'MQTT password (not displayed): '
        )

    username = os.environ['MQTT_USERNAME']

    # only grouo leaders can release protected production updates
    if action in PROTECTED and username not in GROUP_LEADERS:
        raise PermissionError(
            'Only group leaders can release production schedules, batch changes or resume production.'
        )

    # only operational departments can report breakdowns
    if action == 'BREAKDOWN_REPORTED' and username not in DEPARTMENTS:
        raise PermissionError(
            'Only operational departments can report breakdowns.'
        )
    
    return username


def publish(
    event_type,
    *,
    department=None,
    batch='',
    detail='',
    schedule=''
):
    """Publish production updates to the MQTT broker"""

    # checks whether the account can request this type of update
    actor = authenticate_for(event_type)

    # protected messages must originate from GLO; breakdown reports originate from the affected department
    source = GLO if event_type in PROTECTED else actor

    # breakdown reports must identify the affected department
    target = actor if event_type == 'BREAKDOWN_REPORTED' else department

    # creates the production event using the shared event model
    payload = make_event(
        source,
        event_type,
        department=target,
        batch_id=batch,
        detail=detail,
        schedule=schedule,
        issued_by=actor
    )

    # determine which MQTT topic the message should use
    topic = topic_for(source, event_type, target)

    #creates an authenticated MQTT client
    client = make_client()

    # stores responses from the MQTT broker
    pubacks = Queue()

    # records the broker's response when a message is published
    client.on_publish = lambda c, userdata, mid, reason, props: (
        pubacks.put((mid, reason))
    )

    # establishes the MQTT connection
    connect_client(client)

    try:
        # converts event into JSON, then publishes it
        info = client.publish(
            topic,
            json.dumps(payload),
            qos=1
        )

        # checks whether the publish request was accepted locally
        if info.rc != 0:
            raise RuntimeError(
                f'MQTT publish request failed: {info.rc}'
            )

        # waits for broker to acknowledge the message
        try:
            mid, reason = pubacks.get(timeout=7)

        except Empty as exc:
            raise TimeoutError(
                'No MQTT acknowledgement received.'
            ) from exc

        # checks whether the broker rejected the publication
        if mid != info.mid or reason.is_failure:
            raise PermissionError(
                f'MQTT broker refused the update: {reason}'
            )

        # displays confirmation of the published event
        print(
            f'SENT | {event_type} | by={actor} | '
            f'topic={topic} | batch={batch or "-"} | '
            f'id={payload["event_id"]}',
            flush=True
        )

        print(
            'Broker acknowledged the message. Check department logs to confirm delivery.',
            flush=True
        )

    finally:
        # disconnects from MQTT and stops the network thread
        client.disconnect()
        client.loop_stop()


def main():
    """Process commands entered through the terminal"""

    # creates the command-line interface
    parser = argparse.ArgumentParser(
        description='Factory MQTT production communication simulation'
    )

    # defines the available commands
    sub = parser.add_subparsers(
        dest='action',
        required=True
    )

    # allows group leaders to post production schedule changes
    schedule = sub.add_parser(
        'schedule',
        help='Release a production schedule update.'
    )
    schedule.add_argument('--batch', default='B0001')
    schedule.add_argument('--schedule', required=True)
    schedule.add_argument(
        '--detail',
        default='Production schedule amended'
    )

    # allows group leaders to issue batch changes to a single department
    batch = sub.add_parser(
        'batch-change',
        help='Release a batch change to one department.'
    )
    batch.add_argument(
        '--department',
        choices=DEPARTMENTS,
        required=True
    )
    batch.add_argument('--batch', required=True)
    batch.add_argument('--detail', required=True)

    # allows operational departments to report breakdowns
    breakdown = sub.add_parser(
        'breakdown',
        help='Report an equipment breakdown to the group leader office.'
    )
    breakdown.add_argument('--batch', default='')
    breakdown.add_argument('--reason', required=True)

    # allows group leaders to authorise production resumption
    resume = sub.add_parser(
        'resume',
        help='Authorise production to resume.'
    )
    resume.add_argument(
        '--department',
        choices=DEPARTMENTS,
        required=True
    )
    resume.add_argument('--batch', default='')
    resume.add_argument(
        '--detail',
        default='Production authorised to resume'
    )

    # allows group leaders to simulate automatic schedule changes
    automatic = sub.add_parser(
        'auto-schedule',
        help='Generate simulated production schedule updates.'
    )
    automatic.add_argument('--count', type=int, default=2)
    automatic.add_argument('--interval', type=int, default=30)

    # reads the command and its arguments
    args = parser.parse_args()

    # publishes the event associated with the selected command
    if args.action == 'schedule':
        publish(
            'PRODUCTION_SCHEDULE_UPDATED',
            batch=args.batch,
            detail=args.detail,
            schedule=args.schedule
        )

    elif args.action == 'batch-change':
        publish(
            'BATCH_CHANGE',
            department=args.department,
            batch=args.batch,
            detail=args.detail
        )

    elif args.action == 'breakdown':
        publish(
            'BREAKDOWN_REPORTED',
            batch=args.batch,
            detail=args.reason
        )

    elif args.action == 'resume':
        publish(
            'PRODUCTION_RESUMED',
            department=args.department,
            batch=args.batch,
            detail=args.detail
        )

    # creates automatic schedule changes when requested
    else:
        # reject invalid simulation settings
        if args.count < 1 or args.interval < 3:
            parser.error(
                'auto-schedule requires count >= 1 and interval >= 3'
            )

        # authenticates the group leader before starting
        authenticate_for('PRODUCTION_SCHEDULE_UPDATED')

        # publishes the requested number of schedule updates
        for i in range(args.count):
            publish(
                'PRODUCTION_SCHEDULE_UPDATED',
                batch=f'AUTO-{i + 1:02d}',
                schedule=f'Demo schedule revision {i + 1}',
                detail='Simulated production schedule change'
            )

            # wait between updates, except after the final message
            if i + 1 < args.count:
                time.sleep(args.interval)


# run the command-line interface when the file is executed
if __name__ == '__main__':
    main()