import threading, socket, pickle
import mfunctions, tttfuncs

class Client():
    #Class that creates the client object for handling communications from the client's end
    #Implemented seperately to abstract the communications part from the game logic 
    
    def __init__(self,ADDRESS):
        #Takes the address and connects to the server. Also strats a thread to handle listening
        #TODO Might need more info for customizability
        
        self.conn = socket.socket(socket.AF_INET,
					socket.SOCK_STREAM)
        
        self.conn.connect(ADDRESS)
        self.connected = True
        self.uuid = None
        
    def create_room(self):
        self.send(('ROOM','CREATE'))
    
    def fetch_rooms(self):
        self.send(('ROOM','JOIN','LIST'))
        
    def join_room(self,id):
        self.send(('ROOM','JOIN',id))
        
    def start(self):
        self.send(('ROOM','START'))
    
    def startrecv(self,updation_callbacks):
        t = (updation_callbacks, )
        self.listening_thread = threading.Thread(target=self.listener, args=t)
        self.listening_thread.start()
    
    def send(self,msg):
        self.conn.send(pickle.dumps(msg))
        
    def listener(self,updation_callbacks):
        print(updation_callbacks)
        while self.connected:
            instruction = self.conn.recv(1024)
            instruction = pickle.loads(instruction)
            if instruction[0] == 'ROOM':
                #TODO Fix Pls Ty
                updation_callbacks['print'](instruction)
            
            elif instruction[0] == 'MONOPOLY':
                mfunctions.clientside(updation_callbacks, instruction[1], instruction[2:])
                
            elif instruction[0] == 'MONOPOLY':
                tttfuncs.clientside(updation_callbacks, instruction[1], instruction[2:])