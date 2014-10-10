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
from xml.sax.saxutils import escape
from threading import Thread
import logging
import sys

class EpgReader:
    def __init__(self,aChannelList):
        #list retrieved by the channel reader. Needed for mapping
        if aChannelList is not None:
            self._chanTable={}
            for channel in aChannelList:
                self._chanTable.setdefault(channel.getChannelID(),channel)
    
    '''
    Parses the xmlstring based on the xmltv structure.
    The EPG Reader plugin may be subclassed to create different types of EPGInfos (aka Recinfo etc)
    '''
    def readCachedXMLFile(self,epgReaderPlug,path):
        if not path:
            return None
        try:
            with open(path, 'r') as xmlFile:
                epgReaderPlug.xmlString = xmlFile.read();
        except IOError:
            return []
        
        #self.parseXML_TVString(xmlData,aList,UTC=False)
        self.convertXMLToEPG(epgReaderPlug)
        return epgReaderPlug.resultList


    def convertXMLToEPG(self,epgReaderPlug):
        try:
            self._xmlToEPG(epgReaderPlug)
        except Exception, v:
            data = v.args
            logging.log(logging.ERROR, "Parse Error: "+str(data))
            with open('/tmp/error.xmltv', 'w') as aFile:
                aFile.write(epgReaderPlug.xmlString)

    
    def _xmlToEPG(self,epgReaderPlug):
        root = CT.fromstring(epgReaderPlug.xmlString)
        for cElement in root:
            epgInfo=epgReaderPlug.createEpgObject()
            validInfo = epgInfo.createFromXMLElement(self,cElement,epgReaderPlug.isUTC)
            epgReaderPlug.addToResult(validInfo)
            
    def _findChannel(self,aString):
        #first get the number
        if aString is None:
            return None
        tokens = aString.partition(".")
        if len(tokens) == 0:
            return None
        return self._selectChannelFromID(tokens[0])
    
    
    def _selectChannelFromID(self,aString):
        return self._chanTable.get(aString)
        
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

        
    
#     def _readXml(self,stringData,aList,isUTC):
#         root = CT.fromstring(stringData)
#         for program in root:
#             epgInfo = self.createFromXMLElement(program,isUTC)
#             
#             if epgInfo is not None:
#                 aList.append(epgInfo)
                  

    '''
    creates EPGProgrammInfo from xml data. Interprets time either as UTC
    or local time 
    '''
#     def createFromXMLElement(self,cElement,isUTC):
#         epgInfo = EpgProgramInfo()
#         return epgInfo.createFromXMLElement(self,cElement,isUTC)
         

    '''
    The xml parser expects unicode for conversion:
    >>Python tries to convert the regular string to Unicode, which is the more general type, 
    but because you don't specify an explicit conversion, it uses the ASCII codec
    
    Right now data is kept as ascii <str>, encoded in "setTitle" and "setDescription"
    
    write a list of epgInfos Array of daily entries[]     
    '''                
    def dumpEPGData(self,programList,path):
        rootElement = CT.Element('REC')
        for daily in programList:
            for epgInfo in daily:
                if epgInfo.isConsistent:
                    epgInfo.storeAsXMLElement(self,rootElement)

        with open(path, 'w') as aFile:
            CT.ElementTree(rootElement).write(aFile, "utf-8")

        
    def _convertTimeToString(self,aDatetime):
        return aDatetime.strftime('%Y%m%d%H%M%S')


'''
EPG Info plugin, may be subclassed for epg creation
'''
class EpgReaderPlugin():
    def __init__(self,xmlData,isUTCTime=False):
        self.xmlString=xmlData
        self.resultList=[]
        self.isUTC=isUTCTime
    
    def createEpgObject(self):
        return EpgProgramInfo()     
    
    def addToResult(self,epgInfo):
        if epgInfo is not None:
            self.resultList.append(epgInfo)
        
           

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
        self.isConsistent = True #False if previous or adjacent entry does not follow immediately (EPG error)

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
            self.title = titleString.encode('utf-8')
            
        
    def getTitle(self):
        return self.title
    
    #deprecated
    def getTitleEscaped(self):
        return escape(self.title)
            
    def setDescription(self,aString):
        if aString is not None:
            #self.description=escape(aString)
            self.description=aString.encode('utf-8')
        
    def getDescription(self):
        return self.description
    
    #deprecated
    def getDescriptionEscaped(self):
        return escape(self.description)

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
    
    def getEndTimeString(self):
        return self.endTime.strftime("%H:%M")
    
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

    '''
    Indicates that this entry starts at one day and end the next day
    '''
    def isOverMidnight(self):
        date1=self.getStartTime().date()
        date2=self.getEndTime().date()
        return date1.day != date2.day

    def isActual(self,timeNow):
        #now = datetime.today();
        td = self.getStartTime()-timeNow;
        return self.getEndTime()>= timeNow and td.days<20

        
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
        testWorkthread = "?"
        prog= self.getChannel().getName()
        try:
            testWorkthread= "["+prog+"] "+self.getTitle()+" ("+self.dateToString(self.startTime)+" > "+self.dateToString(self.endTime)+")"
        except UnicodeDecodeError,ex:
            error = sys.exc_info()[0]
            msg= "Unicode error: "+str(ex.args[0])
            logging.log(logging.ERROR,msg)
            logging.log(logging.ERROR,' Sys Error:'+str(error))
                
        return testWorkthread

    #-XML part
    '''
    setup self from XML data. 
    Note that all Strings will be encoded here (in the string setter methods) 
    '''
    def createFromXMLElement(self,builder,program,isUTC):
        
        #the key of the dictionary
        channelid = program.get('channel');
        channel = builder._findChannel(channelid)
        #Put the info into the array (which is still unsorted to time)
        if (channel is None):
            return None
        
        self.setChannel(channel)            
        startTimeString = program.get('start')
        self.setStartTime(builder.convertToDate(startTimeString,isUTC))
        endTimeString= program.get('stop')
        self.setEndTime(builder.convertToDate(endTimeString,isUTC))
        
        title=program.find('title')
        if title != None:
            self.setTitle(title.text)

        description = program.find('desc')
        if description != None:
            self.setDescription(description.text)  
            jobid = description.get('JOBID')
            if jobid != None:
                self.setJobID(jobid)
        
        return self    

    '''
    Store as XML element - return an subelement to store
    Note that the text text is decoded from utf-8
    '''
    def storeAsXMLElement(self,builder,rootElement):
        channel = self.getChannel()
        entry = CT.SubElement(rootElement,"programme")
        entry.attrib["channel"]=channel.getChannelID()+".recQueue"
        entry.attrib["start"]=builder._convertTimeToString(self.getStartTime()) 
        entry.attrib["stop"]=builder._convertTimeToString(self.getEndTime())
        titleEntry =CT.SubElement(entry,"title")
        titleEntry.text=  self.getTitle().decode('utf-8')
        descEntry = CT.SubElement(entry,"desc")
        jobID = self.getJobID()
        if len(jobID)>0:
            descEntry.attrib["JOBID"]= jobID 
        descEntry.text = self.getDescription().decode('utf-8')
        
        return entry

        
class ReaderThread(Thread):
    def __init__(self,isDaemon, target, *args):
        self._target = target
        self._args = args
        Thread.__init__(self)
        self.daemon=isDaemon
 
    def run(self):
        self._target(*self._args)
    
