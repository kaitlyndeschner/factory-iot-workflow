"""Test factory events, MQTT topics and message validation"""

import unittest

from app.model import (
    make_event,
    topic_for,
    valid_received_event,
    subscriptions_for
)

class TestFactoryModel(unittest.TestCase):
    """Test the factory event model"""

    def test_event_topic(self):
        """Check that departments use the correct MQTT topics"""

        topic = topic_for('decant', 'MIXING_COMPLETE')

        self.assertEqual(
            topic,
            'factory/events/decant/MIXING_COMPLETE'
        )

    def test_invalid_event(self):
        """Check that unsupported events are rejected"""

        with self.assertRaises(ValueError):
            topic_for('decant', 'ELPO_COMPLETE')

    def test_group_leader_validation(self):
        """Check that protected updates require a group leader"""

        # creates an authorised batch change
        event = make_event(
            'glo',
            'BATCH_CHANGE',
            department='decant',
            issued_by='group_leader_1'
        )

        topic = topic_for('glo', 'BATCH_CHANGE', 'decant')

        # checks that the authorised event is valid
        self.assertTrue(valid_received_event(topic, event))

        # changes the claimed issuer to an unauthorised account
        event['issued_by'] = 'decant'

        # checks that the modified event is rejected
        self.assertFalse(valid_received_event(topic, event))

    def test_department_subscriptions(self):
        """Check that decant receives relevant notifications"""

        topics = subscriptions_for('decant')

        # decant needs completed short weights updates
        self.assertIn(
            'factory/events/dispensary/SHORT_WEIGHTS_COMPLETE',
            topics
        )

        # all departments need production schedule updates
        self.assertIn(
            'factory/glo/schedule',
            topics
        )


if __name__ == '__main__':
    unittest.main()