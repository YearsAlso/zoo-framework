class MobileSignalConstant:
    MOBILE_READ_SIGNAL_DECIBEL = b'AT+CSQ\r\n'
    MOBILE_READ_SIGNAL_CONNECTED = b'AT+CREG?\r\n'