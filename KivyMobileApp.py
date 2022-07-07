########################################################################################################################
##   Mobile App – Technical Project (CMPE2965)
##   Video reception from Server, audio reception from Server, audio transmission to Server,
#    receive notification from Server and send control signal to Server
##   Author:                 Sibat Hassan
##   Created On:             20 March, 2022
##   Submission Date:        NA
########################################################################################################################
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window
import pyaudio
import threading
import cv2
import socket
import numpy as np
import time
import base64
import pickle
import struct

# Initialize Mobile App window size
Window.size = (400, 600)

# Define aqua color for Mobile App buttons
aqua = [0,1,1,1]

# Raspberry Pi IP Address
host_ip = '192.168.137.42'

# Global flag for receiving server audio in a background thread
receiveAudio = False

# Global flag for transmitting app audio in a background thread
transmitAudio = False
runtransmitAudioThread = True

# Text messages
notificationReceived = False
notificationMsg = ""
controlMessage = ""
runControlThread = True


# Audio Reception Thread
def KivyAudioReceiver(self: 'self', data: 'data', payload_size: 'payload_size', chunk: 'chunk', sample_format: 'sample_format', channels: 'channels', fs: 'fs', portAudio: 'portAudio', streamPlay: 'streamPlay'):
    global receiveAudio

    while receiveAudio == True:
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
        streamPlay.write(frame)

    # Stop and close the stream
    streamPlay.stop_stream()
    streamPlay.close()

    # Terminate the PortAudio interface
    portAudio.terminate()

    self.client_socket_audio_receive.close()


