"""event schema, routing and validation helpers"""

from datetime import datetime, timezone
from uuid import uuid4  # generate unique event IDs


DEPARTMENTS = ('dispensary', 'decant', 'elpo', 'eol', 'warehouse')
GLO = 'glo'  # group leader office

# accounts permitted to release protected announcements and production changes
GROUP_LEADERS = ('group_leader_1', 'group_leader_2')

ALL_DEPARTMENTS = DEPARTMENTS + (GLO,)

# events that require group leader authorisation
PROTECTED_EVENTS = (
    'PRODUCTION_SCHEDULE_UPDATED',
    'BATCH_CHANGE',
    'PRODUCTION_RESUMED'
)

# defines events that specific departments can generate
EVENTS = {
    'dispensary': (
        'SHORT_WEIGHTS_STARTED',
        'SHORT_WEIGHTS_COMPLETE'
    ),
    'decant': (
        'MIXING_STARTED',
        'MIXING_COMPLETE'
    ),
    'elpo': (
        'ELPO_STARTED',
        'ELPO_COMPLETE'
    ),
    'eol': (
        'EOL_STARTED',
        'EOL_COMPLETE'
    ),
    'warehouse': (
        'DECANT_DISPATCHED',
        'DECANT_DELIVERED',
        'DISPENSARY_DISPATCHED',
        'DISPENSARY_DELIVERED',
        'EOL_RECEIVED',
        'SHIPMENT_DISPATCHED'
    ),
    GLO: (
        'PRODUCTION_SCHEDULE_UPDATED',
        'BATCH_CHANGE',
        'BREAKDOWN_REPORTED',
        'PRODUCTION_RESUMED'
    ),
}

# inbound operational messages each department requires
INBOUND = {
    'dispensary': (
        'factory/events/warehouse/DISPENSARY_DISPATCHED',
        'factory/events/warehouse/DISPENSARY_DELIVERED',
    ),
    'decant': (
        'factory/events/warehouse/DECANT_DISPATCHED',
        'factory/events/warehouse/DECANT_DELIVERED',
        'factory/events/dispensary/SHORT_WEIGHTS_COMPLETE',
    ),
    'elpo': (
        'factory/events/decant/MIXING_COMPLETE',
    ),
    'eol': (
        'factory/events/elpo/ELPO_COMPLETE',
        'factory/events/warehouse/EOL_RECEIVED',
    ),
    'warehouse': (
        'factory/events/eol/EOL_COMPLETE',
    ),
}


def topic_for(
    source: str,
    event_type: str,
    department: str | None = None
) -> str:
    """return the MQTT topic used to publish event"""

    # ensures breakdown report comes from valid department
    if event_type == 'BREAKDOWN_REPORTED':
        if source not in DEPARTMENTS or (
            department is not None and department != source
        ):
            raise ValueError(
                'Breakdown must originate from the affected department'
            )

        # returns MQTT topic for breakdown reports
        return f'factory/breakdowns/{source}'

    if source not in EVENTS or event_type not in EVENTS[source]:
        raise ValueError(f'Unsupported event: {source}/{event_type}')

    if source == GLO:
        # publishes production schedule updates
        if event_type == 'PRODUCTION_SCHEDULE_UPDATED':
            return 'factory/glo/schedule'

        # batch changes and production resumption require a target department
        if department not in DEPARTMENTS:
            raise ValueError(f'{event_type} must target a department')

        # selects topic category based on the event type
        kind = 'batch' if event_type == 'BATCH_CHANGE' else 'resume'
        return f'factory/glo/{kind}/{department}'

    # returns the MQTT topic for department event
    return f'factory/events/{source}/{event_type}'


def valid_received_event(topic: str, event: dict) -> bool:
    """Check that received messages match expected MQTT topic"""

    # messages must be in Python dictionaries
    if not isinstance(event, dict):
        return False

    source = event.get('source')
    event_type = event.get('event_type')
    department = event.get('department') or None
    issued_by = event.get('issued_by')

    try:
        # checks the source, claimed group leader account and topic for protected production updates
        if event_type in PROTECTED_EVENTS:
            return (
                source == GLO
                and issued_by in GROUP_LEADERS
                and topic == topic_for(GLO, event_type, department)
            )

        # checks that breakdown reports come from relevant department
        if event_type == 'BREAKDOWN_REPORTED':
            return (
                source in DEPARTMENTS
                and issued_by == source
                and department == source
                and topic == topic_for(source, event_type, department)
            )

        return (
            source in DEPARTMENTS
            and issued_by == source
            and topic == topic_for(source, event_type)
        )

    # reject messages containing invalid source or event info
    except (ValueError, TypeError):
        return False


def subscriptions_for(department: str) -> tuple[str, ...]:
    """Return MQTT topics a department needs to subscribe to"""

    # GLO monitors production and breakdown events
    if department == GLO:
        return (
            'factory/events/#',
            'factory/breakdowns/+',
            'factory/glo/#'
        )

    # rejects unknown departmnets
    if department not in DEPARTMENTS:
        raise ValueError(f'Unknown department: {department}')

    return INBOUND[department] + (
        f'factory/breakdowns/{department}',
        'factory/glo/schedule',
        f'factory/glo/batch/{department}',
        f'factory/glo/resume/{department}',
    )


def make_event(
    source: str,
    event_type: str,
    *,
    batch_id: str = '',
    department: str | None = None,
    detail: str = '',
    schedule: str = '',
    issued_by: str = ''
) -> dict:
    """create production event with its associated info"""

    # check event has a valid MQTT topic
    topic_for(source, event_type, department)

    # create and return production message
    return {
        'event_id': str(uuid4()),
        # records current time and date in UTC
        'timestamp': datetime.now(timezone.utc).isoformat(
            timespec='seconds'
        ),

        'source': source,  # record which department issued the event
        'issued_by': issued_by or source,  # record account or department that issued event
        'event_type': event_type,
        'batch_id': batch_id,
        'department': department or '',
        'detail': detail,
        'schedule': schedule,
    }


def department_label(dept: str) -> str:
    """return department name in uppercase for display"""

    # displays GLO and EOL in uppercase consistently
    return 'GLO' if dept == GLO else dept.upper()