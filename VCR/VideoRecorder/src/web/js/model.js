

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
				lastSearchedItemIndex=i;
				return anItem;
			}
		}
		return null;
	};

	ProgrammCollection.prototype.find = function(searchString){
		lastSearchedItemIndex=-1;
		return this.internalFind(0,searchString);
	}


	ProgrammCollection.prototype.findNext = function(searchString){
		if (lastSearchedItemIndex<0)
			return this.internalFind(0,searchString);
			
		return this.internalFind(lastSearchedItemIndex+1,searchString);
	};

	ProgrammCollection.prototype.findPrevious = function(searchString){
		if (lastSearchedItemIndex<0)
			return this.internalFind(0,searchString);
			
		var regEx = new RegExp(searchString,"i");
		for (i=lastSearchedItemIndex-1; i>-1; i--){ 
			var anItem=this.items[i];
			var result = anItem.jsonData.title.search(regEx);
			if (result >= 0){
				lastSearchedItemIndex=i;
				return anItem;
			}
		}
		return null;
			
	};

/* ListEntry Object */
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
		this.domObject.draggable=false;
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

	ListEntry.prototype.getTitle = function(){
		return this.domObject.textContent;
	};

	ListEntry.prototype.removeSelection = function(){
		this.domObject.className="ChannelItem";
	};
	
	ListEntry.prototype.setSelection = function(){
		this.domObject.className="channelSelected";
	};

function SelectionEntry (index,epgInfo,domObject) {
	this.index = index;
	this.domObject=domObject;
	domObject.model=this;
	this.jsonData = epgInfo;
}
    
	SelectionEntry.prototype.registerEvents= function(){
		this.domObject.addEventListener("dblclick",this.handleDbleClicked,false);
	};

    //context DOM not object
	SelectionEntry.prototype.handleDbleClicked = function(event) {
		//class because of a click handle? Make you own handler!
		var jString=JSON.stringify(this.model.jsonData);
		executeServerCommand(new ServerCommand("MARK_Programm",jString,this.model));
		//refresh the list
		refreshProgrammList();
	};
	
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
	removeDOMChildren(programmDOM);
	programmList=new ProgrammCollection();
	if (this.jsonResult=="None"){
		var row = document.createElement("div");
		row.className="dayrow"; //should be error row or icon or so
		row.innerHTML="No Data found";
		programmDOM.appendChild(row);
		return false;
	}

	var daybydayList = JSON.parse(this.jsonResult);
	if (daybydayList.error != null){
		showStatus("Error -"+daybydayList.args);
		return false;
	}
	var index=0;
	for (dx=0; dx< daybydayList.length; dx++){ 
		var dayList=daybydayList[dx];
		var header = dayList.head;
		var dailyProgramList = dayList.list;
		this.createProgramHeader(programmDOM,header,dx);
		for (i=0; i< dailyProgramList.length; i++){ 
			var epgInfo = dailyProgramList[i];
			var programm=this.createProgramEntry(programmDOM,epgInfo,index);
			index++;
			programmList.add(programm);
		}
	}
	return true;
};

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

	ProgramListBuilder.prototype.createProgramEntry = function(node,epgInfo,rowIndex){
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

		var timeCol = document.createElement("div");
		timeCol.className="ColumnTime";
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
	

//Recording list builder
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
		timeCol.className="InfoTime";
		timeCol.innerHTML=epgInfos[i].timetext;
		row.appendChild(timeCol);
		var infoCol= document.createElement("div");
		infoCol.className="InfoText";
		infoCol.innerHTML= epgInfos[i].text;
		row.appendChild(infoCol)
		var listEntry = new SelectionEntry(i-1,epgInfos[i],row);
		recordListDOM.appendChild(row);
     	listEntry.registerEvents();
     	showStatus("Record list loaded");
	}	
	//TODO log errors
};

var updateAutoselectList=function(jsonResult){
	var recordListDOM=document.getElementById("autoselectlist");
	removeDOMChildren(recordListDOM);
	var autoSelectList;
	if (jsonResult!="None"){
		autoSelectList = JSON.parse(jsonResult);
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
		var infoCol= document.createElement("div");
		infoCol.className="InfoText";
		infoCol.innerHTML= autoSelectList[i].text;
		row.appendChild(infoCol)
		//var listEntry = new SelectionEntry(i-1,epgInfos[i],row);
		//TRY a basic approach without model..
		row.addEventListener("dblclick",handleAutoSelectDbleClicked,false);
		row.jsonData=autoSelectList[i];
		recordListDOM.appendChild(row);
		showStatus("Idle");
	}	
};
//Basic autoselect approach
function handleAutoSelectDbleClicked(event){
	var jString=JSON.stringify(this.jsonData);
	executeServerCommand(new ServerCommand("RM_AUTOSELECT",jString,this));
}

function refreshAutoSelectList(selectedNode){
		var parentNode= selectedNode.parentNode;
		//TODO no error handling, nothing...
		parentNode.removeChild(selectedNode);
		showStatus("Idle");
}
