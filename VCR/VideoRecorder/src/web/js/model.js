

function ServerCommand (command,arg,anObject){
	this.cmd=command;
	this.arg=arg;
	this.data=anObject;
}
	ServerCommand.prototype.stringify= function(key,value){
		if (key=="data"){
			return "";
		}
		return value;
	};

/* Collection of selectable objects. Keeps also the info, which one is selected */
function ProgrammCollection(){
		this.selectedIndex=-1;
		this.items = [];
		this.lastSearchedItemIndex=-1;
}
	ProgrammCollection.prototype.add = function(aProgrammEntry){
		this.items.push(aProgrammEntry);
	};

	ProgrammCollection.prototype.reset = function(){
		this.selectedIndex=-1;
		this.items = [];
	};
	
	ProgrammCollection.prototype.getSelected = function(){
		if (this.selectedIndex<0) {
			return null;
		}
		return this.items[this.selectedIndex]; 
	};

	ProgrammCollection.prototype.getSelectedNode = function(){
		if (this.selectedIndex<0) {
			return null;
		}
		return this.items[this.selectedIndex].domObject;
	};
	
	ProgrammCollection.prototype.unselect = function(){
		this.selectedIndex=-1;
	};
	
	ProgrammCollection.prototype.internalFind = function(startIndex,searchString){
		var regEx = new RegExp(searchString,"i");
		for (i=startIndex; i< this.items.length; i++){ 
			var anItem=this.items[i];
			var result = anItem.jsonData.title.search(regEx);
			if (result >= 0){
				this.lastSearchedItemIndex=i;
				return anItem;
			}
		}
		return null;
	};

	ProgrammCollection.prototype.find = function(searchString){
		this.lastSearchedItemIndex=-1;
		return this.internalFind(0,searchString);
	}


	ProgrammCollection.prototype.findNext = function(searchString){
		if (this.lastSearchedItemIndex<0)
			return this.internalFind(0,searchString);
			
		return this.internalFind(this.lastSearchedItemIndex+1,searchString);
	};

	ProgrammCollection.prototype.findPrevious = function(searchString){
		if (this.lastSearchedItemIndex<0)
			return this.internalFind(0,searchString);
			
		var regEx = new RegExp(searchString,"i");
		for (i=this.lastSearchedItemIndex-1; i>-1; i--){ 
			var anItem=this.items[i];
			var result = anItem.jsonData.title.search(regEx);
			if (result >= 0){
				this.lastSearchedItemIndex=i;
				return anItem;
			}
		}
		return null;
			
	};

/* ListEntry Object for channels */
function ListEntry (index,domObject) {
	this.index = index;
	this.domObject=domObject;
	domObject.model=this;
	
}
	ListEntry.prototype.getIndex = function(){
		return this.index;
	};
	
	ListEntry.prototype.registerEvents= function(){
		this.domObject.addEventListener("click",this.handleChannelClicked,false);
		this.domObject.draggable=true;
		this.domObject.addEventListener("dragstart",this.handleDragStart,false);
		this.domObject.addEventListener("dragenter",this.handleDragEnter,false)
		this.domObject.addEventListener("dragover",this.handleDragOver,false)
		this.domObject.addEventListener("dragleave",this.handleDragLeave,false);
		this.domObject.addEventListener("drop",this.handleDrop,false);
	};
	/* context here is the dom object, not the ListEntry object */
	ListEntry.prototype.handleChannelClicked = function(event) {
		var nbrString=this.model.getIndex();
		var selectedChannel = channelList.getSelected();
		if (selectedChannel != null){
			selectedChannel.removeSelection();
		}
		selectedChannel=this.model;
		channelList.selectedIndex=selectedChannel.index;
		var name = this.textContent;
		executeServerCommand(new ServerCommand("REQ_Programs",name));
	};

	/*Context DOM object*/
	ListEntry.prototype.handleDragStart = function(event){
		event.dataTransfer.setData("text", event.target.id);
		return true;
	};

	ListEntry.prototype.handleDragEnter = function(event){
		event.preventDefault();
		var node = event.target;
		
		var targetRect = node.getBoundingClientRect();
		var currentPos = event.clientY;
		if (targetRect.top-currentPos > currentPos-targetRect.bottom){
			node.style.borderTop ="solid blue 2px";
			node.style.borderBottom="none";
		}
		else {
			node.style.borderTop ="none";
			node.style.borderBottom ="solid blue 2px";
		}
	};

	ListEntry.prototype.handleDragOver = function(event){
		event.preventDefault();
	}

	ListEntry.prototype.handleDragLeave = function(event){
		var node = event.target;
		node.style.borderTop ="none";
		node.style.borderBottom="none";
		event.preventDefault();
	};

	ListEntry.prototype.handleDrop = function(event){
		var node = event.target;
		node.style.borderTop ="none";
		node.style.borderBottom="none";
		var sourceId = event.dataTransfer.getData("text");
		var domList=node.parentNode;
		
		var targetRect = node.getBoundingClientRect();
		var currentPos = event.clientY;
		var sourceNode= document.getElementById(sourceId);

		if (targetRect.top-currentPos > currentPos-targetRect.bottom){
			/*above*/
			domList.insertBefore(sourceNode,node);
		}
		else {
			/*below*/
			if (domList.lastchild == node){
				domList.appendChild(sourceNode);
			}
			else 
				domList.insertBefore(sourceNode,node.nextSibling);
			
		}
		
		/*update local storage*/
		children= domList.childNodes;
		var items=[];
		for (i=0; i< children.length; i++){
			items.push(children[i].textContent);
		}
		localStorage[CHANNEL_KEY] = JSON.stringify(items);
		event.preventDefault();
	};


	ListEntry.prototype.getTitle = function(){
		return this.domObject.textContent;
	};

	ListEntry.prototype.removeSelection = function(){
		this.domObject.className="ChannelItem";
	};
	
	ListEntry.prototype.setSelection = function(){
		this.domObject.className="channelSelected";
	};



