import serial

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException

# create Modbus TCP client
client = ModbusTcpClient('192.168.178.211')
# Define Modbus slave address
SLAVE_ADDRESS = 1

# Define Modbus register addresses for SDM230 meter
POWER_REGISTER = 0x000C
FREQUENCY_REGISTER = 0x0046

# Create serial connection
ser = serial.Serial(
    port='/dev/ttyUSB0', # Change this to the appropriate serial port
    baudrate=9600, # Change this to the appropriate baudrate
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

def _calculate_crc16(data):
    crc = 0xFFFF
    for i in range(len(data)):
        crc ^= data[i]
        for j in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder='little')

# Function for converting decimal to binary
def float_bin(my_number, places = 3):
    my_whole, my_dec = str(my_number).split(".")
    my_whole = int(my_whole)
    res = (str(bin(my_whole))+".").replace('0b','')
 
    for x in range(places):
        my_dec = str('0.')+str(my_dec)
        temp = '%1.20f' %(float(my_dec)*2)
        my_whole, my_dec = temp.split(".")
        res += my_whole
    return res

# Function for converting decimal IEEE754 format
def IEEE754(n):
    # identifying whether the number
    # is positive or negative
    sign = 0
    if n < 0 :
        sign = 1
        n = n * (-1)
    p = 30
    # convert float to binary
    dec = float_bin (n, places = p)
 
    dotPlace = dec.find('.')
    onePlace = dec.find('1')
    # finding the mantissa
    if onePlace > dotPlace:
        dec = dec.replace(".","")
        onePlace -= 1
        dotPlace -= 1
    elif onePlace < dotPlace:
        dec = dec.replace(".","")
        dotPlace -= 1
    mantissa = dec[onePlace+1:]
 
    # calculating the exponent(E)
    exponent = dotPlace - onePlace
    exponent_bits = exponent + 127
 
    # converting the exponent from
    # decimal to binary
    exponent_bits = bin(exponent_bits).replace("0b",'')
 
    mantissa = mantissa[0:23]
 
    # the IEEE754 notation in binary    
    final = str(sign) + exponent_bits.zfill(8) + mantissa
 
    # convert the binary to hexadecimal
    hstr = '0x%0*X' %((len(final) + 3) // 4, int(final, 2))
    return (hstr, final)

# Function to handle Modbus read request
def handle_read_request(request):
    # Extract Modbus function code and register address from request
    function_code = request[1]
    register_address = (request[2] << 8) | request[3]

    # Check if request is for power register
    if function_code == 0x04 and register_address == POWER_REGISTER:
        # Read power value from EM2289 Meter
        result = client.read_input_registers(203, 1) 
        value = result.registers[0]
        value = (value if value < 32768 else value  - 65536) * 10 

        
    if function_code == 0x04 and register_address == FREQUENCY_REGISTER:
        # Read frequency value from EM2289 Meter
        result = client.read_input_registers(11, 1)
        value = result.registers[0] * 0.01

    # Convert frequency value to bytes
    data_bytes = IEEE754(float(value))[0]
    data_bytes = bytes.fromhex(data_bytes[2:])

    # Construct response data
    response_data = bytes([SLAVE_ADDRESS, function_code, 0x04]) + data_bytes

    # Calculate CRC16 error check
    crc16 = _calculate_crc16(response_data)

    response_message = response_data + int.from_bytes(crc16, byteorder='big').to_bytes(length=2, byteorder='big')
    
    #print('Response:', ' '.join([hex(b)[2:].zfill(2) for b in response_message]))

    # Send response message to Modbus master
    ser.write(response_message)

# Main function to read Modbus requests
def read_modbus_requests():
    try:
        while True:
            request = ser.read(8)
            #print('Received data:', ' '.join([hex(b)[2:].zfill(2) for b in request]))
            if len(request) == 8:
                handle_read_request(request)
    except KeyboardInterrupt:
        ser.close()

# Call main function
read_modbus_requests()
