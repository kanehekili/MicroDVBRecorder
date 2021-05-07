#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created on Aug 15, 2013

@author: matze
'''
import OSTools
import sys
import base64
from http.server import ThreadingHTTPServer
from PythonWebBridge import RecorderPlugin
from http.server import SimpleHTTPRequestHandler
        
'''
    Entry point. Starts the micro Web server + a Recorder plugin which represents the only instance! of the recorder.
''' 
KXD=""   
def runHTTPServer(port):
    try:
        RecorderHTTPHandler.AppConnector = RecorderPlugin()
        server = ThreadingHTTPServer(('', int(port)),RecorderHTTPHandler)
        print('started httpserver...')
        server.serve_forever()
    except KeyboardInterrupt:
        print('^C received, shutting down server')
        server.socket.close()

'''
  Implementation of the Webserver session. Will be created on each request
  Connects via the RecorderPlugin to the WebRecorder
'''
        
class RecorderHTTPHandler(SimpleHTTPRequestHandler):
    AppConnector=None
    clientAdress= None
    Home="/web"
    def __init__(self,aSocket,adress,aServer):
        self.clientAdress = adress[0]
        SimpleHTTPRequestHandler.__init__(self,aSocket,adress,aServer)
    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"MicroRecorder\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
    
    def handleJerk(self):
        #TODO Save Referer in list, save it and blacklist it on multiple tries
        print("*********** JERK START****************")
        print(self.headers)
        print("*********** JERK END****************")
        
    def checkAuthorization(self):
        if self.clientAdress.startswith("192.168.2") or self.clientAdress.startswith("127.0.0.1"):
            return True
        sendKey= self.headers.get('Authorization')
        if sendKey == None:
            print("No AUTH")
            self.do_AUTHHEAD()
            self.wfile.write(b'no auth header received')
            return False
        
        expectedKey= 'Basic '+KXD
        if  sendKey == expectedKey: 
            print("AUTH OK")
            return True
        #Invalid auth:
        self.do_AUTHHEAD()
        self.wfile.write(bytes(self.headers.get('Authorization'),"utf-8"))
        self.wfile.write(b'not authenticated')
        return False
    #use it for pages    
    def do_GET(self):
        
        ok= self.checkAuthorization()
        if not ok:
            self.handleJerk()
        else:
            self.path=self.Home+self.path
            if "Log." in self.path:
                self.AppConnector.handleLogCommand(self.path)
            elif "Films." in self.path:
                self.AppConnector.handleFilmCommand(self.path)
            self.AppConnector.log("GET:"+self.path)
            print(("GET:"+self.path))
            SimpleHTTPRequestHandler.do_GET(self)
        
            
    #the data stuff    
    def do_POST(self):
        if not self.checkAuthorization():
            SimpleHTTPRequestHandler.do_GET(self)
            self.AppConnector.log("POST FAKE from:"+self.clientAdress)
            print("POST FAKE from:"+self.clientAdress)
            return;
        length = int(self.headers.get('content-length'))
        content_type = "application/json"
        try:
            self.send_response(200, "OK")
            postdata = self.rfile.read(length)
            print("POST len: %d query len: %d"%(length,len(postdata)))
            command = postdata.decode('utf-8')

            self.send_header('Content-type', content_type)
            self.end_headers()
            result=self.AppConnector.executePostData(command)
        except:
            result = 'error'
        if result is not None:
            print("POST:",result[:75])
            self.wfile.write(bytes(result,'utf-8'))

        
def main():
    if OSTools.checkIfInstanceRunning("RecorderWebServer"): 
        global KXD
        argv = sys.argv
        #OSTools.changeWorkingDirectory(argv[0]) 
        OSTools.changeWorkingDirectory(OSTools.getWorkingDirectory()) 
        port = argv[1]
        tmp = argv[2].encode('utf-8')
        KXD = base64.b64encode(tmp).decode('utf-8')
        runHTTPServer(port)
 
if __name__ == '__main__':
    if len(sys.argv)<3:
        print("usage: RecorderWebServer.py [port] [username:password]")
    else:
        main()
    