/*programm row */
function ProgramEntry (index,epgInfo,domObject) {
	this.index = index;
	this.domObject=domObject;
	this.jsonData = epgInfo;
	domObject.model=this;
	
}
	ProgramEntry.prototype.getIndex = function(){
		return this.index;
	};
	
	ProgramEntry.prototype.registerEvents= function(){
		this.domObject.addEventListener("dblclick",this.handleDbleClicked,false);
		this.domObject.draggable=true;
		this.domObject.addEventListener("dragstart",this.handleDragStart,false);
		this.domObject.addEventListener("click",this.handleClicked,false);
	};
	
	//JS context: this is DOM not the object...
	ProgramEntry.prototype.handleClicked = function(event) {
		var node = programmList.getSelectedNode();
		if (node != null){
			removeClassName(node,"channelSelected");
		};
		
		if (node==this){
			programmList.unselect();
			return;
		}
		programmList.selectedIndex=this.model.getIndex();
		addClassName(this,"channelSelected");
	};

	//JS context: this is DOM not the object...
	ProgramEntry.prototype.handleDbleClicked = function(event) {
		programmList.selectedIndex=this.model.getIndex();
		var jString=JSON.stringify(this.model.jsonData);
		executeServerCommand(new ServerCommand("MARK_Programm",jString,this.model));
	};
	
	//JS context: this is DOM not the object...
	ProgramEntry.prototype.handleDragStart = function(event) {
		if (!this.model){
			this.style.cursor="no-drop";
			return;
		}
		var nbrString=this.model.getIndex();
		console.log("dragging:"+nbrString);
		this.model.draggable=true;
		//Sets the node id for retrieval if dropped
		event.dataTransfer.setData("text", this.id);
		return true;
		
	};

	ProgramEntry.prototype.updateProgrammInfo = function(jsonData){
		//happens on program list toggle - update alter the icon..
		if (jsonData=="None"){
			showStatus("Toggle Recording failed");
			return; 
		}
		var epgInfo = JSON.parse(jsonData);
		var selectedNode=this.domObject;
		var child= getChildByClass(selectedNode,"Column1")
		if (child !=null){
			removeDOMChildren(child);
			var recMode = epgInfo.recordMode;
			if (recMode>MODE_DATA){
				var img = document.createElement("IMG");
				if (recMode==MODE_REC)
					img.src = "img/"+"RecIcon.png";
				else 
					img.src = "img/"+"NotAvailable.png";
				child.appendChild(img);
			}
		}
		
		if (epgInfo.error != null)
			showStatus(epgInfo.error);
		else
			showStatus("Ready");	
};	



