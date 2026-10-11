"""Emulates an Eastron SDM230 (Modbus RTU, RS485) using data from a GM EM2289 (Modbus TCP)."""
import logging
import os
import struct

import serial
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# --- Configuration -----------------------------------------------------------
METER_HOST = '192.168.178.211'  # EM2289 Modbus TCP address
SERIAL_PORT = '/dev/ttyUSB0'    # RS485 adapter facing the inverter
BAUDRATE = 9600
SLAVE_ADDRESS = 1

# Optional MQTT publishing: enabled only if MQTT_HOST is set in the environment.
MQTT_HOST = os.environ.get('MQTT_HOST')
MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
MQTT_USER = os.environ.get('MQTT_USER')
MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD')
MQTT_TOPIC_PREFIX = os.environ.get('MQTT_TOPIC_PREFIX', 'pm_emulator')

# --- Modbus constants --------------------------------------------------------
READ_INPUT_REGISTERS = 0x04
REQUEST_LENGTH = 8

# Emulated SDM230 input registers
SDM230_POWER_REGISTER = 0x000C
SDM230_FREQUENCY_REGISTER = 0x0046

# Source registers on the EM2289
EM2289_POWER_REGISTER = 203
EM2289_FREQUENCY_REGISTER = 11

log = logging.getLogger('pm_emulator')


def calculate_crc16(data: bytes) -> bytes:
    """Modbus CRC16, returned little endian as required on the wire."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc.to_bytes(2, byteorder='little')


def _read_power(client: ModbusTcpClient) -> float:
    raw = client.read_input_registers(EM2289_POWER_REGISTER, 1).registers[0]
    signed = raw - 0x10000 if raw >= 0x8000 else raw  # int16
    return float(signed * 10)


def _read_frequency(client: ModbusTcpClient) -> float:
    return client.read_input_registers(EM2289_FREQUENCY_REGISTER, 1).registers[0] * 0.01


# SDM230 register -> (MQTT subtopic, reader for the corresponding EM2289 value)
READERS = {
    SDM230_POWER_REGISTER: ('power', _read_power),
    SDM230_FREQUENCY_REGISTER: ('frequency', _read_frequency),
}


def create_mqtt_client():
    """Return a connected-in-background MQTT client, or None if MQTT is not configured.

    paho's network loop runs in its own thread and reconnects on its own, so the
    serial loop never waits for the broker.
    """
    if not MQTT_HOST:
        return None
    import paho.mqtt.client as mqtt  # imported lazily: only needed when enabled

    try:
        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:  # paho-mqtt < 2.0
        mqttc = mqtt.Client()
    if MQTT_USER:
        mqttc.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    mqttc.reconnect_delay_set(min_delay=1, max_delay=60)
    mqttc.connect_async(MQTT_HOST, MQTT_PORT)
    mqttc.loop_start()
    log.info('MQTT publishing to %s:%d, prefix "%s"', MQTT_HOST, MQTT_PORT, MQTT_TOPIC_PREFIX)
    return mqttc


def publish(mqttc, subtopic: str, value: float) -> None:
    """Fire-and-forget publish; skipped while disconnected so nothing piles up."""
    if mqttc is None or not mqttc.is_connected():
        return
    try:
        mqttc.publish(f'{MQTT_TOPIC_PREFIX}/{subtopic}', f'{value:g}', qos=0)
    except Exception as exc:  # never let MQTT problems disturb the Modbus loop
        log.warning('MQTT publish failed: %s', exc)


def build_response(function_code: int, value: float) -> bytes:
    """Build an RTU response carrying `value` as big-endian IEEE754 float32."""
    payload = bytes([SLAVE_ADDRESS, function_code, 0x04]) + struct.pack('>f', value)
    return payload + calculate_crc16(payload)


def handle_read_request(request: bytes, client: ModbusTcpClient, ser: serial.Serial, mqttc=None) -> None:
    function_code = request[1]
    register = (request[2] << 8) | request[3]

    entry = READERS.get(register)
    if function_code != READ_INPUT_REGISTERS or entry is None:
        log.debug('Ignoring request: %s', request.hex(' '))
        return
    subtopic, reader = entry

    try:
        value = reader(client)
    except (ModbusException, AttributeError) as exc:  # AttributeError: error response has no .registers
        log.warning('Reading register 0x%04X from meter failed: %s', register, exc)
        return

    response = build_response(function_code, value)
    log.debug('Response: %s', response.hex(' '))
    ser.write(response)
    # Publish only after the inverter has its answer, so MQTT cannot add latency to it.
    publish(mqttc, subtopic, value)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    client = ModbusTcpClient(METER_HOST)
    mqttc = create_mqtt_client()
    with serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1,
    ) as ser:
        try:
            while True:
                request = ser.read(REQUEST_LENGTH)
                if len(request) == REQUEST_LENGTH:
                    handle_read_request(request, client, ser, mqttc)
        except KeyboardInterrupt:
            pass
        finally:
            client.close()
            if mqttc is not None:
                mqttc.loop_stop()
                mqttc.disconnect()


if __name__ == '__main__':
    main()
