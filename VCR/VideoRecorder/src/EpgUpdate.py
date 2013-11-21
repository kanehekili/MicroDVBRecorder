# -*- coding: utf-8 -*-
'''
Created on Jan 5, 2013
@author: matze

Headless EPG updater. Reads the current xmlTV file and adds the new EPG data.
Data will be stored.
Needs to remember the last update... Should run once a day 
'''
from ChannelReader import ChannelReader
from EpgReader import EpgReader
from TerrestialDevice import DVB_T_Grabber
from EPGDatabase import EpgDatabase
from RecordQueue import RecordQueue

class EpgUpdater:
    def __init__(self,config):
        self._config = config
        reader = ChannelReader()
        reader.readChannels(self._config.getChannelFilePath());
        self._channelList=reader.getChannels()
        self._recordQueue = RecordQueue(self._channelList, config)

        self._database = None
        self._errorMessage = None
        


    '''
    accessors record queue and database
    '''
    def getDatabase(self):
        return self._database
    
    def getRecordQueue(self):
        return self._recordQueue
        
    '''
    adds the epg data from a device to the database. Base data is expected to be there
    '''
    def updateDatabase(self):
        self._errorMessage = None
        self.readEPGCache()
        self._collectEPGFromDevice()
    
    '''
    hook to read cached epgdata
    Reads the previously cached data - if present
    '''
    def readEPGCache(self):
        self._database = EpgDatabase(self._config)
        path = self._config.getCachedXMLTVFilePath()
        epgReader=EpgReader(self._channelList)
        epgList= epgReader.readCachedXMLFile(path)
        self._database.setUpChannelList(epgList)

    '''
    Stores the database
    '''
    def persistDatabase(self):
        self._errorMessage = None
        if not self._database:
            self._errorMessage = "No database!"

        plainList = self._database.getPersistenceData()
        infoCount = len(plainList) 
        if infoCount==0:
            self._errorMessage = "No data saved"
        else:
            path = self._config.getCachedXMLTVFilePath()
            EpgReader(None).dumpEPGData(plainList,path)


    def hasError(self):
        return not self._errorMessage is None

    def getErrorMessage(self):
        return self._errorMessage


    def _collectEPGFromDevice(self):
        self._errorMessage = None
        DVBT = self._getEPGDevice()
        try:
            dvbList = DVBT.collectEPGList()
        except Exception,ex:
            error = ex.args
            aString = str(error)
            self._errorMessage="Error while retrieving EPG data: "+aString
            self._config.logError(self._errorMessage)
            return self._errorMessage
        
        if len(dvbList) is 0:
            self._errorMessage="No EPG data received"
            self._config.logError(self._errorMessage)
            return self._errorMessage
        
        epgReader=EpgReader(self._channelList)
        epgList=[]
        for xmls in dvbList:    
            epgReader.parseXML_TVString(xmls,epgList,UTC=True)
        
        self._database.updateChannelList(epgList)
        epgData= self._database.getData()
        self._updateRecordInfo(epgData)
        
         
    def _updateRecordInfo(self,infoArray):
        autoSelector = self._database.getAutoSelector()
        self.getRecordQueue().synchronizeEntries(infoArray)
        for dayToDayList in infoArray:
            #mark the newly received data in the record queue
            epgsToCheck=autoSelector.getEPGListForAutoSelect(dayToDayList)
            for epgInfo in epgsToCheck:
                state = ""
                if epgInfo.isBlockedForRecord():
                    state="Block"
                if epgInfo.isMarkedForRecord():
                    state=state+";Rec"
                if len(state)==0:
                    self._recordQueue.addRecording(epgInfo)
#                 if len(state)>0:
#                     self._config.logInfo("["+state+"]NO Rec Q for:"+epgInfo.getString())
#                 else:
#                     self._config.logInfo("Add to Rec Q:"+epgInfo.getString()) 
#                     self._recordQueue.addRecording(epgInfo)

    def _getEPGDevice(self):
        return DVB_T_Grabber(self._channelList,self._config)



