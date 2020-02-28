# -*- coding: utf-8 -*-
'''
Created on Oct 11, 2012
June 2016: Keep SDCard safe, add path for logging and xmltv data
@author: matze
'''
import os

from datetime import timedelta
import logging
import configparser
import OSTools

class Config():

    HomeDir = os.path.dirname(__file__)
    UserPath=os.path.expanduser("~")
    #Due to a problem in systemd:
    print(("curent dir:",HomeDir," user-home:",UserPath))
    
    LogPath="log"
    XMLPath = "xmltv"
    BinPath = "bin"
    TzapPath = ".tzap"
    CzapPath = ".czap"
    WebPath="web"
    ResourcePath=os.path.join(WebPath,"img")
    RecordDestination = os.path.join("Videos","Recordings")
    ConfigPath = os.path.join(HomeDir,XMLPath,"Config.conf")
    RecordDir = os.path.join(UserPath,RecordDestination)#default,place to store the films
    DataDir = HomeDir #default,place to store xmltv +log data
        
    ChannelFile = "channels.conf"
    AutoSelectFile="AutoSelect.conf"
    RecQueueFile="RecordQueue.xml"
    VCRMarkerFile="MODE_VCR"
    ServerMarkerFile="MODE_SERVER"
    EPGFile = "EPGList.xmltv"
    TimeFile="EPGTime.txt"
    
    XMLFileTyp=".xmltv"
    MPGFileTyp=".m2t" #Type of file to store
    
    POLICY_SERVER =0xB0
    POLICY_VCR =0xB1
    MODE_NONE =0xA0
    MODE_SLEEP =0xA1
    MODE_HIBERNATE=0xA2
    
    REC_TYPE_TZAP = "TZAP"
    REC_TYPE_CZAP = "CZAP"
    REC_TYPE_SZAP = "SZAP"
    REC_TYPE_VLC = "VLC"
    REC_TYPE_SUNDTEK="SUNDTEK_C"
    REC_TYPE_FAKE = "FAKE"
    
    #configurable items
    RecordTimeMargin = None
    DAEMON_POLICY = None
    SUSPEND_MODE = None
    RECORD_DEVICE = None

    def __init__(self):
        if not os.path.isfile(self.ConfigPath):
            self._writeDefaultConfig()
      
        self._loadConfig()
        self.__setupDirectories()

    
    def __setupDirectories(self):
        OSTools.ensureDirectory(self.DataDir,self.LogPath)
        OSTools.ensureDirectory(self.DataDir,self.XMLPath)
    
    def setupLogging(self,fileName): 
        path = os.path.join(self.DataDir,self.LogPath,fileName)
        logging.basicConfig(filename=path,level=logging.DEBUG,format='%(asctime)s %(message)s')           

    def getCachedXMLTVFilePath(self):
        return os.path.join(self.DataDir,self.XMLPath,self.EPGFile)
    
    def getEPGTimestampPath(self):
        return os.path.join(self.DataDir,self.XMLPath,self.TimeFile)
    
    def getAutoSelectPath(self):
        return os.path.join(self.DataDir,self.XMLPath,self.AutoSelectFile)
    
    def getRecQueuePath(self):
        return os.path.join(self.DataDir,self.XMLPath,self.RecQueueFile)
    
    def getLoggingPath(self):
        return os.path.join(self.DataDir,self.LogPath);
    
    def getWebPath(self):
        return os.path.join(self.HomeDir,self.WebPath);
    #path where to put the recordings in
    def getRecordingPath(self):
        return self.RecordDir
    
    #config and record queue data
    def getResourcePath(self):
        return os.path.join(self.HomeDir,self.ResourcePath)
    
    #path of the xmltv files - not used anymore 
    def getXMLPath(self):
        return os.path.join(self.DataDir,self.XMLPath)
    
    #path for the additional progs 
    def getBinPath(self):
        return os.path.join(self.HomeDir,self.BinPath)
    
    def getChannelFilePath(self):
        if self.RECORD_DEVICE == self.REC_TYPE_CZAP or self.RECORD_DEVICE == self.REC_TYPE_SUNDTEK:
            return os.path.join(self.UserPath,self.CzapPath,self.ChannelFile)
        else:
            return os.path.join(self.UserPath,self.TzapPath,self.ChannelFile)
    
    def getEnergySaverFileMarker(self):
        return os.path.join(self.HomeDir,self.XMLPath,self.VCRMarkerFile)
    
    def getServerFileMarker(self):
        return os.path.join(self.HomeDir,self.XMLPath,self.ServerMarkerFile)
    
    def getFilePath(self,filePath,fileName):
        return os.path.join(filePath,fileName)
    
    def getLogger(self):
        return logging

    def logInfo(self,aString):
        logging.log(logging.INFO,aString)

    def logError(self,aString):
        logging.log(logging.ERROR,aString)
    
    def logClose(self):
        logging.shutdown() 

    def _loadConfig(self):
        c = ConfigAccessor(self.ConfigPath)
        c.read()
        margin = c.getInt("RECORDMARGIN")
        Config.RecordTimeMargin = timedelta(minutes=margin)
        policy = c.get("DAEMON_POLICY")
        if policy.upper() == "SERVER":
            Config.DAEMON_POLICY = Config.POLICY_SERVER
        else:
            Config.DAEMON_POLICY= Config.POLICY_VCR
        suspendMode=c.get("SUSPEND_MODE")
        if suspendMode.upper() == "SLEEP":
            Config.SUSPEND_MODE=Config.MODE_SLEEP
        else:
            Config.SUSPEND_MODE=Config.MODE_HIBERNATE
        
        #read recording path
        aRecPath = c.get("RECORDING_PATH")
        if aRecPath and len(aRecPath)>4:
            Config.RecordDir = aRecPath
        #read data path - log & xmltv
        aDataPath = c.get("DATA_PATH")
        if aDataPath and len(aDataPath)>4:
            Config.DataDir = aDataPath
            
        recType = c.get("RECORD_TYPE")
        if recType:
            Config.RECORD_DEVICE = recType.upper()
        else:
            Config.RECORD_DEVICE = Config.REC_TYPE_FAKE

    def isArm(self):
        return os.uname()[4][:3] == 'arm'
        
   
    def _writeDefaultConfig(self):
        c = ConfigAccessor(self.ConfigPath)
        c.set("RECORDMARGIN","5")
        c.set("DAEMON_POLICY","SERVER")
        c.set("SUSPEND_MODE","SLEEP")
        c.set("RECORD_TYPE",Config.REC_TYPE_TZAP)
        c.store()

 
