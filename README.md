# Power Meter Emulator

## Description
The purpose of this script is to simulate an RS485 Modbus RTU Power Meter by using the data of an available power meter, in this case a GM EM2289.
The script emulates the registers of an EASTRON SDM230. It is designed to be used in conjunction with a Fox ESS converter.

## Optional MQTT output
If `MQTT_HOST` is set, every value served to the inverter is also published to an MQTT broker (requires `pip install paho-mqtt`). Without `MQTT_HOST`, MQTT is fully disabled and paho-mqtt is not needed.

| Variable | Default | Meaning |
|---|---|---|
| `MQTT_HOST` | – (disabled) | Broker host |
| `MQTT_PORT` | `1883` | Broker port |
| `MQTT_USER` / `MQTT_PASSWORD` | – | Optional credentials |
| `MQTT_TOPIC_PREFIX` | `pm_emulator` | Topics: `<prefix>/power` (W), `<prefix>/frequency` (Hz) |

The publish happens after the response was written to the RS485 bus, uses QoS 0, and runs on paho's own network thread. Values are dropped while the broker is unreachable, so MQTT cannot slow down or block the emulation. For the systemd service add e.g. `Environment=MQTT_HOST=192.168.178.10` to the `[Service]` section.

## Run as service
1. Create a systemd service file: `sudo nano /etc/systemd/system/pm_emulator.service`

2. Add the following contents to the file:
    ```
    [Unit]
    Description=PM Emulator Service
    After=multi-user.target

    [Service]
    Type=idle
    ExecStart=/usr/bin/python3.9 /home/pi/pm_emulator.py
    User=pi
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```

3. Save and close the file.

4. Reload the systemd daemon: `sudo systemctl daemon-reload`

5. Enable the service: `sudo systemctl enable pm_emulator.service`

6. Start the service: `sudo systemctl start pm_emulator.service`

7. Check the status of the service: `sudo systemctl status pm_emulator.service`

8. If everything is working correctly, the status should indicate that the service is active and running.

9. You can stop the service with `sudo systemctl stop pm_emulator.service`, disable it with `sudo systemctl disable pm_emulator.service`, and restart it with `sudo systemctl restart pm_emulator.service`.



## Sources
https://www.geeksforgeeks.org/python-program-to-represent-floating-number-as-hexadecimal-by-ieee-754-standard/

https://chat.openai.com/chat