//-- List Builder functions
//ProgrammList
function ProgramListBuilder(serverData) {
	this.jsonResult=serverData;
}
	ProgramListBuilder.prototype.updateProgrammList=function(){
	var programmDOM=document.getElementById("programmbody");
	var rootDOM = programmDOM.parentNode
	//disconnect
	rootDOM.removeChild(programmDOM)
	removeDOMChildren(programmDOM);
	programmList=new ProgrammCollection();
	if (this.jsonResult=="None"){
		this.showNoData(programmDOM);
		rootDOM.appendChild(programmDOM)
		return false;
	}

	var daybydayList = JSON.parse(this.jsonResult);
	if (daybydayList.error != null){
		this.showNoData(programmDOM);
		showStatus("Error -"+daybydayList.args);
		rootDOM.appendChild(programmDOM)
		return false;
	}
	var index=0;
	var addHeaderData=false
	for (dx=0; dx< daybydayList.length; dx++){ 
		var dayList=daybydayList[dx];
		var header = dayList.head;
		var dailyProgramList = dayList.list;
		this.createProgramHeader(programmDOM,header,dx);
		for (i=0; i< dailyProgramList.length; i++){ 
			var epgInfo = dailyProgramList[i];
			var programm=this.createProgramEntry(addHeaderData,programmDOM,epgInfo,index);
			index++;
			programmList.add(programm);
		}
	}
	rootDOM.appendChild(programmDOM);
	return true;
};

	ProgramListBuilder.prototype.showNoData = function(mainDOM){
		showMessageInProgrammArea("No Data found",mainDOM);
		return false;
	}
	
	/* creates the "day" header in the program list*/
	ProgramListBuilder.prototype.createProgramHeader = function(node,header,dayId){
		var row = document.createElement("div");
		row.id="dayID"+dayId;
		row.className="dayrow";
		row.dayIndex=dayId;
		var code = document.createElement("div");
		code.className="Column2";
		var textDOM=document.createElement("p");
		textDOM.innerHTML=header.text;
		code.appendChild(textDOM);
		row.appendChild(code);
		node.appendChild(row)
	};

	ProgramListBuilder.prototype.createProgramEntry = function(showFullData,node,epgInfo,rowIndex){
		var row = document.createElement("div");
		row.id="progitem_"+rowIndex;
		if (rowIndex%2==0){
			row.className="programmrow evenrow";	
		}
		else {
			row.className="programmrow oddrow";	
		}
			
		var icoCol = document.createElement("div");
		icoCol.className="Column1";
		
		//record mode
		var recMode = epgInfo.recordMode;
		if (recMode>MODE_DATA){
			var img = document.createElement("IMG");
			if (recMode==MODE_REC){
				img.src = "img/"+"RecIcon.png";
			}
			else {
				img.src = "img/"+"NotAvailable.png";
			}
			icoCol.appendChild(img);
		}
		row.appendChild(icoCol);

		if (showFullData){
			var infoPlus = document.createElement("div");
			infoPlus.className="ColumnInfoPlus"
			infoPlus.innerHTML= "<b>"+epgInfo.channel+"</b> "+epgInfo.date+"<br>&zwnj;";
			row.appendChild(infoPlus);
		}

		var timeCol = document.createElement("div");
		if (epgInfo.epgOK)
			timeCol.className="ColumnTime";
		else
			timeCol.className="ColumnTimeGap"; //Mark it red if a gap exists
			
		timeCol.innerHTML= epgInfo.time+"<br>&zwnj;"; //TODO a hack wg. right border
		row.appendChild(timeCol);

		var code = document.createElement("div");
		code.className="Column2";
		code.innerHTML=epgInfo.text;
		row.appendChild(code);
		node.appendChild(row)
		var prog = new ProgramEntry(rowIndex,epgInfo,row);
		prog.registerEvents();
		return prog;
	};
	

// ------------- Recording list builder ---------------------
var updateRecordList=function(jsonResult){
	var recordListDOM=document.getElementById("recordlist");
	removeDOMChildren(recordListDOM);
	if (jsonResult=="None"){
		return;
	}
	var epgInfos = JSON.parse(jsonResult);
	if (epgInfos.error != null){
		showStatus("Error retrieving data:"+epgInfos.args);
		return;
	}
	var count = epgInfos.length;
	for (i=0; i< count; i++){ 
		var row = document.createElement("div");
		if (i%2==0){
			row.className="InfoRow evenrow";	
		}
		else {
			row.className="InfoRow oddrow";	
		}
		row.id="infoitem_"+i;
		var timeCol = document.createElement("div");
		timeCol.className="InfoChannel";
		timeCol.innerHTML=epgInfos[i].timetext;
		row.appendChild(timeCol);
		
		var marginCol= document.createElement("div");
		marginCol.className="RecMargins";
		/*data will be set with #updateMargins*/
		row.appendChild(marginCol);
		
		var infoCol= document.createElement("div");
		infoCol.className="InfoText";
		infoCol.innerHTML= epgInfos[i].text;
		row.appendChild(infoCol)
		var recEntry = new SelectionEntry(i-1,epgInfos[i],row);
		recordListDOM.appendChild(row);
     	recEntry.registerEvents();

		m1=epgInfos[i].marginStart;
		m2=epgInfos[i].marginStop;
		recEntry.updateMargins(m1,m2);

		var domRecStart = document.getElementById("recStart");
		var domRecEnd = document.getElementById("recEnd");
     	domRecStart.value="";
     	domRecEnd.value="";
     	showStatus("Record list loaded");
	}	
	//TODO log errors
};