class ConfigAccessor():
    __SECTION="Mdvbrec"

    def __init__(self,filePath):
        self._path=filePath
        self.parser = configparser.ConfigParser()
        self.parser.add_section(self.__SECTION)
        
    def read(self):
        self.parser.read(self._path)
        
    def set(self,key,value):
        self.parser.set(self.__SECTION,key,value)
    
    def get(self,key):
        if self.parser.has_option(self.__SECTION, key):
            return self.parser.get(self.__SECTION,key)
        return None

    def getInt(self,key):
        if self.parser.has_option(self.__SECTION, key):
            return self.parser.getint(self.__SECTION,key)
        return None
        
    def store(self):
        try:
            with open(self._path, 'w') as aFile:
                self.parser.write(aFile)
        except IOError:
            return False
        return True           

class MessageListener():
    MSG_STATUS = 0xF2
    MSG_EPG = 0xF3
    MSG_REFRESH = 0xF4
    '''
    singleton class for connecting dispatcher and listeners of messages
    listeners must implement the message for which they were registered   
    '''

    class __impl:
        """ Implementation of the singleton interface """
        def __init__(self):
            self._listeners={}     
        
        def addListener(self,mode,function):
            self._listeners.setdefault(mode,function)
        
#        def removeListener(self,aListener):
#            self._listeners.remove(aListener)
        
        def signalMessage(self, mode, *arguments):
            argList = arguments
            registeredFunction = self._listeners.setdefault(mode,None)
            if registeredFunction:
                registeredFunction(*argList)
            
    # storage for the instance reference
    __instance = None

    def __init__(self):
        """ Create singleton instance """
        # Check whether we already have an instance
        if MessageListener.__instance is None:
            # Create and remember instance
            MessageListener.__instance = MessageListener.__impl()

        # Store instance reference as the only member in the handle
        self.__dict__['_Singleton__instance'] = MessageListener.__instance

    def __getattr__(self, attr):
        """ Delegate access to implementation """
        return getattr(self.__instance, attr)

    def __setattr__(self, attr, value):
        """ Delegate access to implementation """                    