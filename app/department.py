"""Six autonomous department clients that simulate a factory production workflow using MQTT messages"""

import heapq
import itertools
import json
import os
from queue import Empty, Queue
import time

from app.model import (
    GLO, ALL_DEPARTMENTS, make_event, topic_for,
    subscriptions_for, department_label, valid_received_event
)
from mqtt import make_client, connect_client


class Department:
    def __init__(self, name):
        """Set up one department and its MQTT connection"""

        # create clients only for departments defined in model.py
        if name not in ALL_DEPARTMENTS:
            raise ValueError(f'Unknown department: {name}')

        self.name = name
        self.inbox = Queue()  # stores messages until they can be processed
        self.client = make_client(self.receive)
        self.client.on_connect = self.on_connect

        # stores actions that must run after a short delay
        self.tasks = []
        self.task_counter = itertools.count()

        # warehouse creates a new batch at regular intervals
        self.batch = 0
        self.next_batch = time.monotonic() + 5
        self.batch_interval = int(os.getenv('BATCH_INTERVAL_SECONDS', '60'))

        # decant must receive ingredients and short weights
        self.delivered_to_decant = set()
        self.weights_complete = set()
        self.mixing_started = set()

        # pause scheduled production if a breakdown is reported
        self.paused = False
        self.pending = []

    def on_connect(self, client, userdata, flags, reason_code, properties):
        """Subscribe to the topics needed by this department"""

        for topic in subscriptions_for(self.name):
            client.subscribe(topic, qos=1)

    def receive(self, client, userdata, msg):
        """Decode an MQTT message and add it to the inbox"""

        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            self.inbox.put((msg.topic, payload))
        except (UnicodeError, ValueError) as exc:
            print(
                f'[{department_label(self.name)}] Invalid JSON ignored: {exc}',
                flush=True
            )

    def schedule(self, delay, fn, *args):
        """Schedule a function to run after the given delay"""

        # counter keeps tasks in order when their times are the same
        heapq.heappush(
            self.tasks,
            (time.monotonic() + delay, next(self.task_counter), fn, args)
        )

    def publish(self, event_type, batch='', detail=''):
        """Create and publish a departmental production event"""

        payload = make_event(self.name, event_type, batch_id=batch, detail=detail)
        topic = topic_for(self.name, event_type)
        info = self.client.publish(topic, json.dumps(payload), qos=1)

        # MQTT permissions are enforced by Mosquitto's ACL file, so a department may be rejected if it tries to publish an event it is not allowed to send
        if info.rc != 0:
            raise RuntimeError(f'Failed to enqueue MQTT message: {info.rc}')

        print(
            f'[SENT {department_label(self.name)}] {event_type} | '
            f'batch={batch or "-"} | id={payload["event_id"][:8]}',
            flush=True
        )

    def start_batch(self):
        """Simulate Warehouse dispatching ingredients for a new batch"""

        self.batch += 1
        batch_id = f'B{self.batch:04d}'
        print(f'\n[WAREHOUSE] Beginning simulated batch {batch_id}', flush=True)

        # publish dispatch and delivery updates a few seconds apart to simulate the time taken for ingredients to be delivered to Dispensary and Decant
        self.publish('DISPENSARY_DISPATCHED', batch_id)
        self.schedule(1.0, self.publish, 'DISPENSARY_DELIVERED', batch_id)
        self.schedule(2.0, self.publish, 'DECANT_DISPATCHED', batch_id)
        self.schedule(3.0, self.publish, 'DECANT_DELIVERED', batch_id)

    def process(self, topic, event):
        """Check an incoming event and respond if it affects this department"""

        # reject messages that have a different source, event type, or MQTT topic
        if not valid_received_event(topic, event):
            print(
                f'[IGNORED {department_label(self.name)}] '
                f'Invalid event/topic/source combination on {topic}',
                flush=True
            )
            return

        event_type = event.get('event_type', '')
        batch = event.get('batch_id', '')
        source = event.get('source', '')
        print(
            f'[RECEIVED {department_label(self.name)}] {event_type} | '
            f'from={source} | batch={batch or "-"} | '
            f'id={event.get("event_id", "")[:8]}',
            flush=True
        )

        # department pauses when it receives its own breakdown report
        if event_type == 'BREAKDOWN_REPORTED' and event.get('department') == self.name:
            self.paused = True
            print(
                f'[PAUSED {department_label(self.name)}] '
                'Simulated breakdown; awaiting GLO resume',
                flush=True
            )
            return

        # only a protected GLO resume event releases the affected department(s) from a production pause
        if event_type == 'PRODUCTION_RESUMED' and event.get('department') == self.name:
            self.paused = False
            print(
                f'[RESUMED {department_label(self.name)}] '
                'GLO authorised resumption',
                flush=True
            )
            for fn, args in self.pending:
                self.schedule(0.2, fn, *args)
            self.pending.clear()
            return

        # dispensary starts weighing after Warehouse delivers its ingredients
        if self.name == 'dispensary' and event_type == 'DISPENSARY_DELIVERED' and batch:
            self.schedule(0.4, self.publish, 'SHORT_WEIGHTS_STARTED', batch)
            self.schedule(2.0, self.publish, 'SHORT_WEIGHTS_COMPLETE', batch)

        # decant only starts mixing after both deliveries are complete
        if self.name == 'decant' and batch:
            if event_type == 'DECANT_DELIVERED':
                self.delivered_to_decant.add(batch)
            elif event_type == 'SHORT_WEIGHTS_COMPLETE':
                self.weights_complete.add(batch)

            if (
                batch in self.delivered_to_decant
                and batch in self.weights_complete
                and batch not in self.mixing_started
            ):
                self.mixing_started.add(batch)
                self.schedule(0.6, self.publish, 'MIXING_STARTED', batch)
                self.schedule(2.4, self.publish, 'MIXING_COMPLETE', batch)

        # ELPO fills containers once Decant has completed mixing
        if self.name == 'elpo' and event_type == 'MIXING_COMPLETE' and batch:
            self.schedule(0.6, self.publish, 'ELPO_STARTED', batch)
            self.schedule(2.3, self.publish, 'ELPO_COMPLETE', batch)

        # EOL palletises and labels products after ELPO finishes filling
        if self.name == 'eol' and event_type == 'ELPO_COMPLETE' and batch:
            self.schedule(0.6, self.publish, 'EOL_STARTED', batch)
            self.schedule(2.3, self.publish, 'EOL_COMPLETE', batch)

        # Warehouse receives the completed pallet and dispatches the shipment
        if self.name == 'warehouse' and event_type == 'EOL_COMPLETE' and batch:
            self.schedule(0.7, self.publish, 'EOL_RECEIVED', batch)
            self.schedule(2.5, self.publish, 'SHIPMENT_DISPATCHED', batch)

    def main(self):
        """Connect to MQTT and keep the department simulation running"""

        connect_client(self.client)
        print(
            f'[READY {department_label(self.name)}] '
            'MQTT connected; waiting for production messages.',
            flush=True
        )

        try:
            while True:
                now = time.monotonic()

                # only Warehouse starts new batches automatically
                if self.name == 'warehouse' and now >= self.next_batch:
                    if not self.paused:
                        self.start_batch()
                    self.next_batch = now + self.batch_interval

                # run scheduled tasks, or hold them during a breakdown
                while self.tasks and self.tasks[0][0] <= now:
                    _, _, fn, args = heapq.heappop(self.tasks)
                    if self.paused:
                        self.pending.append((fn, args))
                    else:
                        fn(*args)

                # read incoming MQTT events
                try:
                    topic, event = self.inbox.get(timeout=0.15)
                except Empty:
                    continue
                self.process(topic, event)
        except KeyboardInterrupt:
            pass
        finally:
            # close the MQTT connection when the application stops
            self.client.disconnect()
            self.client.loop_stop()


if __name__ == '__main__':
    # docker provides the department name through an environment variable
    Department(os.environ['DEPARTMENT']).main()