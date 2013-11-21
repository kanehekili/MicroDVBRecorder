#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created on Aug 15, 2013

@author: matze
'''
from SimpleHTTPServer import SimpleHTTPRequestHandler
from BaseHTTPServer import HTTPServer
from PythonWebBridge import WebRecorder 
import OSTools
import json
import os

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
        self.AppConnector.log("GET:"+self.path)
        print "GET:"+self.path
        SimpleHTTPRequestHandler.do_GET(self)
        
    #the data stuff    
    def do_POST(self):
        length = int(self.headers.getheader('content-length'))
        try:
            command = self.rfile.read(length)
            result=self.AppConnector.executePostData(command)
        except:
            result = 'error'
        self.wfile.write(result)
        
'''
  This is the connector from the HTTP Server to the WebRecorder. Should only exist one instance
'''
class RecorderPlugin():
    Commands=["REQ_Channels","REQ_Programs", "MARK_Programm", "AUTO_SELECT", "LIST_REC", "LIST_AUTO", "FILTER", "RM_AUTOSELECT","Download"]
    def __init__(self):
        print "RecorderPlugin activated"
        self.count=0;
        self._webRecorder=WebRecorder()
        self._config = self._webRecorder.configuration
        self.__linkLogging()

    def __linkLogging(self):
        #../../../VideoRecorder/src/log/
        #NO! That is where the command shell sits: currentPath=os.getcwd()
        destFile =  self._config.getFilePath(self._config.getWebPath(), "Log.txt")
        #destFile =  os.path.join(currentPath,"web/Log.txt")
        srcFile = self._config.getLoggingPath();
        srcFile =  os.path.join(srcFile,"webdvb.log");
        self._config.logInfo("Linking file:"+srcFile)
        if not os.path.lexists(destFile):
            os.symlink(srcFile, destFile)

    def log(self,aString):
        self._config.logInfo(aString)
    
    def _getArgs(self,commandDic):
        return commandDic["arg"].encode('utf-8')
        
         
    def executePostData(self,jsonCmd):
        try:
            print "Processing post data:"+jsonCmd
            self.log("Processing post data:"+jsonCmd);
            commandDic = json.loads(jsonCmd)
            command = commandDic["cmd"]
            if command==self.Commands[0]:  #channel request
                return (self._webRecorder.getChannelList())
            if command==self.Commands[1]:  #prog request
                self._webRecorder.checkEPGData()
                channel = self._getArgs(commandDic)
                return self._webRecorder.getProgrammInfoForChannel(channel)
            if command==self.Commands[2]:  #Recording on/off
                jsonString = self._getArgs(commandDic)
                return self._webRecorder.toggleRecordMode(jsonString)
            if command==self.Commands[3]:  #AUTOSELECT DnD
                jsonString = self._getArgs(commandDic)
                return self._webRecorder.addToAutoSelection(jsonString)
            if command==self.Commands[4]:  #get rec list
                return self._webRecorder.getRecordingList()
            if command==self.Commands[5]:  #get auto select list
                return self._webRecorder.getAutoSelectList()
            if command==self.Commands[6]:  #Filter current list
                atuple=commandDic["arg"]
                return self._webRecorder.getFilterList(atuple) #channel and The string
            if command==self.Commands[7]:  #Remove Autoselect entry
                jsonString = self._getArgs(commandDic)
                return self._webRecorder.removeFromAutoSelection(jsonString) #channel and The string
            #more:settings, download file....
            
            
        except Exception,ex:
            msg= "Error running POST data: "+str(ex.args[0])
            print msg
            self._config.getLogger().exception(msg)
            jsonError= self._webRecorder.asJsonError("Server Error", msg)
            return json.dumps(jsonError)
        
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
        
def main():
    if OSTools.checkIfInstanceRunning("RecorderWebServer"):   
        runHTTPServer()
 
if __name__ == '__main__':
    main()
    
