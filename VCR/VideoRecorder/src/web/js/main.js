var isFilterOn=false;

var channelList= null;
var programmList= null;
//constanst definition
var TYPE_HEAD=0;
var TYPE_PROG=1;
var TYPE_INFO=2;

var MODE_DATA = 0xA0;
var MODE_REC = 0xA1;
var MODE_BLOCK = 0xA3;

/*TODO: use local store for this kind of data. Keeps it over a refresh!*
 * Note:
 * var functionX = function() == is defined at runtime, calls muss lie below it.
 * function functionX() == defined at parse time, so refrences can be anywhere
 */

var initialize = function(){
	connectToServer();
	hookActionEvents();
};

function refreshProgrammList(){
	this.executeServerCommand(new ServerCommand("REQ_Programs",channelList.getSelected().getTitle()));
};


//var txt = function is a class, not a function?
function connectToServer(){
	this.showStatus("..connecting");
	this.executeServerCommand(new ServerCommand("REQ_Channels",""));
};


function executeServerCommand(aServerCommand){
	this.showStatus("..reading");
	var url="cmd";
	var jCommand = JSON.stringify(aServerCommand,aServerCommand.stringify);
	var request = new XMLHttpRequest();
	request.open("POST",url,false);
	request.onload = function() {
		if (request.status==200){
			handleServerResponse(aServerCommand,request.responseText);
		}
	};
	try {
		request.send(jCommand);
	}
	catch(err){
		showStatus(err.message);
	}
	
};

function handleServerResponse(aServerCommand,jsonResult){
	var command = aServerCommand.cmd;
	if (command=="REQ_Channels"){
		updateChannels(jsonResult);
		refreshProgrammList();
		return;
	} 
	if (command=="REQ_Programs"){
		updateProgrammList(jsonResult);
		isFilterOn=false;
		return;
	}

	if (command=="MARK_Programm"){
		//var builder= new ProgramListBuilder(jsonResult);
		//builder.updateProgrammInfo(aServerCommand.data);
		aServerCommand.data.updateProgrammInfo(jsonResult);
		return;
	}
	
	if (command=="FILTER"){
		updateProgrammList(jsonResult);
		isFilterOn=true;
		return;
	}

	if (command=="LIST_REC"){
		updateRecordList(jsonResult);
		return;
	}
	if (command=="LIST_AUTO"){
		updateAutoselectList(jsonResult);
		return;
	}
	if (command=="AUTO_SELECT"){ //DnD add to autoselect
		console.log("select done");
		return;
	}
	
	if (command=="RM_AUTOSELECT"){ 
		refreshAutoSelectList(aServerCommand.data);
		return;
	}


};

/* ---- serverfunctions ----*/
function updateChannels(jsonResult){
	channelList = new ProgrammCollection();
	var channels = JSON.parse(jsonResult);
	if (channels.error != null){
		showStatus("Error retrieving data:"+channels.args);
		return;
	}
	var count = channels.length;
	var channelDOM=document.getElementById("channel_contents");
	for (i=0; i< count; i++){ 
		var li= document.createElement("li");
		/*textContent replaces innerText and is W3C compliant*/
		li.className="ChannelItem";
		li.textContent=channels[i];
		li.id="channel_"+(i+1);
		channelDOM.appendChild(li);
		var listEntry = new ListEntry(i,li);
		listEntry.registerEvents();
		channelList.add(listEntry);
	}
	channelList.selectedIndex=0;
	showStatus("Channels loaded");
};


function updateProgrammList(jsonResult){
	var builder = new ProgramListBuilder(jsonResult);
	if (builder.updateProgrammList()){
		channelList.getSelected().setSelection();
		showStatus("Infos loaded");
	}
};



