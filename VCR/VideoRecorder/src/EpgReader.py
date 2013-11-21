# -*- coding: utf-8 -*-
'''
Created on Sep 22, 2012
Parses  epg data from a String.
Puts the data into a list of EpgProgramInfo
Since the data retrieved by a device may contain several channels
the epgDictionary is build up as follows:
key= chanel name, value = List[epgchanel infos]
The program infos are not sorted, since frequency blocks are updated sequential...
They are accessed by the EpgProgrammProvider who sorts & converts that data  

Note- there seems to be a time offset in the epg data (Germany)
Seems to be ONE hour early (+1) to get the time right (Summertime?)
@author: matze
'''
import xml.etree.cElementTree as CT
from datetime import datetime, timedelta
import time as xtime
from xml.sax.saxutils import unescape,escape
from threading import Thread
import logging
import sys

class EpgReader:
    def __init__(self,aChannelList):
        #list retrieved by the channel reader. Needed for mapping
        if aChannelList is not None:
            self.channelList=aChannelList
        
    def readCachedXMLFile(self,path):
        if not path:
            return None
        aList=[]
        try:
            with open(path, 'r') as xmlFile:
                xmlData = xmlFile.read()
        except IOError:
            return aList
        
        self.parseXML_TVString(xmlData,aList,UTC=False)
        return aList

    '''
    Parses the xmlstring based on the xmltv structure.
    returns a dictionary with channels as keys and an ordered list of EpgChannelInfo
    '''
    def parseXML_TVString(self,xmlString,aList,UTC):
        try:
            self._readXml(xmlString,aList,UTC)
        except Exception, v:
            data = v.args
            logging.log(logging.ERROR, "Parse Error: "+str(data))
            with open('/tmp/error.xmltv', 'w') as aFile:
                aFile.write(xmlString)
            
    def _findChannel(self,aString):
        #first get the number
        if aString is None:
            return None
        
        tokens = aString.partition(".")
        if len(tokens) == 0:
            return None
        return self._selectChannelFromID(tokens[0])
    
    
    def _selectChannelFromID(self,aString):
        for channel in self.channelList:
            if channel.getChannelID() == aString:
                return channel;
        return None
        
    def convertToDate(self,dateString,UTC):
        if dateString is None:
            dateString="197001010000"

        #rawDatetime = datetime.strptime(dateString,"%Y%m%d%H%M%S") -- Too slow!
        rawDatetime = self.__convertStringToDate(dateString);
        if not UTC:
            return rawDatetime
        utcOffset = xtime.timezone
        return rawDatetime-timedelta(seconds=utcOffset);
    
    def __convertStringToDate(self,dateString):
        year=int(dateString[0:4])
        month=int(dateString[4:6])
        day=int(dateString[6:8])
        hour=int(dateString[8:10])
        minute=int(dateString[10:12])
        sec=0
        return datetime(year,month,day,hour,minute,sec)

        
    
    def _readXml(self,stringData,aList,UTC):
        root = CT.fromstring(stringData)
        for program in root:
            #print program.tag,program.attrib
            epgInfo = EpgProgramInfo()
            #the key of the dictionary
            channelid = program.get('channel');
            channel = self._findChannel(channelid)
            #Put the info into the array (which is still unsorted to time)
            if (channel is not None):
                epgInfo.setChannel(channel)
                aList.append(epgInfo)
            
            
            startTimeString = program.get('start')
            epgInfo.setStartTime(self.convertToDate(startTimeString,UTC))
            endTimeString= program.get('stop')
            epgInfo.setEndTime(self.convertToDate(endTimeString,UTC))
            
            title=program.find('title')
            if title != None:
                epgInfo.setTitle(title.text)

            description = program.find('desc')
            if description != None:
                epgInfo.setDescription(description.text)  
                jobid = description.get('JOBID')
                if jobid != None:
                    epgInfo.setJobID(jobid)
                  

    #write a list of epgInfos Array of daily entries[]
    def dumpEPGData(self,programList,path):
        rootElement = CT.Element('REC')
        for daily in programList:
            for epgInfo in daily:
                self._writeXMLEGPElement(rootElement, epgInfo)

        with open(path, 'w') as aFile:
            CT.ElementTree(rootElement).write(aFile, "utf-8")

                
    def _writeXMLEGPElement(self,rootElement,epgInfo):
        channel = epgInfo.getChannel()
        entry = CT.SubElement(rootElement,"programme")
        entry.attrib["channel"]=channel.getChannelID()+".recQueue"
        entry.attrib["start"]=self._convertTimeToString(epgInfo.getStartTime()) 
        entry.attrib["stop"]=self._convertTimeToString(epgInfo.getEndTime())
        titleEntry =CT.SubElement(entry,"title")
        titleEntry.text= epgInfo.getTitleUnescaped()
        descEntry = CT.SubElement(entry,"desc")
        jobID = epgInfo.getJobID()
        if len(jobID)>0:
            descEntry.attrib["JOBID"]= jobID 
        descEntry.text = epgInfo.getDescriptionUnescaped()
        
        return entry

        
    def _convertTimeToString(self,aDatetime):
        return aDatetime.strftime('%Y%m%d%H%M%S')
        

