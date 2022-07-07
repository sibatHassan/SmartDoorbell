########################################################################################################################
##   Server – Technical Project (CMPE2965)
##   Video transmission to Mobile App, audio transmission to Mobile App, audio reception from Mobile App,
#    send notification to Mobile App and receive control signal from Mobile App
##   Author:                 Sibat Hassan
##   Created On:             20 March, 2022
##   Submission Date:        NA
########################################################################################################################
import cv2
import imutils
import socket
import time
import base64
import threading
import pyaudio
import wave
import pickle
import struct
import RPi.GPIO as GPIO
import I2C_LCD_Driver

# LCD Test String
lcd = I2C_LCD_Driver.lcd()
lcd.lcd_display_string("Smart Doorbell",1)

# GPIO Ports
PIR = 11
SOL = 12
LED = 13
BUTTON = 16
BUZZER = 18

# Raspberry Pi GPIO Setup
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(PIR, GPIO.IN)
GPIO.setup(SOL, GPIO.OUT)
GPIO.setup(LED, GPIO.OUT)
GPIO.setup(BUTTON, GPIO.IN)
GPIO.setup(BUZZER, GPIO.OUT)

# Flags for threads and Raspberry Pi GPIO pins
Click = 0
Wait = 0
Switch = False
Play = True

# Raspberry Pi IP Address
host_ip = '192.168.137.42'

# Global flag for transmitting server audio in a background thread
transmitAudio = False

# Global flag for receiving Mobile App audio in a background thread
receiveAudio = False

# Notification
notify = False
notificationMessage = ''

# Ring Doorbell
runRingThread = False


