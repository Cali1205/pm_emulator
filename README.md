# Power Meter Emulator

## Desictiption
The purpose of this script is to simulate an RS485 Modbus RTU Power Meter by using the data of an available power meter, in this case a GM EM2289.
The script emulates the registers of an EASTRON SDM230. It is designed to be used in conjunction with a Fox ESS converter.

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



## Soruces
https://www.geeksforgeeks.org/python-program-to-represent-floating-number-as-hexadecimal-by-ieee-754-standard/
https://chat.openai.com/chat