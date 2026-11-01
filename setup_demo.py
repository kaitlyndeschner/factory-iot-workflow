"""Generate random MQTT credentials for the factory simulation"""

from pathlib import Path
from secrets import token_urlsafe # generates cryptographically secure random values


# defines the project directory and environment file
ROOT = Path(__file__).parent
TARGET = ROOT / '.env'

# defines the accounts that require MQTT passwords
ACCOUNTS = (
    'DISPENSARY',
    'DECANT',
    'ELPO',
    'EOL',
    'WAREHOUSE',
    'GLO',
    'GROUP_LEADER_1',
    'GROUP_LEADER_2',
)

# reads existing credentials if the environment file exists
existing = TARGET.read_text(encoding='utf-8') if TARGET.exists() else ''

# identifies credentials already stored in the environment file
existing_keys = {
    line.split('=', 1)[0].strip()
    for line in existing.splitlines()
    if '=' in line and not line.lstrip().startswith('#')
}

# identifies accounts that do not have passwords
missing = [
    account
    for account in ACCOUNTS
    if f'MQTT_{account}_PASSWORD' not in existing_keys
]

# generates passwords only for accounts that are missing credentials
if missing:
    with TARGET.open('a', encoding='utf-8') as output:

        # adds new line if the existing file does not end with one
        if existing and not existing.endswith('\n'):
            output.write('\n')

        # generates and saves a random password for each missing account
        for account in missing:
            output.write(
                f'MQTT_{account}_PASSWORD={token_urlsafe(24)}\n'
            )

    print(
        f'Created {len(missing)} missing password(s) in .env. Please keep this file private.'
    )

else:
    # preserves existing passwords when all accounts are configured
    print('All credentials already exist in .env. No passwords changed.')

# reminds users which accounts can release protected production updates
print(
    'Only group leader accounts can publish production updates.'
)