#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created on Aug 15, 2013

@author: matze
'''
import OSTools
import sys
from BaseHTTPServer import HTTPServer
from PythonWebBridge import RecorderPlugin
from SimpleHTTPServer import SimpleHTTPRequestHandler
        
'''
    Entry point. Starts the micro Web server + a Recorder plugin which represents the only instance! of the recorder.
'''    
def runHTTPServer():
    try:
        RecorderHTTPHandler.AppConnector = RecorderPlugin()
        server = HTTPServer(('', 8080),RecorderHTTPHandler)
        print 'started httpserver...'
        server.serve_forever()
    except KeyboardInterrupt:
        print '^C received, shutting down server'
        server.socket.close()

'''
  Implementation of the Webserver session. Will be created on each request
  Connects via the RecorderPlugin to the WebRecorder
'''
        
class RecorderHTTPHandler(SimpleHTTPRequestHandler):
    AppConnector=None
    Home="/web"
    
    def __init__(self,aSocket,adress,aServer):
        SimpleHTTPRequestHandler.__init__(self,aSocket,adress,aServer)
    
    #use it for pages    
    def do_GET(self):
        self.path=self.Home+self.path
        if "Log." in self.path:
            self.AppConnector.handleLogCommand(self.path)
        self.AppConnector.log("GET:"+self.path)
        print "GET:"+self.path
        SimpleHTTPRequestHandler.do_GET(self)
        
    #the data stuff    
    def do_POST(self):
        length = int(self.headers.getheader('content-length'))
        try:
            command = self.rfile.read(length)
            self.send_response(200, "OK")
            self.end_headers()
            result=self.AppConnector.executePostData(command)
        except:
            result = 'error'
        self.wfile.write(result)

        
def main():
    if OSTools.checkIfInstanceRunning("RecorderWebServer"): 
        argv = sys.argv
        #OSTools.changeWorkingDirectory(argv[0]) 
        OSTools.changeWorkingDirectory(OSTools.getWorkingDirectory()) 
        runHTTPServer()
 
if __name__ == '__main__':
    main()
    
