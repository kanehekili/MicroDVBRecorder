#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created on Aug 15, 2013
Interface/data provider for the web service.
@author: matze
'''

from ChannelReader import ChannelReader
from TerrestialDevice import DVB_T_Grabber
from EPGProgramProvider import EPGProgramProvider
from Configuration import Config,MessageListener
#from datetime import datetime
import json
import OSTools

class WebRecorder():
    '''
    API methods are called by the RecorderPlugin in the RecorderWebService module.
    '''
    #signal modes
    #TODO change mode to STATUS und ERROR...
    MSG_STATUS = MessageListener.MSG_STATUS
    #MSG_EPG = MessageListener.MSG_EPG
    MSG_REFRESH = MessageListener.MSG_REFRESH
    
    #Modes or types of rec? 
    (MODE_DATA,MODE_REC,MODE_BLOCK)=range(0xA0,0xA3)
    (TYPE_HEAD,TYPE_PROG,TYPE_INFO)=range(3)



    def __init__(self):
        '''
        starts the app
        '''
        self.configuration = Config()
        self.configuration.setupLogging("webdvb.log")
        
        self._lastMessage=None
        ml = MessageListener();
        ml.addListener(ml.MSG_STATUS, self.storeLastMessage)
        #ml.addListener(ml.MSG_EPG, this.storeLastMessage)
        ml.addListener(ml.MSG_REFRESH, self.storeLastMessage)
        
        channelReader = ChannelReader()
        cPath = self.configuration.getChannelFilePath()

        channelReader.readChannels(cPath)
        self.channelList = channelReader.getChannels()
        self.progProvider = EPGProgramProvider(self,self.channelList,self.configuration)
        self._lastEpgRead = None
        self._readCachedEpgData()
  

  
    def _readCachedEpgData(self):
        ml = MessageListener();
        if not self.channelList:
            ml.signalMessage(self.MSG_STATUS,"Where is that channel.conf? RTF!")
            return

        ml.signalMessage(self.MSG_STATUS,"Reading programm info")
        msg = "Idle"
        try:
            self.progProvider.readEPGCache()
            ml.signalMessage(self.MSG_REFRESH,"Program info read")# enforces a new list
        except IOError:
            msg = "No EPG data"
        except Exception,ex:
            msg= "Error reading cached EPG Data: "+str(ex.args[0])

        self.configuration.logInfo(msg)                        
        ml.signalMessage(self.MSG_STATUS,msg)
        
    def _getEPGDevice(self):
        return DVB_T_Grabber(self.channelList,self.configuration)

    def _collectEPGFromDevice(self):
        epgUpdater = self.progProvider.getEPGUpdater()
        self._updater.updateDatabase();
        if epgUpdater.hasError():
            MessageListener().signalMessage(self.MSG_STATUS,epgUpdater.getErrorMessage())
        
    '''
    API to Recorder plugin
    Basic idea: should be json objects
    '''    

    def storeLastMessage(self,message):
        self._lastMessage=message
    
    def getLastSignal(self):
        msg = self._lastMessage
        self._lastMessage = None
        return msg
    
    
    def readEPGDeviceData(self):
        self._collectEPGFromDevice()

    def getChannelList(self):
        channelNames = []
        for channel in self.channelList:
            channelNames.append(channel.getName())
        jchannels = json.dumps(channelNames)
        return jchannels  

    def getProgrammInfoForChannel(self,aChannelString):
        daytoDayList = self.progProvider.getInfosForChannel(aChannelString)
        jDayToDayArray = self._formatProgramList(daytoDayList)
        jInfos = json.dumps(jDayToDayArray)
        return jInfos
    
    def toggleRecordMode(self,jsonString):
        jsonDict = json.loads(jsonString)
        epgInfo=self._lookupEPGInfoFromJSON(jsonDict)
        forceRemove = jsonDict["type"]==self.TYPE_INFO;
        if epgInfo is not None:
            self.progProvider.toggleRecordInfo(epgInfo,forceRemove)
            result=self._formatProgramRow(epgInfo)
        else:
            result=jsonDict["error"]="Entry not found"
        if self._lastMessage is not None:
            result["error"]=self.getLastSignal()    
        return json.dumps(result)    

    def getFilterList(self,searchTuple):
        channelName = searchTuple[0]
        filterString = searchTuple[1]
        epgInfoList = self.progProvider.searchInChannel(channelName,filterString)
        jDayToDayArray = self._formatProgramList(epgInfoList)
        return json.dumps(jDayToDayArray)
        

    def getAutoSelectList(self):
        autoselectList=self.progProvider.getAutoSelector().getAutoSelectionList();
        
        jList = self._formatAutoSelectList(autoselectList)
        return json.dumps(jList)

        
    def addToAutoSelection(self,jsonString):
        jsonDict = json.loads(jsonString)
        epgInfo = self._lookupEPGInfoFromJSON(jsonDict)
        autoSelector = self.progProvider.getAutoSelector() 
        autoSelector.addAutoSelectPreference(epgInfo)
        autoSelector.saveAutoSelectData()

    def removeFromAutoSelection(self,jsonString):
        jsonDict = json.loads(jsonString)
        hourString=jsonDict["timetext"]
        titleString=jsonDict["text"]
        autoSelector = self.progProvider.getAutoSelector()
        autoSelector.removeFromAutoSelectPreference(hourString,titleString)
        autoSelector.saveAutoSelectData()
        
    def getRecordingList(self):
        epgInfoList=self.progProvider.getRecordQueue().getEpgList();
        jList = self._formatSimpleList(epgInfoList)
        return json.dumps(jList)

    '''
    reread epg info if a modification took place.If changes took place (like a daemon epg update)
    update the database 
    '''
    def checkEPGData(self):
        fileName= self.configuration.getCachedXMLTVFilePath()
        currentModificationtime=0
        try:
            currentModificationtime=OSTools.getLastModificationTime(fileName)
        except OSError as osError:
            msg = "CheckEpgData:"+osError.strerror
            self.configuration.logError(msg)                        
            self.storeLastMessage(msg)
            return
            
        if self._lastEpgRead is None:
            self._lastEpgRead= currentModificationtime-100

        if currentModificationtime-self._lastEpgRead>60:
            self._readCachedEpgData()
            self._lastEpgRead= currentModificationtime

    '''
    End of WebRecorder API
    --
    
    Helper/conversion methods -- aka WebViewGenerator?
    '''
    def _formatHeader(self,epgInfo):
        header = epgInfo.getStartTime().strftime("%A %d %B")
        headerText = "<b>%s</b>" % header
        return {"type":self.TYPE_HEAD,"text":headerText,"time":None};
                
    def _formatProgramRow(self,epgInfo):
        epgTime = epgInfo.getStartTimeString()
        epgDate = epgInfo.getDateString()
        title = epgInfo.getTitle()
        duration = str(epgInfo.getDuration())
        description = epgInfo.getDescription() 
        #TODO: Formating is client work- only the data!
        programText = "<b>%s</b><br>%s<small><i> Duration: %s</i></small>" % (title, description, duration)
        
        jobID=None
        if epgInfo.isMarkedForRecord():
            recmode = self.MODE_REC
            jobID= epgInfo.getJobID()
        elif epgInfo.isBlockedForRecord():
            recmode =self.MODE_BLOCK
        else:
            recmode = self.MODE_DATA
        return {"type":self.TYPE_PROG,"text":programText,"time":epgTime,"date":epgDate, "recordMode":recmode, "jobID":jobID,"title":title, "channel":epgInfo.getChannel().getName(),"error":None};

    def _formatProgramList(self,daytoDayList):
        jDayToDayArray=[]
        for singleDayList in daytoDayList:
            jDayList = []
            #adds the header - setting the date only
            #TODO: Empty singleDayList! Should not happen
            if len(singleDayList)==0:
                print "ERROR: Empty single day list"
                continue
                
            headerText=self._formatHeader(singleDayList[0])
            for epgInfo in singleDayList:
                jInfo = self._formatProgramRow(epgInfo);
                jDayList.append(jInfo)

            jDayObject={"head":headerText,"list":jDayList};
            jDayToDayArray.append(jDayObject)
        if len(jDayToDayArray)==0:
            return self.asJsonError("Error fetching data", self.getLastSignal())    
        return jDayToDayArray
        
    def asJsonError(self,errorMsg,argumentString):
        return {"type":self.TYPE_INFO,"error":errorMsg,"args":argumentString}

    def _lookupEPGInfoFromJSON(self,jsonData):
        aChannelString = jsonData["channel"]
        dayString=jsonData["date"]
        timeString = jsonData["time"]
        #TODO: - str encoding problem?
        daytoDayList = self.progProvider.getInfosForChannel(str(aChannelString))
        #Well... get the right DAY first....
        for singleDayList in daytoDayList:
            if singleDayList[0].getDateString() in dayString:
                for epgInfo in singleDayList:
                    if epgInfo.getStartTimeString() in timeString:
                        return epgInfo 
        return None
    
    def _formatAutoSelectList(self,autoSelectList):
        jDayList = []
        for autoSelection in autoSelectList:
            timeString= autoSelection.getHourListString()
            title = autoSelection.getTitle()
            jInfo = {"type":self.TYPE_INFO,"timetext":timeString,"text":title,"title":title,"error":None}
            jDayList.append(jInfo)
        return jDayList
            
    
    def _formatSimpleList(self,epgInfoList):
        jDayList = []
        for epgInfo in epgInfoList:
            jInfo = self._formatInfoRow(epgInfo);
            jDayList.append(jInfo)
        return jDayList
    
    def _formatInfoRow(self,epgInfo):
        epgTime = epgInfo.getStartTimeString()
        epgDate = epgInfo.getDateString()
        theDay= epgInfo.getStartTime().strftime("%a %d")
        start = epgInfo.getStartTime().strftime("%H:%M-")
        end = epgInfo.getEndTime().strftime("%H:%M")
        channel = epgInfo.getChannel().getName()
        formatTime = "<b>%s</b><i> %s</i><br><small>%s%s</small>" % (channel,theDay,start,end)
        
        title = epgInfo.getTitle()
        description = epgInfo.getDescription()
        jobID = epgInfo.getJobID()
        if len(jobID)>0:
            programText = "<b>%s</b><br>%s <i>(%s)</i>" % (title, description,jobID)
        else:
            programText = "<b>%s</b><br>%s" % (title, description)
        return {"type":self.TYPE_INFO,"timetext":formatTime,"text":programText,"time":epgTime,"date":epgDate,"jobID":jobID,"title":title, "channel":channel,"error":None};
        
            