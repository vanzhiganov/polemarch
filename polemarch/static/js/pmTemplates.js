
var pmTemplates = inheritance(pmItems)
 
pmTemplates.model.name = "templates"


// Поддерживаемые kind /api/v1/templates/supported-kinds/
pmTemplates.model.kind = "Task,Module"
pmTemplates.model.className = "pmTemplates"

pmTemplates.copyAndEdit = function(item_id)
{
    var def = new $.Deferred();
    var thisObj = this;
    return $.when(this.copyItem(item_id)).done(function(newItemId)
    {
        $.when(spajs.open({ menuId:thisObj.model.page_name + "/"+thisObj.model.items[item_id].kind+"/"+newItemId})).done(function(){
            $.notify("Item was duplicate", "success");
            def.resolve()
        }).fail(function(e){
            $.notify("Error in duplicate item", "error");
            polemarch.showErrors(e)
            def.reject()
        })
    }).fail(function(){
        def.reject()
    })

    return def.promise();
}
    
    
// Содержит соответсвия разных kind к объектами с ними работающими.
pmTemplates.model.kindObjects = {}

pmTemplates.showSearchResults = function(holder, menuInfo, data)
{
    var thisObj = this;
    var query = decodeURIComponent(data.reg[1])

    var search = this.searchStringToObject(query)
    search['kind'] = thisObj.model.kind
    return $.when(this.sendSearchQuery(search)).done(function()
    {
        $(holder).insertTpl(spajs.just.render(thisObj.model.name+'_list', {query:query}))
    }).fail(function()
    {
        $.notify("", "error");
    })
}
 
pmTemplates.exportToFile = function(item_ids)
{
    var def = new $.Deferred();
    if(!item_ids)
    {
        $.notify("No data for export", "error");
        def.reject();
        return def.promise();
    }

    var data = {
        "filter": {
            "id__in": item_ids,
        },
    }

    var thisObj = this;
    spajs.ajax.Call({
        url: "/api/v1/"+this.model.name+"/filter/?detail=1",
        type: "POST",
        contentType:'application/json',
        data:JSON.stringify(data),
                success: function(data)
        {
            var filedata = []
            for(var i in data.results)
            {
                var val = data.results[i]
                delete val['id'];
                delete val['url'];

                filedata.push({ 
                    item: thisObj.model.page_name,
                    data: val
                })
            }
            
            var fileInfo = {
                data:filedata,
                count:filedata.length,
                version:"1"
            }
            
            var textFileAsBlob = new Blob([JSON.stringify(fileInfo)], {
              type: 'text/plain'
            });

            var newLink = document.createElement('a')
            newLink.href = window.URL.createObjectURL(textFileAsBlob)
            newLink.download = thisObj.model.name+"-"+Date()+".json"
            newLink.target = "_blanl"
            var event = new MouseEvent("click");
            newLink.dispatchEvent(event);


            def.resolve();
        },
        error:function(e)
        {
            console.warn(e)
            polemarch.showErrors(e)
            def.reject();
        }
    });

    return def.promise();
}

pmTemplates.importFromFile = function(files_event)
{  
    var def = new $.Deferred(); 
    this.model.files = files_event
    
    for(var i=0; i<files_event.target.files.length; i++)
    {
        var reader = new FileReader();
        reader.onload = (function(index_in_files_array)
        {
            return function(e)
            {
                console.log(e)
                var bulkdata = []
                var filedata = JSON.parse(e.target.result)
                
                if(filedata.version/1 > 1)
                {
                    polemarch.showErrors("Error file version is "+filedata.version)
                    def.reject();
                    return;
                }
                
                for(var i in filedata.data)
                {
                    var val = filedata.data[i]
                    val.type = "add"
                    bulkdata.push(val)
                }
                console.log(bulkdata)
                 
                spajs.ajax.Call({
                    url: "/api/v1/_bulk/",
                    type: "POST",
                    contentType:'application/json',
                    data:JSON.stringify(bulkdata),
                                        success: function(data)
                    { 
                        def.resolve();
                        spajs.openURL(window.location.href);
                    },
                    error:function(e)
                    {
                        console.warn(e)
                        polemarch.showErrors(e)
                        def.reject();
                    }
                });
            };
        })(i);
        reader.readAsText(files_event.target.files[i]); 
        
        // Нет поддержки загрузки более одного файла за раз.
        break;
    }
    
    return def.promise();
}