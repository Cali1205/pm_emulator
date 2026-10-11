"""Emulates an Eastron SDM230 (Modbus RTU, RS485) using data from a GM EM2289 (Modbus TCP)."""
import logging
import struct

import serial
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# --- Configuration -----------------------------------------------------------
METER_HOST = '192.168.178.211'  # EM2289 Modbus TCP address
SERIAL_PORT = '/dev/ttyUSB0'    # RS485 adapter facing the inverter
BAUDRATE = 9600
SLAVE_ADDRESS = 1

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


# SDM230 register -> reader for the corresponding EM2289 value
READERS = {
    SDM230_POWER_REGISTER: _read_power,
    SDM230_FREQUENCY_REGISTER: _read_frequency,
}


def build_response(function_code: int, value: float) -> bytes:
    """Build an RTU response carrying `value` as big-endian IEEE754 float32."""
    payload = bytes([SLAVE_ADDRESS, function_code, 0x04]) + struct.pack('>f', value)
    return payload + calculate_crc16(payload)


def handle_read_request(request: bytes, client: ModbusTcpClient, ser: serial.Serial) -> None:
    function_code = request[1]
    register = (request[2] << 8) | request[3]

    reader = READERS.get(register)
    if function_code != READ_INPUT_REGISTERS or reader is None:
        log.debug('Ignoring request: %s', request.hex(' '))
        return

    try:
        value = reader(client)
    except (ModbusException, AttributeError) as exc:  # AttributeError: error response has no .registers
        log.warning('Reading register 0x%04X from meter failed: %s', register, exc)
        return

    response = build_response(function_code, value)
    log.debug('Response: %s', response.hex(' '))
    ser.write(response)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    client = ModbusTcpClient(METER_HOST)
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
                    handle_read_request(request, client, ser)
        except KeyboardInterrupt:
            pass
        finally:
            client.close()


if __name__ == '__main__':
    main()
