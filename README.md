# Factory IoT Workflow Simulation

This project simulates production updates between six departments in a food manufacturing factory: Warehouse, Dispensary, Decant, ELPO, End of Line (EOL) and Group Leader Office (GLO). Python applications publish and receive MQTT messages through an Eclipse Mosquitto broker. Docker Compose runs the services together on a local computer.

The simulation is intended for testing messaging, deployment and access control. It does not connect to factory machinery or production systems.

## Requirements

- Windows with Docker Desktop running in Linux container mode
- Python 3 (for the initial setup script)
- PowerShell or a VS Code terminal

## 1. Installation and Setup

Extract the project folder, open PowerShell and run:

```powershell
cd "FILE_PATH"
py setup_demo.py
docker compose up --build -d
docker compose ps
```

`setup_demo.py` creates a `.env` file containing separate passwords for each MQTT account. It does not replace existing credentials unless instructed.

The `.env` file should remain private and must not be uploaded to a public GitHub repository.

The `init-auth` service generates the MQTT broker password file and then exits. An `Exited (0)` status is normal. The broker and six department services should remain running.

### Viewing Live Production Events

To follow the live messages:

```powershell
docker compose logs -f --tail=30 warehouse dispensary decant elpo eol glo
```

Events are generated automatically. Warehouse starts a new simulated batch approximately every 60 seconds.

Each batch is assigned an identifier that can be followed through the departments' logs to track production updates.

Press `Ctrl+C` to stop following the logs. The containers will continue running.

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
| GLO | `BATCH_CHANGE` | Production batch change issued |
| Department | `BREAKDOWN_REPORTED` | Equipment breakdown reported to GLO |
| GLO | `PRODUCTION_RESUMED` | Production authorised to resume |

The simulated production process moves from ingredient delivery and weighing to mixing, filling, palletising and shipment.

GLO receives departmental updates, while other departments receive notifications relevant to their operations.

Messages include an event identifier, timestamp, source department and, where applicable, a batch identifier.

## 3. System Architecture

The system uses MQTT publish/subscribe communication.

Each department operates as an independent containerised application. Production messages are published to the MQTT broker and distributed to authorised subscribers.

Docker Compose manages the application services and their networking configuration.

The six departments are:

- **Warehouse:** Supplies ingredients to production departments and handles finished products.
- **Dispensary:** Weighs and prepares ingredients for Decant.
- **Decant:** Mixes dry ingredients.
- **ELPO:** Fills products into packaging.
- **EOL:** Palletises, labels and prepares finished products for Warehouse.
- **GLO:** Coordinates production schedules, communicates batch changes, monitors breakdowns and authorises production resumption.

MQTT topics and access-control rules determine which departments can publish and receive specific messages.

## 4. Group Leader Access Control

Production schedule updates, batch changes and production-resumption notices can only be published using authorised Group Leader accounts.

Two demonstration accounts are configured:

- `group_leader_1`
- `group_leader_2`

Each account has a separate password generated during setup.

### Account Permissions

| Account | Permissions |
|---|---|
| `group_leader_1` | Publish schedule changes, batch changes and production-resumption notices |
| `group_leader_2` | Publish schedule changes, batch changes and production-resumption notices |
| `glo` | Read-only monitoring of departmental production events |
| Department accounts | Publish departmental events, report breakdowns and receive relevant updates |

The MQTT broker enforces authentication and topic permissions using the rules defined in `broker/aclfile`.

Department accounts cannot publish protected group leader updates.

The simulation distributes production notifications but does not maintain or modify a real production scheduling database.

## 5. Manual Production Updates

Open a second PowerShell window in the project directory to send manual production updates.

Protected commands require authentication using an authorised Group Leader account.

### Production Schedule Update

```powershell
docker compose run --rm glo-cli schedule --batch B0001 --schedule "Friday 09:00" --detail "Production moved to Friday morning"
```

This publishes a `PRODUCTION_SCHEDULE_UPDATED` event to all departments.

### Batch Change

```powershell
docker compose run --rm glo-cli batch-change --department decant --batch B0001 --detail "Switch to batch B0001 revision 2"
```

This publishes a `BATCH_CHANGE` event to Decant.

### Breakdown Report

```powershell
docker compose run --rm elpo python -m app.cli breakdown --batch B0001 --reason "ELPO equipment stopped"
```

This allows ELPO to report an equipment breakdown to GLO.

### Production Resumption

```powershell
docker compose run --rm glo-cli resume --department elpo --batch B0001 --detail "Fault cleared, production may resume"
```

This publishes a `PRODUCTION_RESUMED` notification to ELPO following Group Leader authorisation.

### Viewing Department Messages

```powershell
docker compose logs --tail=40 dispensary decant elpo eol warehouse glo
```

### Automatic Schedule Updates

The system also supports simulated schedule updates.

```powershell
docker compose run --rm glo-cli auto-schedule --count 2 --interval 30
```

This generates two schedule updates at 30-second intervals following group leader authentication.

Automatic production events run by default. Automatic schedule updates must be triggered separately.

## 6. Security Testing

The project includes MQTT integration tests for authentication, access control and message delivery.

Run:

```powershell
docker compose run --rm security-tests
```

The security tests verify:

1. MQTT connections using incorrect passwords are rejected.
2. Department accounts and the read-only GLO account cannot publish protected production updates.
3. Authorised Group Leader accounts can publish schedule, batch and resumption updates.
4. Production schedule updates reach all five operational departments.
5. Batch changes reach the selected department without being distributed to unrelated departments.
6. Breakdown reports are delivered to GLO.

The expected output is:

```text
RESULT: 6/6 PASSED
```

Actual results should be verified against the running MQTT broker.

### Python Unit Tests

Run:

```powershell
py -m unittest discover -s tests -v
```

These tests check the application's local event-processing and message-routing logic.

## 7. Project Limitations

This project is a local IoT simulation rather than a production-ready industrial control system.

Current limitations include:

- No connection to physical industrial equipment.
- No integration with SAP or existing factory systems.
- MQTT communication does not currently use TLS encryption.
- A single MQTT broker represents a potential point of failure.
- Production data and events are simulated.
- Demonstration accounts are used for authentication.
- Schedule updates are notifications rather than persistent changes to a scheduling database.
- Docker administrators with access to the local credentials are outside the MQTT account-permission model.

Additional controls, including encrypted communication, monitoring, redundancy and integration testing, would be required before the system could be considered for use in a real manufacturing environment.

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

If MQTT credentials are changed, the broker authentication volume may need to be reset.

```powershell
docker compose down -v
```

This removes the project's stored authentication data.

After deleting the existing `.env` file, credentials can be generated again:

```powershell
py setup_demo.py
docker compose up --build -d
```

The reset command should only be used when the existing local authentication data is no longer required.

## 9. Documentation

| File | Description |
|---|---|
| `README.md` | Project overview and setup instructions |
| `compose.yaml` | Docker Compose service configuration |
| `setup_demo.py` | MQTT credential setup |
| `broker/mosquitto.conf` | MQTT broker configuration |
| `broker/aclfile` | MQTT access-control rules |
| `TEST_RESULTS.md` | Test results and observations |
