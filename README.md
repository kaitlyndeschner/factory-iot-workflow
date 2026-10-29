# factory-iot-workflow
An Industrial IoT workflow prototype for real-time communication and event-driven coordination between departments in a food manufacturing facility.

This project is a small local IoT simulation, not a production factory system. It demonstrates:

IoT communication: Six simulated departments exchange timely MQTT events.
Automation: A compose.yaml file starts the same containerised services with one command.
Cybersecurity: Password authentication, department-specific topic permissions and actual MQTT security tests.
Critical evaluation: Limits such as lack of TLS, a single broker, simulated events and no machine integration.
No dashboard, frontend, SAP, Excel or other features are included. The terminal logs are the demonstration. Decant is the dry-ingredient mixing department.

1. Start on Windows
Requirements: Docker Desktop (running in Linux-container mode); Python installed so py works. You do not need to install Python packages on Windows, because the apps run inside Docker.

Open PowerShell, then run these commands from the folder containing compose.yaml:
cd "FILE_PATH"
dir
py setup_demo.py
docker compose up --build -d
docker compose ps
The first setup command creates new, random passwords in .env and will not overwrite existing ones. Never show .env in a screenshot or put it on GitHub. init-auth is a one-shot container that should finish successfully and may appear as Exited (0); the broker and six department containers should be running.

If PowerShell says py is missing but you have Python 3 installed, try python setup_demo.py instead. If Docker cannot start, open Docker Desktop first.

Live production logs
docker compose logs -f --tail=30 warehouse dispensary decant elpo eol group-leader-office
Wait about 20 seconds for a whole simulated production chain to appear. A new batch begins approximately every 60 seconds. A matching batch ID (e.g. B0001) should appear across departments. Press Ctrl+C to leave log-following mode; this does not stop Docker.

Sender	Event names	Main recipients
Dispensary	SHORT_WEIGHTS_STARTED, SHORT_WEIGHTS_COMPLETE	Decant receives SHORT_WEIGHTS_COMPLETE; Office monitors both
Decant	MIXING_STARTED, MIXING_COMPLETE	ELPO receives MIXING_COMPLETE; Office monitors both
ELPO	ELPO_STARTED, ELPO_COMPLETE	EOL receives ELPO_COMPLETE; Office monitors both
EOL	EOL_STARTED, EOL_COMPLETE	Warehouse receives EOL_COMPLETE; Office monitors both
Warehouse	DISPENSARY_DISPATCHED, DISPENSARY_DELIVERED, DECANT_DISPATCHED, DECANT_DELIVERED, EOL_RECEIVED, SHIPMENT_DISPATCHED	Relevant recipient (Dispensary, Decant, EOL) and Office
Group Leader Office	PRODUCTION_SCHEDULE_UPDATED, BATCH_CHANGE, BREAKDOWN_REPORTED, PRODUCTION_RESUMED	Schedules go to all, batch/resume notices go to the selected department, breakdowns are reported to Group Leader Office
The breakdown report is sent by the affected department and received by the Group Leader Office. The group leader authorises production resumption. The group leader also receives other departmental events for coordination.

Example event chain
WAREHOUSE:    DISPENSARY_DISPATCHED -> DISPENSARY_DELIVERED
WAREHOUSE:    DECANT_DISPATCHED     -> DECANT_DELIVERED
DISPENSARY:   SHORT_WEIGHTS_STARTED -> SHORT_WEIGHTS_COMPLETE
DECANT:       MIXING_STARTED        -> MIXING_COMPLETE
ELPO:         ELPO_STARTED          -> ELPO_COMPLETE
EOL:          EOL_STARTED           -> EOL_COMPLETE
WAREHOUSE:    EOL_RECEIVED          -> SHIPMENT_DISPATCHED
The events are generated using simulated delays; real ingredient handling and production do not occur. The group leader office prints updates for all five operational departments.

2. Group Leader Office — manual updates (no user interface)
Run these commands from a second PowerShell window while the containers are running.

A. Change the weekly production schedule — broadcast to all departments:

docker compose run --rm office-cli schedule --batch B0001 --schedule "Friday 09:00" --detail "Production moved to Friday morning"
B. Notify Decant about a batch change — only Decant receives this target topic:

docker compose run --rm office-cli batch-change --department decant --batch B0001 --detail "Switch to batch B0001 revision 2"
C. Simulate an equipment breakdown reported by ELPO to the Office:

docker compose run --rm elpo python -m app.cli breakdown --batch B0001 --reason "Filling equipment stopped"
The ELPO subscriber also receives its own breakdown notice and pauses further simulated processing. Group Leader Office receives the report.

D. Office notifies ELPO that production can resume:

docker compose run --rm office-cli resume --department elpo --batch B0001 --detail "Fault cleared, production may resume"
E. OPTIONAL — automatically generate two schedule changes:

docker compose run --rm office-cli auto-schedule --count 2 --interval 30
Automatic production events run by default; automatic schedule updates are off until you run the command above, making it easier to demonstrate manual changes without interference.

After each command, check receiving logs:

docker compose logs --tail=35 dispensary decant elpo eol warehouse group-leader-office
Messages are not retained if a receiving department is offline; the simulation does not implement an industrial scheduling database or guaranteed replay. The commands publish notifications, not persistent, authoritative schedule records. Batch changes are informational; they do not rewrite the already-running batch sequence.

3. Run real MQTT security checks
docker compose run --rm security-tests
The code tests these four behaviours against the running broker:

A client with a wrong password is rejected.
A TM account cannot publish a production schedule change.
Production schedule updates reaches all five operational departments.
A targeted Decant batch change is accessible to Decant, but EOL cannot subscribe to Decant's private batch topic.
The expected output is RESULT: 4/4 PASSED only if your own integration test completes successfully. The tests use MQTT version 5.0 acknowledgements and subscriptions, not just mock logic.

4. Cybersecurity and scope limitations for critical evaluation
Authentication and authorisation: Mosquitto denies anonymous connections and uses a hashed password database plus per-user topic read/write ACLs. Only Group Leader Office can publish schedule, batch change and resumption notices; the affected department can publish a breakdown report.
MQTT broker is not published outside Docker. No web dashboard or host-exposed port is needed.
No MQTT TLS: network traffic is not encrypted on the private Docker bridge. A real industrial deployment needs encryption and protected credentials.
Single broker: this is a possible availability failure point. There is no redundancy, message persistence, external identity provider or hardware integration.
Simulated automation: MQTT notifications are independent of physical machinery. The system does not validate actual operator permissions or manage a real production schedule. The simple pause/resume behaviour is educational only.
Repeatability: Compose definitions make it easy to restart the same services, but this alone does not prove a speed, resilience or energy-efficiency benefit.
Never connect this project to production systems. It is only for a local academic demonstration.

5. Useful commands
# Show container status
docker compose ps

# Read the most recent logs without leaving PowerShell in follow mode
docker compose logs --tail=50

# Stop and redeploy with the same configuration (for reproducibility evidence)
docker compose down
docker compose up -d

# Stop the project when finished
docker compose down

# Run purely local Python unit tests (without Docker, if Python is installed)
py -m unittest discover -s tests -v
If you see a credential error after changing .env, passwords inside the existing Docker auth volume must be regenerated too. For a fresh local reset, run docker compose down -v, delete .env, and rerun py setup_demo.py then docker compose up --build -d. This removes only this project's named Docker volume.