# Initialize App
class MobileApp(App):
    def build(self):
        # Video reception initialization
        self.BUFF_SIZE = 65536
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.BUFF_SIZE)
        self.host_name = socket.gethostname()
        global host_ip
        self.host_ip = host_ip
        self.port = 9999
        message = b'Connection successful . . .'
        self.client_socket.sendto(message, (self.host_ip, self.port))
        self.fps, self.st, self.frames_to_count, self.cnt = (0, 0, 20, 0)

        # Audio reception initialization
        self.client_socket_audio_receive = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.port_audio_receive = 4982
        socket_address = (self.host_ip, self.port_audio_receive)
        self.client_socket_audio_receive.connect(socket_address)
        print("CLIENT CONNECTED TO", socket_address)

        # App Layout
        self.main_layout = BoxLayout(orientation="vertical")
        self.labelSpace1 = Label(size_hint=(.01, .01),
                                 pos_hint={'center_x': .5, 'center_y': .5})
        self.main_layout.add_widget(self.labelSpace1)
        self.videoFrame = Image(size_hint=(0.8, 0.6),
                                pos_hint={'center_x': .5, 'center_y': .5})
        self.main_layout.add_widget(self.videoFrame)
        self.labelSpace2 = Label(size_hint=(.01, .01),
                                 pos_hint={'center_x': .5, 'center_y': .5})
        self.main_layout.add_widget(self.labelSpace2)
        self.buttonMic = Button(background_color=aqua,
                                 background_normal='Images/mic_muted.jpg',
                                 size_hint=(.15, .15),
                                 pos_hint={'center_x': .5, 'center_y': .5},
                                 padding_y=200,
                                 on_press=self.TransmitAudio)
        self.main_layout.add_widget(self.buttonMic)
        self.labelSpace3 = Label(size_hint=(.01, .01),
                                 pos_hint={'center_x': .5, 'center_y': .5})
        self.main_layout.add_widget(self.labelSpace3)
        self.buttonLock = Button(background_color=aqua,
                                 background_normal='Images/locked.jpg',
                                 size_hint=(.15, .15),
                                 pos_hint={'center_x': .5, 'center_y': .5},
                                 padding_y=20,
                                 on_press=self.ControlLock)
        self.main_layout.add_widget(self.buttonLock)
        self.labelStatus = Label(text=f"Connected to: {self.host_ip}",
                           size_hint=(.15, .15),
                           pos_hint={'center_x': .5, 'center_y': .5})
        self.main_layout.add_widget(self.labelStatus)

        # Schedule video frames capture
        Clock.schedule_interval(self.KivyVideoClient, 1.0 / 20)
    
        # Initiate audio reception settings
        self.KivyAudioReceiveClient()

        # Receive text messages
        Clock.schedule_interval(self.DisplayNotification, 1.0)
        Clock.schedule_interval(self.ClearNotification, 5.0)

        return self.main_layout

    # Video Reception
    def KivyVideoClient(self, dt):
        try:
            packet, _ = self.client_socket.recvfrom(self.BUFF_SIZE)
        except:
            self.labelStatus.text = "Lost connection with server . . ."
            self.client_socket.close()
            Clock.unschedule(self.KivyVideoClient)
            Window.close()
        data = base64.b64decode(packet, ' /')
        npdata = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(npdata, 1)
        frame = cv2.putText(frame, 'FPS: ' + str(self.fps), (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Convert to texture
        buf1 = cv2.flip(frame, 0)
        buf = buf1.tostring()
        texture1 = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')

        # If working on RASPBERRY PI, use colorfmt='rgba' here instead, but stick with "bgr" in blit_buffer.
        texture1.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')

        # Display image from the texture
        self.videoFrame.texture = texture1

        # Video frames per second calculation
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            self.client_socket.close()
        if self.cnt == self.frames_to_count:
            try:
                self.fps = round(self.frames_to_count / (time.time() - self.st))
                self.st = time.time()
                self.cnt = 0
            except:
                pass
        self.cnt += 1

    # Audio Reception Settings
    def KivyAudioReceiveClient(self):
        global receiveAudio
        receiveAudio = True

        data = b""
        payload_size = struct.calcsize("Q")

        chunk = 1024  # Record in chunks of 1024 samples
        sample_format = pyaudio.paInt16  # 16 bits per sample
        channels = 1#2
        fs = 44100  # Record at 44100 samples per second

        # Create an interface to PortAudio
        portAudio = pyaudio.PyAudio()

        # Open a .Stream object to write the WAV file to
        # 'output = True' indicates that the sound will be played rather than recorded
        streamPlay = portAudio.open(format=sample_format,
                            channels=channels,
                            rate=fs,
                            output=True)
        
        # Start audio reception thread
        threadAudioReceiveArgs = {'self': self, 'data': data, 'payload_size': payload_size, 'chunk': chunk, 'sample_format': sample_format, 'channels': channels, 'fs': fs, 'portAudio': portAudio, 'streamPlay': streamPlay}
        threadAudioReceive = threading.Thread(target=KivyAudioReceiver, daemon=True, kwargs=threadAudioReceiveArgs)
        threadAudioReceive.start()

    # Audio Transmission Settings
    def TransmitAudio(self, instance):
        global transmitAudio
        global runtransmitAudioThread

        # App mic widget
        if instance.background_normal == 'Images/mic_unmuted.jpg':
            instance.background_normal = 'Images/mic_muted.jpg'
            transmitAudio = False
        else:
            instance.background_normal = 'Images/mic_unmuted.jpg'
            transmitAudio = True

        # Start audio transmission thread
        if runtransmitAudioThread:
            threadPlay = threading.Thread(target=_SendAudio, daemon=True)
            threadPlay.start()
            runtransmitAudioThread = False

    # Door Lock Controlling Text Message
    def ControlLock(self, instance):
        global controlMessage
        global runControlThread
        controlMessage = ""
        
        # Door lock widget
        if instance.background_normal == 'Images/locked.jpg':
            instance.background_normal = 'Images/unlocked.jpg'
            controlMessage = b'unlock'
        else:
            instance.background_normal = 'Images/locked.jpg'
            controlMessage = b'lock'

        # Start text message thread
        if runControlThread:
            threadControlSignal = threading.Thread(target=_SendControlSignal, daemon=True)
            threadControlSignal.start()
            runControlThread = False

    # Server Connection Test
    def PingServer(self, dt):
        message = b'Client is connected . . .'

        try:
            self.client_socket.sendto(message, (self.host_ip, self.port))
        except:
            self.labelStatus.text = "Lost connection with server . . ."
            self.client_socket.close()
            Clock.unschedule(self.PingServer)
            Window.close()

    # Receive Text Messages
    def DisplayNotification(self, dt):
        global notificationReceived
        global notificationMsg
        if notificationReceived:
            self.labelStatus.text = notificationMsg
            notificationReceived = False

    # Clear Text Messages
    def ClearNotification(self, dt):
        global notificationReceived
        global notificationMsg
        if not notificationReceived:
            self.labelStatus.text = ""


# Audio Transmission Thread
def _SendAudio():
    AppTransmitAudio()
    
    
# Audio Transmission Settings
class AppTransmitAudio(MobileApp):
    def __init__(self):
        self.client_socket_audio_transmit = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.port_audio_transmit = 4983

        global host_ip
        self.host_ip = host_ip

        socket_address = (self.host_ip, self.port_audio_transmit)
        self.client_socket_audio_transmit.connect(socket_address)
        print("CLIENT CONNECTED TO", socket_address)

        chunk = 1024  # Record in chunks of 1024 samples
        sample_format = pyaudio.paInt16  # 16 bits per sample
        channels = 1  # 2
        fs = 44100  # Record at 44100 samples per second

        # Create an interface to PortAudio
        portAudio = pyaudio.PyAudio()
        streamCapture = portAudio.open(format=sample_format,
                                       channels=channels,
                                       rate=fs,
                                       input=True)

        global transmitAudio

        if self.client_socket_audio_transmit:

            while True:
                time.sleep(1)
                while transmitAudio:
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

        self.client_socket_audio_transmit.close()


# Open TCP connection for text transmition and reception
def Tcp_connect(HostIp, Port):
    global s
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HostIp, Port))
    return


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


# Text Message Thread
def _SendControlSignal():
    AppControlSignal()


# Text Messages
class AppControlSignal(MobileApp):
    def __init__(self):
        global host_ip
        self.host_ip = host_ip
        Tcp_connect(self.host_ip, 4985)

        # Start text message transmission thread
        threadDataSend = threading.Thread(target=ThreadSendData, daemon=True)
        threadDataSend.start()

        # Start text message reception thread
        threadDataReceive = threading.Thread(target=ThreadReceiveData, daemon=True)
        threadDataReceive.start()


# Text Message Reception Thread
def ThreadReceiveData():
    global notificationMsg
    global notificationReceived
    while True:
        msg = Tcp_Read()
        print(msg)
        if msg == '  Doorbell Ringing !!!' or msg == '  Motion Detected !!!':
            notificationReceived = True
            notificationMsg = msg
        time.sleep(1)
    Tcp_Close()


# Text Message Transmission Thread
def ThreadSendData():
    global controlMessage
    while True:
        time.sleep(1)
        if controlMessage == b'lock' or controlMessage == b'unlock':
            Tcp_Write(controlMessage)
            controlMessage = b''
    Tcp_Close()


# Start App
if __name__ == '__main__':
    MobileApp().run()
    print("App Closed . . .")