# Transmit Video Thread
def TransmitVideo(self: 'self', vid: 'vid', fps: 'fps', st: 'st', frames_to_count: 'frames_to_count', cnt: 'cnt'):
    global transmitAudio

    while transmitAudio == True:
        WIDTH = 400
        while (vid.isOpened()):
            _, frame = vid.read()
            frame = imutils.resize(frame, width=WIDTH)
            encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            message = base64.b64encode(buffer)
            try:
                self.server_socket.sendto(message, self.client_addr)
            except:
                print(f"Lost connection with: {self.client_addr}")
                transmitAudio = False
                self.server_socket.close()
                cv2.destroyAllWindows()
            frame = cv2.putText(frame, 'FPS: ' + str(fps), (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow('TRANSMITTING VIDEO', frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self.server_socket.close()
                break
            if cnt == frames_to_count:
                try:
                    fps = round(frames_to_count / (time.time() - st))
                    st = time.time()
                    cnt = 0
                except:
                    pass
            cnt += 1


# Transmit Audio Thread
def TransmitAudio(self: 'self', chunk: 'chunk', sample_format: 'sample_format', channels: 'channels', fs: 'fs',
                  streamCapture: 'streamCapture', portAudio: 'portAudio'):
    global transmitAudio

    if self.client_socket_audio_transmit:

        while transmitAudio == True:
            data = streamCapture.read(chunk)

            if data != None:
                a = pickle.dumps(data)
                message = struct.pack("Q", len(a)) + a
                self.client_socket_audio_transmit.sendall(message)

    # Stop and close the stream
    streamCapture.stop_stream()
    streamCapture.close()

    # Terminate the PortAudio interface
    portAudio.terminate()

    # Audio Capture End
    self.client_socket_audio_transmit.close()


# Receive Audio Thread
def ReceiveAudio(self: 'self', chunk: 'chunk', sample_format: 'sample_format', channels: 'channels', fs: 'fs',
                 streamPlay: 'streamPlay', portAudioPlay: 'portAudioPlay'):
    global receiveAudio

    data = b""
    payload_size = struct.calcsize("Q")

    while receiveAudio:
        # Receiving Audio
        try:
            while len(data) < payload_size:
                packet = self.client_socket_audio_receive.recv(4 * 1024)  # 4K
                if not packet: break
                data += packet
            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("Q", packed_msg_size)[0]

            while len(data) < msg_size:
                data += self.client_socket_audio_receive.recv(4 * 1024)
            frame_data = data[:msg_size]
            data = data[msg_size:]
            frame = pickle.loads(frame_data)
            
            # Play audio
            streamPlay.write(frame)
        except:
            receiveAudio = False

    # Stop and close the stream
    streamPlay.stop_stream()
    streamPlay.close()

    # Terminate the PortAudio interface
    portAudioPlay.terminate()

    self.server_socket_audio_receive.close()

    ServerReceiveAudio()


# Client Connection Test Thread
def ClientConnectionStatus(self: 'self'):
    global transmitAudio

    while transmitAudio == True:

        try:
            msg, client_addr = self.server_socket.recvfrom(self.BUFF_SIZE)
        except:
            print(f"Lost connection with: {client_addr}")
            transmitAudio = False
            self.server_socket.close()
            cv2.destroyAllWindows()


# Initialize Server
class Server:
    def __init__(self):
        # Video transmit initialization
        self.BUFF_SIZE = 65536
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.BUFF_SIZE)
        global host_ip
        self.host_ip = host_ip
        print(self.host_ip)
        self.port = 9999
        socket_address_vid = (self.host_ip, self.port)
        self.server_socket.bind(socket_address_vid)
        print('Listening at:', socket_address_vid)
        msg, self.client_addr = self.server_socket.recvfrom(self.BUFF_SIZE)
        print('GOT connection from ', self.client_addr)

        # Audio transmit initialization
        self.server_socket_audio_transmit = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.port_audio_transmit = 4982
        self.backlog_audio_transmit = 1
        socket_address = (self.host_ip, self.port_audio_transmit)
        print('STARTING SERVER AT', socket_address, '...')
        self.server_socket_audio_transmit.bind(socket_address)
        self.server_socket_audio_transmit.listen(self.backlog_audio_transmit)
        self.client_socket_audio_transmit, self.client_addr_audio_transmit = self.server_socket_audio_transmit.accept()
        print('GOT CONNECTION FROM:', self.client_addr_audio_transmit)

    # Video Settings
    def ServerVideo(self):
        global transmitAudio
        transmitAudio = True

        # Set 20 fps for Raspberry Pi
        vid = cv2.VideoCapture(0)
        vid.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V'))
        vid.set(cv2.CAP_PROP_FRAME_WIDTH, 864)
        vid.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        vid.set(cv2.CAP_PROP_FPS, 20)
        fps, st, frames_to_count, cnt = (0, 0, 20, 0)

        # Start video transmission thread
        threadServerVideoArgs = {'self': self, 'vid': vid, 'fps': fps, 'st': st, 'frames_to_count': frames_to_count,
                                 'cnt': cnt}
        threadServerVideo = threading.Thread(target=TransmitVideo, daemon=True, kwargs=threadServerVideoArgs)
        threadServerVideo.start()

    # Audio Settings
    def ServerAudio(self):
        global transmitAudio
        transmitAudio = True

        chunk = 1024  # Record in chunks of 1024 samples
        sample_format = pyaudio.paInt16  # 16 bits per sample
        channels = 1
        fs = 44100  # Record at 44100 samples per second

        # Create an interface to PortAudio
        portAudio = pyaudio.PyAudio()
        streamCapture = portAudio.open(format=sample_format,
                                       channels=channels,
                                       rate=fs,
                                       frames_per_buffer=chunk,
                                       input=True)

        # Start audio transmission thread
        threadServerAudioTransmitArgs = {'self': self, 'chunk': chunk, 'sample_format': sample_format,
                                         'channels': channels, 'fs': fs, 'streamCapture': streamCapture,
                                         'portAudio': portAudio}
        threadServerAudioTransmit = threading.Thread(target=TransmitAudio, daemon=True,
                                                     kwargs=threadServerAudioTransmitArgs)
        threadServerAudioTransmit.start()

    # Start Cilent Status Thread
    def PingResponse(self):
        threadPingResponseArgs = {'self': self}
        threadPingResponse = threading.Thread(target=ClientConnectionStatus, daemon=True, kwargs=threadPingResponseArgs)
        threadPingResponse.start()


# Receive Audio
class ServerReceiveAudio(Server):
    def __init__(self):
        # Audio receive initialization
        global host_ip
        self.host_ip = host_ip
        self.server_socket_audio_receive = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.port_audio_receive = 4983
        self.backlog_audio_receive = 1
        socket_address = (self.host_ip, self.port_audio_receive)
        print('STARTING SERVER AT', socket_address, '...')

        self.server_socket_audio_receive.bind(socket_address)
        self.server_socket_audio_receive.listen(self.backlog_audio_receive)

        self.client_socket_audio_receive, self.client_addr_audio_receive = self.server_socket_audio_receive.accept()
        print('GOT CONNECTION FROM:', self.client_addr_audio_receive)

        global receiveAudio
        receiveAudio = True

        chunk = 1024  # Record in chunks of 1024 samples
        sample_format = pyaudio.paInt16  # 16 bits per sample
        channels = 1  # 2
        fs = 44100  # Record at 44100 samples per second

        # Create an interface to PortAudio
        portAudioPlay = pyaudio.PyAudio()
        streamPlay = portAudioPlay.open(format=sample_format,
                                        channels=channels,
                                        rate=fs,
                                        frames_per_buffer=chunk,
                                        output=True)

        # Start audio reception thread
        threadServerAudioReceiveArgs = {'self': self, 'chunk': chunk, 'sample_format': sample_format,
                                        'channels': channels, 'fs': fs, 'streamPlay': streamPlay,
                                        'portAudioPlay': portAudioPlay}
        threadServerAudioReceive = threading.Thread(target=ReceiveAudio, daemon=True,
                                                    kwargs=threadServerAudioReceiveArgs)
        threadServerAudioReceive.start()


# Open TCP connection for text transmition and reception
def Tcp_connect(HostIp, Port):
    global s
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HostIp, Port))
    return


