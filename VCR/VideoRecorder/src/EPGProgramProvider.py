# -*- coding: utf-8 -*-
'''
Created on Oct 12, 2012

@author: matze
'''

'''
Holds the program dictionary, whose keys are the channel names
values are unsorted lists of epg info data
GUIs may get the sorted stuff via this  
 
'''
from EpgUpdate import EpgUpdater
 
class EPGProgramProvider:
    '''
    application: someone that answers to readEPGDeviceData()
    channelList: aList of Channel Entries
    config: The reocrders config
    '''
    def __init__(self,application,channelList,config):
        self.channelList = channelList
        self._updater = EpgUpdater(config)
        self._config=config
        self._application = application
    
    #called on view update and channel select
    def getInfosForChannel(self,aChannelString):
        #dayToDayList = self.egpDatabase[aChannelString]
        dayToDayList = self.getDatabase().getInfosForChannel(aChannelString)
        for dayList in dayToDayList:
            if self._config.FUTURE_ITEMS_ONLY:
                dayList[:]=[epgInfo for epgInfo in dayList if epgInfo.isActual()]
        dayToDayList[:]=[dl for dl in dayToDayList if len(dl)>0]
        self.getRecordQueue().markRecordingSlots(dayToDayList)    
        return dayToDayList
    
    def searchInChannel(self,aChannelString,aSearchString):
        dayToDayList = self.getDatabase().getInfosForChannel(aChannelString)
        searchResult=[]
        for dayList in dayToDayList:
            dailySearch=[]
            for epgInfo in dayList:
                if aSearchString in epgInfo.getTitle():
                    dailySearch.append(epgInfo)
            if len(dailySearch)>0:
                searchResult.append(dailySearch)
            
        return searchResult
        
    
    def getChannels(self):
        return self.channelList
    
    '''
    A dictionary with the channel name as key and a list of EpgProgrammInfos
    Data contains recording infos, since read from file cache
    '''
    def readEPGCache(self):
        self._updater.readEPGCache()
        
       
    #invoked on dble click returns true if status could be changed
    def toggleRecordInfo(self,epgInfo,forceRemove=False):
        if epgInfo.isBlockedForRecord():
            return False;
        if epgInfo.isMarkedForRecord():
            return self.getRecordQueue().cancelRecording(epgInfo,forceRemove)
            
        return self.getRecordQueue().addRecording(epgInfo)            
        
        
            
    #Answer the List of the day for this epgInfo (channel included)
    def _getDayList(self,epgInfo):
        aChannelString = epgInfo.getChannel().getName()
        epgDate = epgInfo.getStartTime().date()
        dayToDayList = self.getInfosForChannel(aChannelString)
        for dayList in dayToDayList:
            if dayList[0].getStartTime().date()== epgDate:
                return dayList
        return None
    
    
    ##Called by GUI: reads the EPG data from a configured device within a thread!... 
    def readEPGDeviceData(self):
        self._application.readEPGDeviceData()
    
    #called by DVB Recorder: execution within the thread
    def getEPGUpdater(self):
        return self._updater
 

    
    def getRecordQueue(self):
        return self._updater.getRecordQueue()

    def getDatabase(self):
        return self._updater.getDatabase()

    def getAppIconPath(self):
        return self.getIconPath("dvbrec_tv.svg")
    
    def getIconPath(self,iconName):
        path = self._config.getResourcePath()
        return self._config.getFilePath(path,iconName)
    
    
    #-- The auto select feature
    def getAutoSelector(self):
        return self.getDatabase().getAutoSelector()
    
    