//Right now the entry is the selection entry of a recording list!!!
function SelectionEntry (index,epgInfo,domObject) {
	this.index = index;
	this.domObject=domObject;
	domObject.model=this;
	this.jsonData = epgInfo;
}
    
	SelectionEntry.prototype.registerEvents= function(){
		this.domObject.addEventListener("dblclick",this.handleDbleClicked,false);
		this.domObject.addEventListener("click",this.handleClicked,false);
	};

    //context DOM not object
	SelectionEntry.prototype.handleDbleClicked = function(event) {
		//class because of a click handle? Make you own handler!
		var jString=JSON.stringify(this.model.jsonData);
		executeServerCommand(new ServerCommand("MARK_Programm",jString,this.model));
		//refresh the list
		refreshProgrammList();
	};
	
	//context DOM not object
	SelectionEntry.prototype.handleClicked = function(event) {
		previousSelection = currentRecListSelection;
		if (previousSelection != null)
			previousSelection.removeSelection();
		currentRecListSelection = this.model;
		currentRecListSelection.setSelection();
		//now set the current margins to the two entry fields
		var domRecStart = document.getElementById("recStart");
		var domRecEnd = document.getElementById("recEnd");
		
		m1=this.model.jsonData.marginStart;
		m2=this.model.jsonData.marginStop;
		var startMargin = secondStringToMinutes(m1);
		var endMargin = secondStringToMinutes(m2);
		domRecStart.value = startMargin;
		domRecEnd.value = endMargin;

	};
	
	SelectionEntry.prototype.removeSelection = function() {
		removeClassName(this.domObject,"channelSelected");
	};
	
	SelectionEntry.prototype.setSelection = function(){
		addClassName(this.domObject,"channelSelected");
	};
	
	//called by server command (MARK_Programm)
	SelectionEntry.prototype.updateProgrammInfo = function(jsonData){
		//happens on program list toggle - update alter the icon..
		if (jsonData=="None"){
			showStatus("Toggle Recording failed");
			return; 
		}
		var epgInfo = JSON.parse(jsonData);
		var selectedNode=this.domObject;
		var parentNode= selectedNode.parentNode;
		var recMode = epgInfo.recordMode;
		if (recMode!=MODE_REC && parentNode!=null)
			parentNode.removeChild(selectedNode);
	}
	
	SelectionEntry.prototype.updateMargins = function (prerunSeconds, postrunSeconds){
		this.jsonData.marginStart = prerunSeconds;
		this.jsonData.marginStop = postrunSeconds;
		
		var startMargin = secondStringToMinutes(prerunSeconds);
		var endMargin = secondStringToMinutes(postrunSeconds);
		
		var marginDOM = this.domObject.childNodes.item(1);
		var ico = "\u25ca";
		marginDOM.innerHTML= startMargin+"<"+ ico + ">"+endMargin;
	}


var handleRecButtonChangeTime=function(event){
	if (currentRecListSelection == null)
		return;
		
	delta = 5;
	var domRecStart = document.getElementById("recStart");
	var domRecEnd = document.getElementById("recEnd");
	switch (this.id){
		case "rec1p":
		  var minutes = parseInt(domRecStart.value);
		  minutes+=delta;
		  domRecStart.value=minutes;			
		break;
		case "rec1m":
		    var minutes = parseInt(domRecStart.value);
			minutes = Math.max(0,minutes-=delta);
			domRecStart.value=minutes;
		break;
		case "rec2p":
		    var minutes = parseInt(domRecEnd.value);
			minutes+=delta;			
			domRecEnd.value=minutes;
		break;
		case "rec2m":
		    var minutes = parseInt(domRecEnd.value);
			minutes = Math.max(0,minutes-=delta);		
			domRecEnd.value=minutes;
		break;
		
		default:
			return;
	}
	//update the stuff in the list. when closed save it.
	//must be seconds /string
	var secsStart = minuteStringToSeconds(domRecStart.value)
	var secsEnd = minuteStringToSeconds(domRecEnd.value)
	currentRecListSelection.updateMargins(secsStart,secsEnd);


};	
//called on close of the rec overlay
var onOverlayClose=function(event){
	var recordListDOM=document.getElementById("recordlist");
	children= recordListDOM.childNodes;
	var items=[];
	for (i=0; i< children.length; i++){
		var recData = children[i].model.jsonData;
		var dataDict={};
		dataDict["jobID"] = recData.jobID;
		dataDict["marginStop"] = recData.marginStop;
		dataDict["marginStart"] = recData.marginStart;
		items.push(dataDict);
	}
	var jString=JSON.stringify(items);
	executeServerCommand(new ServerCommand("REC_MARGINS",jString));
};