# Listen for client connection
def Tcp_server_wait(numofclientwait, port):
    global s2
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.bind(('', port))
    s2.listen(numofclientwait)


# Accept next connection
def Tcp_server_next():
    global s
    s = s2.accept()[0]


# Send text message
def Tcp_Write(D):
    s.send(D + b'\r')
    return


# Receive text message
def Tcp_Read():
    a = ' '
    b = ''
    b = b + a
    while a != '\r':
        b = b + a
        a = s.recv(1).decode('utf-8')
    return b


# Close TCP connection
def Tcp_Close():
    s.close()
    return


# Initiate text messages
class ServerControlSignal(Server):
    def __init__(self):
        Tcp_server_wait(5, 4985)
        Tcp_server_next()
        
        # Start text message reception thread
        threadDataReceive = threading.Thread(target=ThreadReceiveData, daemon=True)
        threadDataReceive.start()

        # Start text message transmission thread
        threadDataSend = threading.Thread(target=ThreadSendData, daemon=True)
        threadDataSend.start()


# Receive text message for door lock control
def ThreadReceiveData():
    while True:
        msg = Tcp_Read()
        if msg == '  lock':
            GPIO.output(SOL, False)
        if msg == '  unlock':
            GPIO.output(SOL, True)
        print(msg)
        time.sleep(1)
    Tcp_Close()


# Send text message to Mobile App
def ThreadSendData():
    global notify
    global notificationMessage
    while True:
        if notify:
            Tcp_Write(notificationMessage)
            notify = False
            notificationMessage = ''
            time.sleep(1)
    Tcp_Close()


# Doorbell audio message playing thread
def Ring():
    # Doorbell audio file
    filename = 'Doorbell.wav'

    # Set chunk size of 1024 samples per data frame
    chunk = 1024

    # Open the sound file
    wf = wave.open(filename, 'rb')

    # Create an interface to PortAudio
    portAudioRing = pyaudio.PyAudio()

    # Open a .Stream object to write the WAV file to
    # 'output = True' indicates that the sound will be played rather than recorded
    streamRing = portAudioRing.open(format=portAudioRing.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True)

    # Read data in chunks
    data = wf.readframes(chunk)

    # Play the sound by writing the audio data to the stream
    while data != b'':
        streamRing.write(data)
        data = wf.readframes(chunk)

    # Close and terminate the stream
    streamRing.close()
    portAudioRing.terminate()
    
    time.sleep(4)

    global runRingThread
    runRingThread = True


# Raspberry Pi GPIO interface thread
def RPiGPIO():
    # GPIO delay
    global Wait
    Wait = 0
    
    # Play doorbell audio
    global Play
    Play = True
    
    # Buzzer input
    global Click
    Click = 0
    global Switch
    Switch = False
    
    # Text message
    global notify
    notify = False
    global notificationMessage
    
    # Doorbell audio thread
    global runRingThread
    runRingThread = True
    
    # LCD diaplay
    updateLCD = False
    
    # GPIO interface pooling
    while True:
        # Motion Sensor
        if GPIO.input(PIR) == 1:
            GPIO.output(LED, 1)
            
            # Transmit text message
            if notificationMessage != b'Doorbell Ringing !!!':
                notificationMessage = b'Motion Detected !!!'
                notify = True
                
                # Start doorbell audio message playing thread
                if runRingThread and Play:
                    threadRing = threading.Thread(target=Ring, daemon=True)
                    threadRing.start()
                    runRingThread = False
        else:
            GPIO.output(LED, 0)

        # Buzzer
        if (GPIO.input(BUTTON)):
            Click += 1
            print("Click")
        else:
            Click = 0
            
            # Update LCD display
            if updateLCD:
                lcd.lcd_clear()
                lcd.lcd_display_string("Smart Doorbell",1)
                updateLCD = False
                
        # Doorbell button press
        if (Click >= 5):
            GPIO.output(BUZZER, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(BUZZER, GPIO.LOW)
            Click = 0
            notify = True
            notificationMessage = b'Doorbell Ringing !!!'
            lcd.lcd_clear()
            lcd.lcd_display_string("Ringing ...", 1)
            updateLCD = True
            Play = False

        Wait += 1
        time.sleep(0.1)


# Raspberry Pi GPIO interafce initialization
class RPiInterface:
    threadRPiInterface = threading.Thread(target=RPiGPIO, daemon=True)
    threadRPiInterface.start()


# Server entry point function
def main():
    server = Server()
    server.ServerVideo()
    server.ServerAudio()
    # server.PingResponse()
    ServerReceiveAudio()
    ServerControlSignal()
    RPiInterface()


# Run the server entry point function
if __name__ == '__main__':
    main()
    print("Server is running . . .")
    print("Press any key to stop server . . .")
    input()