//---------------- Action events from buttons, DnD and List ----------
var hookActionEvents = function(){
	//var nodes = document.getElementsByClassName("icoAction");
	//Connect the buttons to events
	
	button = document.getElementById("logBtn");
	button.addEventListener("click",handleShowLogClicked,false);

	var button = document.getElementById("reclistBtn");
	button.addEventListener("click",handleRecListClicked,false);
	
	button = document.getElementById("filterBtn");
	button.addEventListener("click",handleFilterClicked,false);
	
	button = document.getElementById("nextPageBtn");
	button.addEventListener("click",handleNextDayClicked,false);
	
	button = document.getElementById("prevPageBtn");
	button.addEventListener("click",handlePreviousDayClicked,false);
	

	
	
	var dropzone = document.getElementById("dropzone");
	dropzone.addEventListener("dragover",this.handleDragenter,false);
	dropzone.addEventListener("dragleave",this.handleDragleave,false);
	dropzone.addEventListener("drop",this.handleDrop,false);
	dropzone.addEventListener("click",handleAutoListClicked,false);
	
	var input = button = document.getElementById("search");
	input.addEventListener("keyup",this.handleKeypress,false);
};

//--- DnD action handler -----
var handleDragenter= function(event){
	var node = event.target;
	if (event.target.id.length==0){
		node= node.parentNode;
	}
	console.log("dragenter:"+node.id+">"+event.target.id);
	event.preventDefault();
	node.style.webkitTransform="scale(1.4,1.4)";
	node.style.transform="scale(1.5,1.5)";
};

var handleDragleave= function(event){
	var node = event.target;
	if (event.target.id.length==0){
		node= node.parentNode;
	}
	console.log("dragleave:"+node.id+">"+event.target.id);
	event.preventDefault();
	node.style.webkitTransform="scale(1,1)";
	node.style.transform="scale(1,1)";
};

var handleDrop= function(event){
	event.preventDefault();
	var node = event.target;
	if (event.target.id.length==0){
		node= node.parentNode;
	}
	console.log("droping:"+node.id);
	node.style.webkitTransform="scale(1,1)";
	node.style.transform="scale(1,1)";
	var id=event.dataTransfer.getData("text");
	if (id=="")
		return;
	var node = document.getElementById(id);
	console.log("Auto select von: "+node);
	var jString=JSON.stringify(node.model.jsonData);
	executeServerCommand(new ServerCommand("AUTO_SELECT",jString));
};


//--Autoselect click handler
var handleAutoListClicked= function(event) {
	console.log("auto list clicked:"+event);
	executeServerCommand(new ServerCommand("LIST_AUTO",""));
};

//-Log button button
var handleShowLogClicked=function(event) {
	window.open("/Log.txt",'_blank');
};
//--Rec list handler
var handleRecListClicked= function(event) {
	executeServerCommand(new ServerCommand("LIST_REC",""));
	console.log("rec list clicked:"+event);
};
//--Filter list handler
var handleFilterClicked= function(event) {
	if (channelList.getSelected() == null){
		showStatus("No channel selected");
		return;
	}		

	var currentChannelName = channelList.getSelected().getTitle();
	if (isFilterOn){
		executeServerCommand(new ServerCommand("REQ_Programs",currentChannelName));
	}
	else { 
		if (programmList.getSelected() == null){
			showStatus("No program selected");
			return;
		}		
		var objectData = programmList.getSelected().jsonData;
		var searchData = [currentChannelName,objectData.title];		
		executeServerCommand(new ServerCommand("FILTER",searchData));
	}
};

//--Next day handler
var handleNextDayClicked= function(event) {
	var item = nearestDayRow();
	var next = item.dayIndex+1;
	var nextItem= document.getElementById("dayID"+next);
	if (nextItem!=null){
		item= nextItem;
	}
	item.scrollIntoView(true);
};

//--Previous day handler
var handlePreviousDayClicked= function(event) {
	var item = nearestDayRow();
	var next = item.dayIndex-1;
	if (next >=0){
		item= document.getElementById("dayID"+next);
	}
	if (item==null){
		return;
	}
	item.scrollIntoView(true);
};

//- search inpunt field handler
var handleKeypress=function(evt) {
	var inputField = (evt.target) ? evt.target : evt.srcElement;
	var searchString = inputField.value;
	var keytype = evt.keyIdentifier;
	//console.log("search for:"+searchString+" key="+keytype);
	var programEntry;
	if (keytype=="Down"){
		programEntry = programmList.findNext(searchString);
	} else if (keytype=="Up"){
		programEntry=programmList.findPrevious(searchString);
	} else {
		programEntry=programmList.find(searchString);
	}
	if (programEntry != null){
		programEntry.domObject.scrollIntoView(true);
	}
	
};