//----------- Autoselect section ---------------------
var updateAutoselectList=function(jsonResult){
	var recordListDOM=document.getElementById("autoselectlist");
	removeDOMChildren(recordListDOM);
	var autoSelectList;
	if (jsonResult!="None"){
		var autoSelectData = JSON.parse(jsonResult);
		var weekModes = autoSelectData.weekTypes;
		var autoSelectList = autoSelectData.elements;
		if (autoSelectList.error != null){
			showStatus("Error retrieving data:"+epgInfos.args);
			return;
		}
	}
	var count = autoSelectList.length;
	for (i=0; i< count; i++){ 
		var row = document.createElement("div");
		if (i%2==0){
			row.className="InfoRow evenrow";	
		}
		else {
			row.className="InfoRow oddrow";	
		}
		row.id="infoitem_"+i;
		var timeCol = document.createElement("div");
		timeCol.className="InfoTime";
		timeCol.innerHTML=autoSelectList[i].timetext;
		row.appendChild(timeCol);

		var chanCol= document.createElement("div");
		chanCol.className="InfoChannel";
		chanCol.innerHTML= autoSelectList[i].chanID;
		row.appendChild(chanCol);
		
		var chanPeriod= document.createElement("div");
		chanPeriod.className="InfoPeriod";

		
		var selector = document.createElement("select");
		for (k=0; k< weekModes.length; k++){
		  var opt = document.createElement("option");
		  opt.text=weekModes[k];    
		  opt.value=k;
		  selector.appendChild(opt);
		}
		selector.value=autoSelectList[i].weekMode;/*the id*/
		selector.addEventListener("change",setAutoselectionWeekMode,false);
		chanPeriod.appendChild(selector);
		row.appendChild(chanPeriod);

		var infoCol= document.createElement("div");
		infoCol.className="InfoText";
		infoCol.innerHTML= autoSelectList[i].text;
		row.appendChild(infoCol);
		
		//var listEntry = new SelectionEntry(i-1,epgInfos[i],row);
		//TRY a basic approach without model..
		row.addEventListener("dblclick",handleAutoSelectDbleClicked,false);
		row.jsonData=autoSelectList[i];
		recordListDOM.appendChild(row);
	}	
	showStatus("Idle");
};

function setAutoselectionWeekMode(event){
  var hugo = this.parentNode.parentNode.jsonData;
  hugo.weekMode = this.value;
  var jString=JSON.stringify(hugo);
  executeServerCommand(new ServerCommand("AUTO_WEEKMODE",jString,this));
}

//Basic autoselect approach
function handleAutoSelectDbleClicked(event){
	var jString=JSON.stringify(this.jsonData);
	executeServerCommand(new ServerCommand("RM_AUTOSELECT",jString,this));
};

function refreshAutoSelectList(selectedNode){
		var parentNode= selectedNode.parentNode;
		//TODO no error handling, nothing...
		parentNode.removeChild(selectedNode);
		showStatus("Idle");
}

//-- search function create a seach list...---
function createSearchList(jsonResult){
	var programmDOM=document.getElementById("programmbody");
	var rootDOM = programmDOM.parentNode
	//disconnect
	rootDOM.removeChild(programmDOM)
	removeDOMChildren(programmDOM);
	if (jsonResult=="None"){
		this.showMessageInProgrammArea("Broken search",programmDOM);
		rootDOM.appendChild(programmDOM)
		return false;
	}

	var result = JSON.parse(jsonResult);
	
	if (result.error != null){
		this.showMessageInProgrammArea("Search error",programmDOM);
		showStatus(result.error);
		rootDOM.appendChild(programmDOM);
		return false;
	}
	var epgInfos = result.list;
	//now lets build something	
	var builder = new ProgramListBuilder(null);
	for (i=0; i< epgInfos.length; i++){ 
		builder.createProgramEntry(true,programmDOM,epgInfos[i],i);
	}
	
	//this.showMessageInProgrammArea("Not implemented yet",programmDOM);
	rootDOM.appendChild(programmDOM)
	showStatus("Idle "+epgInfos.length);
}
