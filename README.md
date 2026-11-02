
# Factory IoT Workflow Simulation

This university project simulates production updates between six departments in a food manufacturing plant: Warehouse, Dispensary, Decant, ELPO, End of Line (EOL) and Group Leader Office (GLO). Python applications exchange MQTT messages through an Eclipse Mosquitto broker, and Docker Compose runs the services together.

The project demonstrates live department communication, container deployment and MQTT access control. It uses simulated production data and does not connect to real factory machinery or production systems.

## Requirements

- Windows with Docker Desktop running in Linux container mode
- Python 3.11 or later for the setup script and local unit tests
- PowerShell or the VS Code terminal
- The project files downloaded or cloned into one folder

## 1. Installation and Setup

Open the project folder in VS Code, then open **Terminal > New Terminal**. Run the following commands from the folder containing `compose.yaml`:

```powershell
py setup_demo.py
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

`setup_demo.py` generates a local `.env` file with separate MQTT passwords for the department and Group Leader accounts. Existing passwords are preserved when you run the script again.

**Keep `.env` private.** Do not commit it to GitHub. The `.gitignore` and `.dockerignore` files help exclude sensitive local files from version control and Docker builds.

The `init-auth` service creates the Mosquitto password file and then finishes. Seeing **`Exited (0)`** for this service is normal. The broker and the six department containers should remain running.

### Viewing Live Production Events

To view live messages from all six departments:

```powershell
docker compose logs -f --tail=30 warehouse dispensary decant elpo eol glo
```

Warehouse starts a new simulated batch approximately every 60 seconds. Each batch has an identifier, such as `B0001`, which can be followed across the department logs.

Press **Ctrl+C** to stop viewing the logs. This does not stop the Docker containers.

## 2. Production Events

The simulation represents production activities across six departments.

| Department | Event | Description |
|---|---|---|
| Warehouse | `DISPENSARY_DISPATCHED` | Ingredients dispatched to Dispensary |
| Warehouse | `DISPENSARY_DELIVERED` | Ingredients delivered to Dispensary |
| Warehouse | `DECANT_DISPATCHED` | Ingredients dispatched to Decant |
| Warehouse | `DECANT_DELIVERED` | Ingredients delivered to Decant |
| Warehouse | `EOL_RECEIVED` | Finished pallets received from EOL |
| Warehouse | `SHIPMENT_DISPATCHED` | Finished products dispatched for shipment |
| Dispensary | `SHORT_WEIGHTS_STARTED` | Ingredient weighing and preparation started |
| Dispensary | `SHORT_WEIGHTS_COMPLETE` | Ingredient weighing and preparation completed |
| Decant | `MIXING_STARTED` | Dry ingredient mixing started |
| Decant | `MIXING_COMPLETE` | Dry ingredient mixing completed |
| ELPO | `ELPO_STARTED` | Product filling started |
| ELPO | `ELPO_COMPLETE` | Product filling completed |
| EOL | `EOL_STARTED` | Palletising and labelling started |
| EOL | `EOL_COMPLETE` | Palletising and labelling completed |
| GLO | `PRODUCTION_SCHEDULE_UPDATED` | Production schedule update issued |
| GLO | `BATCH_CHANGE` | Batch change issued to a selected department |
| Operational department | `BREAKDOWN_REPORTED` | Equipment breakdown reported to GLO |
| GLO | `PRODUCTION_RESUMED` | Production resumption authorised for a department |

The simulated workflow starts with ingredient and short weight deliveries, then continues through mixing, filling, palletising and shipment. Decant waits for its ingredient delivery and the completed short weights before starting mixing.

Group leader office (GLO) monitors department updates, while each operational department subscribes to the messages relevant to its work. Messages include an event identifier, timestamp, source department and, where applicable, a batch identifier.

When a breakdown is reported, the affected department pauses until an authorised group leader sends a production resumption message. An unrelated breakdown does not automatically pause Warehouse or EOL, although a department may still need to wait for a required earlier production event.

## 3. System Architecture

The project uses the **MQTT publish/subscribe model**. Each department runs as a separate Python application inside a Docker container. Applications publish events to Mosquitto, which sends them to permitted subscribers.

Docker Compose defines the services, credentials and private network. The broker's MQTT port is not published to the host computer.

The six departments are:

- **Warehouse:** Dispatches ingredients and handles completed products
- **Dispensary:** Weighs and prepares short weights
- **Decant:** Mixes ingredients
- **ELPO:** Fills containers
- **EOL:** Palletises and labels finished products
- **GLO:** Monitors production events and breakdowns

MQTT topics identify the source and type of message. For example:

```text
factory/events/decant/MIXING_COMPLETE
factory/breakdowns/elpo
factory/glo/schedule
factory/glo/batch/decant
factory/glo/resume/elpo
```

The files in `app/` contain the Python logic. `broker/mosquitto.conf` configures the broker, while `broker/aclfile` defines the topic permissions.

## 4. Group Leader Access Control

Only the two authorised group leader accounts can publish production schedule updates, batch changes and production resumption notices:

- `group_leader_1`
- `group_leader_2`

Each account has a separate password generated during setup. The `glo` account is for monitoring only and does not have permission to publish production changes.

### Account Permissions

| Account | Permissions |
|---|---|
| `group_leader_1` | Publish protected schedule, batch and resumption updates |
| `group_leader_2` | Publish protected schedule, batch and resumption updates |
| `glo` | Read-only monitoring of production and management events |
| Operational departments | Publish their own production events and breakdown reports; receive relevant notifications |

Mosquitto checks account credentials and enforces the topic permissions in `broker/aclfile`. The Python application also validates event information, but the broker ACL is the main control preventing unauthorised publishing.

These messages are notifications within the simulation. The program does not edit a real production scheduling database.

## 5. Manual Production Updates

Keep the simulation running and open a **second terminal** in the project folder.

Protected GLO commands ask for an authorised group leader username and password. The account passwords are stored in the local `.env` file.

### Production Schedule Update

Send a schedule update to all five operational departments:

```powershell
docker compose run --rm glo-cli schedule --batch B0001 --schedule "Friday 09:00" --detail "Batch B001 moved to Friday 09:00"
```

This publishes a `PRODUCTION_SCHEDULE_UPDATED` event.

### Batch Change

Send a batch change specifically to Decant:

```powershell
docker compose run --rm glo-cli batch-change --department decant --batch B0001 --detail "Switch to batch B0001 revision 2"
```

This publishes a `BATCH_CHANGE` event to the Decant topic.

### Breakdown Report

Report an equipment breakdown using the ELPO department account:

```powershell
docker compose run --rm elpo python -m app.cli breakdown --batch B0001 --reason "ELPO equipment stopped"
```

This publishes `BREAKDOWN_REPORTED`. ELPO should pause its scheduled production tasks until a resumption message is received. Other departments are not automatically paused.

### Production Resumption

Use a group leader account to authorise ELPO to resume:

```powershell
docker compose run --rm glo-cli resume --department elpo --batch B0001 --detail "Fault cleared, production may resume"
```

This publishes a targeted `PRODUCTION_RESUMED` event.

### Viewing Department Messages

Check the recent logs after issuing a command:

```powershell
docker compose logs --tail=40 dispensary decant elpo eol warehouse glo
```

### Automatic Schedule Updates

The simulation also supports optional automatic schedule announcements issued through an authenticated group leader session:

```powershell
docker compose run --rm glo-cli auto-schedule --count 2 --interval 30
```

This issues two schedule updates, 30 seconds apart. Ordinary production events run automatically, but automatic **schedule** changes are not enabled by default.

## 6. Security Testing

The project includes simple MQTT integration tests and Python unit tests.

### MQTT Security Tests

Start the Docker services before running:

```powershell
docker compose run --rm security-tests
```

The three integration tests check that:

1. The broker rejects a connection with an incorrect password
2. Decant cannot publish protected schedule, batch-change or production-resumption updates
3. An authorised group leader can publish a schedule update that dispensary receives

If all three tests succeed, the expected summary is:

```text
RESULT: 3/3 PASSED
```

### Python Unit Tests

Run the unit tests from the project folder:

```powershell
py -m unittest discover -s tests -v
```

The four unit tests check:

- Correct MQTT topic generation
- Rejection of an unsupported event
- Validation of a protected group leader event
- Decant's required subscriptions

These tests examine `app/model.py` and do not need a running MQTT broker.

## 7. Project Limitations

This is a local educational simulation, not a production-ready industrial control system.

Current limitations include:

- No connection to physical factory equipment
- No integration with existing factory systems
- MQTT communication is not encrypted using TLS
- A single MQTT broker is a potential point of failure
- Production data and events are simulated
- Demonstration accounts are used instead of an organisational identity system
- Schedule changes are notifications rather than persistent database updates
- Administrators who control Docker or the local credentials are outside the MQTT account-permission model
- The integration tests cover selected cases rather than a full security assessment

A real factory deployment would need additional security controls, fault tolerance, monitoring, testing and integration with existing production systems.

## 8. Useful Commands

### Check Container Status

```powershell
docker compose ps
```

### View Recent Logs

```powershell
docker compose logs --tail=50
```

### Restart the Application

```powershell
docker compose down
docker compose up -d
```

### Stop the Application

```powershell
docker compose down
```

### Reset Local Authentication Data

If you want to reset the locally stored broker passwords, stop the simulation and remove the project's named volumes:

```powershell
docker compose down -v
```

**Warning:** This removes the project's Docker volumes, including its stored MQTT password hashes. Do not use it if you need to keep that data.

To generate entirely new credentials, delete the local `.env` file, then run:

```powershell
py setup_demo.py
docker compose up --build -d
```

Do not delete `.env` if you want to keep the existing passwords.

## 9. Documentation

| File | Description |
|---|---|
| `README.md` | Project overview and setup instructions |
| `compose.yaml` | Docker Compose services and network configuration |
| `Dockerfile` | Python application image configuration |
| `setup_demo.py` | Generates local MQTT account passwords |
| `app/model.py` | Event definitions, topics and validation |
| `app/department.py` | Simulated department behaviour |
| `app/cli.py` | Manual Group Leader commands and breakdown reporting |
| `app/security_tests.py` | Three MQTT integration tests |
| `tests/test_model.py` | Four Python unit tests |
| `broker/mosquitto.conf` | Mosquitto broker configuration |
| `broker/aclfile` | MQTT topic access-control rules |