class EpgProgramInfo:
    
    def __init__(self):
        NotAvailable='n.a.'
        self.startTime=None
        self.endTime=None
        self.channel=NotAvailable
        self.title=NotAvailable
        self.description=NotAvailable
        self.category=NotAvailable
        self._recordBlocked=False
        self._jobID = ""

    '''
    returns a channel object
    '''
    def getChannel(self):
        return self.channel


    def setChannel(self, aChannel):
        if aChannel is not None:
            self.channel = aChannel

    def setStartTime(self,aDateTime):
        self.startTime=aDateTime
    
    def getStartTime(self):
        return self.startTime
    
    def setEndTime(self,aDateTime):
        self.endTime=aDateTime
        
    def getEndTime(self):
        return self.endTime
    
    '''
    @return timedelta...
    '''
    def getDuration(self):
        return self.endTime - self.startTime
    
    def getDurationInSeconds(self):
        td = self.getDuration()
        seconds = td.days * 3600 * 24 + td.seconds
        #return "%s" %(seconds)
        return seconds
    
    def setTitle(self,titleString):
        if titleString is not None:
            self.title = escape(titleString)
        
    def getTitle(self):
        return self.title
    
    def getTitleUnescaped(self):
        return unescape(self.title)
            
    def setDescription(self,aString):
        if aString is not None:        
            self.description=escape(aString)
        
    def getDescription(self):
        return self.description
    
    def getDescriptionUnescaped(self):
        return unescape(self.description)

    def setCategory(self,aString):
        if aString is not None:        
            self.category= aString
    
    def getCategory(self):
        return self.category
    
    # Datetime String like 17:05 28.Oct
    def dateToString(self,aDateTime):
        return aDateTime.strftime("%H:%M %d.%b")
    
    def getStartTimeString(self):
        return self.startTime.strftime("%H:%M")
    
        #Date id as 15.Oct
    def getDateString(self):
        return self.startTime.strftime("%d.%b")
    
    def getStartDateTimeString(self):
        return self.dateToString(self.startTime)
    
    def isMarkedForRecord(self):
        return len(self._jobID)>0

    def markBlocked(self,blockFlag):
        self._recordBlocked=blockFlag

    def isBlockedForRecord(self):
        return self._recordBlocked
    
    def getJobID(self):
        return self._jobID
    
    def setJobID(self,jobid):
        self._jobID= jobid
    
    def isSameDay(self,otherInfo):
        date1=self.getStartTime().date()
        date2=otherInfo.getStartTime().date()
        return date1.day == date2.day and date1.month == date2.month        

    def isActual(self):
        now = datetime.today();
        td = self.getStartTime()-now;
        return self.getEndTime()>= now and td.days<20

        
    #check if the TIME of this overlaps with the other info
    def overlapsWith(self,otherInfo):
        
        oStart = otherInfo.getStartTime()
        oEnd = otherInfo.getEndTime()
        myStart = self.getStartTime()
        myEnd = self.getEndTime()
        return oStart < myEnd and oEnd > myStart
        
    def isAlike(self,otherInfo):
        if not otherInfo:
            return False
        if not self.startTime ==  otherInfo.getStartTime():
            return False
        return self.channel.getChannelID() == otherInfo.getChannel().getChannelID()
         

    def hasSameContent(self,otherInfo):
        if not self.channel.getChannelID() == otherInfo.getChannel().getChannelID():
            return False
        return self.title == otherInfo.getTitle() and self.description == otherInfo.getDescription()

        
    def isTimeShiftedWith(self,otherInfo):
        if self.overlapsWith(otherInfo):
            return self.hasSameContent(otherInfo)
        return False
            
   
    def getString(self):
        test = "?"
        prog= self.getChannel().getName()
        try:
            test= "["+prog+"] "+self.getTitle()+" ("+self.dateToString(self.startTime)+" > "+self.dateToString(self.endTime)+")"
        except:
            error = sys.exc_info()[0]
            logging.log(logging.ERROR,'could not print epg toString:'+str(error))     
        return test

        
class ReaderThread(Thread):
    def __init__(self,isDaemon, target, *args):
        self._target = target
        self._args = args
        Thread.__init__(self)
        self.daemon=isDaemon
 
    def run(self):
        self._target(*self._args)
    
