# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2016-2018 TechSpell srl (<http://techspell.eu>). All Rights Reserved
#    
#    Created on : 2016-03-01
#    Author : Fabio Colognesi
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import socket
import datetime
from xml.etree.ElementTree import fromstring

from openerp.osv import fields, orm
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import openerp.tools.config as tools_config

from .common import getIDs, getCleanList, isAdministrator, packDictionary, unpackDictionary, \
                    getCleanBytesDictionary, getCleanBytesList, getListIDs, streamPDF
                    

class plm_config_settings(orm.Model):
    _name = 'plm.config.settings'
    _description = "PLM Settings"
    _table = "plm_config_settings"
    _order = 'plm_service_id'
     
    _columns = {
        'plm_service_id': fields.char('Service ID', size=128,
                                      help="Insert the Service ID and register your PLM module. Ask it to TechSpell."),
        'activated_id': fields.char('Activated PLM client', size=128, readonly="True", help="Listed activated Client."),
        'active_editor': fields.char('Client Editor Name', size=128, readonly="True", help="Used Editor Name"),
        'active_node': fields.char('OS machine name', size=128, readonly="True", help="Editor Machine Name"),
        'expire_date': fields.datetime('Expiration Date', readonly="True", help="Expiration Date"),
        'active_os': fields.char('OS name', size=128, readonly="True", help="Editor OS Name"),
        'active_os_rel': fields.char('OS release', size=128, readonly="True", help="Editor OS Release"),
        'active_os_ver': fields.char('OS version', size=128, readonly="True", help="Editor OS Version"),
        'active_os_arch': fields.char('OS architecture', size=128, readonly="True", help="Editor OS Architecture"),
        'node_id': fields.char('Registered PLM client', size=128, readonly="True", help="Listed Registered Client."),
        'domain_id': fields.char('Domain Name', size=128, readonly="True", help="Listed domain name."),
        'active_kind': fields.char('Kind of license', size=128, readonly="True",
                                   help="Kind of license code ('node-locked' = Local individual license, 'domain-assigned' = Domain level license)."),
        'opt_editbom': fields.boolean("Edit BoM not in 'draft'", help="Allows to edit BoM if product is not in 'Draft' status. Default = False."),
        'opt_editreleasedbom': fields.boolean("Edit BoM in 'released'", help="Allows to edit BoM if product is in 'Released' status. Default = False."),
        'opt_duplicatedrowsinbom': fields.boolean("Allow rows duplicated in BoM", help="Allows to duplicate product rows editing a BoM. Default = True."),
        'opt_autonumbersinbom': fields.boolean("Allow to assign automatic positions in BoM", help="Allows to assign automatically item positions editing a BoM. Default = False."),
        'opt_autostepinbom': fields.integer("Assign step to automatic positions in BoM", help="Allows to use this step assigning item positions, editing a BoM. Default = 5."),
        'opt_autotypeinbom': fields.boolean("Assign automatically types in BoM", help="Allows to use the same type of BoM in all new items, editing a BoM. Default = True."),
    }
    _defaults = {
        'plm_service_id': lambda *a: False,
        'activated_id': lambda *a: False,
        'opt_duplicatedrowsinbom': lambda *a: True,
        'opt_autostepinbom': lambda *a: 5,
        'opt_autotypeinbom': lambda *a: True,
    }

    def GetServiceIds(self, cr, uid, oids=None, default=None, context=None):
        """
            Get all Service Ids registered.
        """
        ids = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        partIds = self.search(cr, uid, [('activated_id', '=', False)], context=context)
        for part in self.browse(cr, uid, partIds, context=context):
            ids.append(part.plm_service_id)
        return getCleanList(ids)

    def RegisterActiveId(self, cr, uid, vals=[], default=None, context=None):
        """
            Registers Service Id & Activation infos.  [serviceID, activation, activeEditor, expirationDate, (system, node, release, version, machine, processor), nodeId, domainName ]
        """
        default = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        serviceID, activation, activeEditor, expirationDate, (
        system, node, release, version, machine, processor), nodeId, domainName, kind = vals
        if activation:
            default.update({
                'plm_service_id': serviceID,
                'activated_id': activation,
                'active_editor': activeEditor,
                'domain_id': domainName,
                'expire_date': datetime.datetime.strptime(expirationDate, "%d/%m/%Y"),
                'active_os': system,
                'active_node': node,
                'active_os_rel': release,
                'active_os_ver': version,
                'active_os_arch': machine,
                'node_id': nodeId,
                'active_kind': kind,
            })

            for partId in self.search(cr, uid, [('plm_service_id', '=', serviceID), ('activated_id', '=', activation),
                                            ('active_editor', '=', activeEditor)], context=context):
                self.write(cr, uid, [partId], default, context=context)
                return False

            self.create(cr, uid, default, context=context)
        return False

    def GetActivationId(self, cr, uid, vals=[], default=None, context=None):
        """
            Gets activation codes as registered.
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        results = []
        found = []
        today = datetime.datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        nodeId, domainID, activeEditor, _ = vals

        if len(domainID) > 0:
            partIds = self.search(cr, uid, [('domain_id', '=', domainID), ('expire_date', '>', today)], context=context)
            for partId in self.browse(cr, uid, partIds, context=context):
                results.append((partId.plm_service_id, partId.activated_id, partId.domain_id))
                found.append(partId.id)

        partIds = self.search(cr, uid, [('node_id', '=', nodeId), ('expire_date', '>', today)], context=context)
        for partId in self.browse(cr, uid, partIds, context=context):
            if partId.id not in found:
                results.append((partId.plm_service_id, partId.activated_id, partId.domain_id))

        return results

    def getoptionfields(self, cr, uid, context=None):
        ret=[]
        for keyName in self._all_columns.keys():
            if keyName.startswith('opt_'):
                ret.append(keyName)
        return ret

    def GetOptions(self, cr, uid, request=None, default=None, context=None):
        """
            Gets activation codes as registered.
        """
        results = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        optionNames=self.getoptionfields(cr,uid,context)
        optIds = self.search(cr, uid, [('activated_id', '=', False), ('plm_service_id', '!=', False)], context=context)
        if optIds:
            for optId in self.browse(cr, uid, getListIDs(optIds), context=context):
                for optionName in optionNames:
                    results[optionName]=optId[optionName]
        return results

###################################################################
#                        C R U D  Methods                         #
###################################################################

    def Create(self, cr, uid, request=[], default=None, context=None):
        """
            Creates items on DB.
        """
        results=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        objectName, values=request
        userType=self.pool[objectName] if objectName in self.pool.models else None
        
        if userType!=None:
            for valueSet in values:
                results.append(userType.create(cr, uid, valueSet, context=context))          
        return results

    def Read(self, cr, uid, request=[], default=None, context=None):
        """
            Read given fields on items on DB.
        """
        results=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        objectName, criteria, fields = request        
        if len(fields)<1:
            return results
        
        userType=self.pool[objectName] if objectName in self.pool.models else None
        
        if userType!=False and userType!=None:
            ids=userType.search(cr, uid, criteria, context=context)
            if ids:
                tmpData=userType.export_data(cr, uid, ids, fields, context=context)
                if 'datas' in tmpData:
                    results=tmpData['datas']
        return results

    def Update(self, cr, uid, request=[], default=None, context=None):
        """
            Updates items on DB.
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        objectName, criteria, values = request        
        if len(values)<1:
            return False        
        userType=self.pool[objectName] if objectName in self.pool.models else None
        
        if userType!=None:
            ids=userType.search(cr, uid, criteria, context=context)
            for oid in ids:
                userType.write(cr, uid, oid, values, context=context)
        return False

    def Delete(self, cr, uid, request=[], default=None, context=None):
        """
            Remove items from DB.
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        objectName, criteria, values = request        
        if len(values)<1:
            return False        
        userType=self.pool[objectName] if objectName in self.pool.models else None
        
        if userType!=None:
            ids=userType.search(cr, uid, criteria, context=context)
            if ids:
                userType.unlink(cr, uid, ids, values, context=context)
        return False
    
###################################################################
#                        C R U D  Methods                         #
###################################################################

    def GetDocumentByName(self, cr, uid, request=None, default=None, context=None):
        """
            Gets content of document named <docName> (latest revision).          
        """
        docID, nameFile, contentFile, writable, lastupdate=[False, "","", False, False]
        context = context or self.pool['res.users'].context_get(cr, uid)
        docName=request
        if docName:
            docType=self.pool["plm.document"]
            docIds = docType.search(cr, uid, [('name','=',docName),('type','=','binary')], order='revisionid', context=context)
            if docIds:
                docIds.sort()   # Ids are not surely ordered, but revision are always in creation order.
                oid=docIds[len(docIds)-1]
                docID, nameFile, contentFile, writable, lastupdate = docType._data_get_files(cr, uid, [oid])[0]
        return docID, nameFile, contentFile, writable, lastupdate

    def GetCustomProcedure(self, cr, uid, request=None, default=None, context=None):
        """
            Gets document named 'CustomProcedure'           
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        _, _, contentFile, _, _ = self.GetDocumentByName(cr, uid, 'CustomProcedure', default, context=context)
        return contentFile

    def GetAttachedPDF(self, cr, uid, request=[], default=None, context=None):
        """
            Gets attached PDF.          
        """
        ids=request
        if ids:
            context = context or self.pool['res.users'].context_get(cr, uid)
            from ..reports.report.document_report import create_report
            ret, _ =create_report(cr, uid, ids, datas=None, context=None)         
        return streamPDF(ret)

    def GetDataConnection(self, cr, uid, request=None, default=None, context=None):
        """
            Gets data for external connection to DB.
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        tableViews,columnViews=self.getColumnViews(cr, uid)
        criteria=self.getCriteriaNames(cr, uid)
        user = tools_config.get('plm_db_user', False) or tools_config.get('db_user', False) or ''
        pwd = tools_config.get('plm_db_password', False) or tools_config.get('db_password', False) or ''
        host = tools_config.get('plm_db_host', False) or tools_config.get('db_host', False) or socket.gethostname()
        port = tools_config.get('plm_db_port', False) or tools_config.get('db_port', False) or 5432
        dbname = cr.dbname
        if (host=="127.0.0.1") or (host=="localhost") or (host==""):
            host=socket.gethostname()
        return ([user,pwd,host,port,dbname],tableViews,columnViews,criteria)

    def GetServerTime(self, cr, uid, request=None, default=None, context=None):
        """
            calculate the server db time 
        """
        return datetime.datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT), DEFAULT_SERVER_DATETIME_FORMAT

    def GetUserSign(self, cr, uid, ids=None, default=None, context=None):
        """
            Gets the user login, name and signature
        """
        ret=["","",""]
        context = context or self.pool['res.users'].context_get(cr, uid)
        for uiUser in self.pool['res.users'].browse(cr, uid, [uid], context=context):
            ret=[uiUser.login, uiUser.name, uiUser.signature]
            break
        return ret

    def GetDataModel(self, cr, uid, request=None, default=None, context=None):
        """
            Get properties as assigned.
        """
        return packDictionary(self.getDataModel(cr, uid, request, default, context=context))

    def GetFieldsModel(self, cr, uid, objectName="", context=None):
        ret=[]
        if objectName:
            ret = self.pool[objectName]._all_columns.keys()
        return ret

    def getDataModel(self, cr, uid, request=None, default=None, context=None):
        """
            Get properties as assigned.
        """
        retValues={}
        if request:
            objectName=request
            context = context or self.pool['res.users'].context_get(cr, uid)
            objType=self.pool['ir.model']
            ids=objType.search(cr, uid, [('model','=',objectName)], context=context)
            for model in objType.browse(cr, uid, ids, context=context):
                for field in model.field_id:
                    retValues.update({field.name:[
                                                   ('description', _(field.field_description)),
                                                   ('type', field.ttype),
                                                   ('relation', field.relation),
                                                   ('required', field.required)
                                                ] })
        return retValues

    def checkViewExistence(self, cr, uid, criteria=None, context=None):
        ret=None
        if criteria:
            viewObjType=self.pool['ir.ui.view']
            viewIDs=viewObjType.search(cr, uid, criteria, context=context)
            if viewIDs:
                ret=viewIDs[0]
        return ret

    def getViewArchitecture(self, cr, uid, criteria=None, context=None):
        ret=None
        if criteria:
            context = context or self.pool['res.users'].context_get(cr, uid)
            viewID=self.checkViewExistence(cr, uid, criteria, context=context)
            if viewID:
                readView=self.pool['ir.ui.view'].get_inheriting_views_arch(cr, uid, viewID, "arch", context=context)
                if 'arch' in readView:
                    ret=[[readView['arch'],],]
                else:
                    ret=self.Read(cr, uid, ['ir.ui.view', criteria, ["arch"]], context=context) 
            else:
                ret=self.Read(cr, uid, ['ir.ui.view', criteria, ["arch"]], context=context) 
        return ret

    def GetFormView(self, cr, uid, request=None, default=None, context=None):
        criteria=None
        viewName=request
        if viewName:
            criteria=[('name','=','{}.inherit'.format(viewName)),('type','=','form')]
            if not self.checkViewExistence(cr, uid, criteria, context=context):
                criteria=[('name','=',viewName),('type','=','form')]
        return self.getViewArchitecture(cr, uid, criteria, context=context)

    def GetTreeView(self, cr, uid, request=None, default=None, context=None):
        criteria=None
        viewName=request
        if viewName:
            criteria=[('name','=','{}.inherit'.format(viewName)),('type','=','tree')]
            if not self.checkViewExistence(cr, uid, criteria, context):
                criteria=[('name','=',viewName),('type','=','tree')]
        return self.getViewArchitecture(cr, uid, criteria, context=context)

    def GetFormViewByModel(self, cr, uid, request=None, default=None, context=None):
        criteria=None
        modelName=request
        if modelName:
            criteria=[('model','=',modelName),('type','=','form')]
        return self.getViewArchitecture(cr, uid, criteria, context=context)
        
    def GetTreeViewByModel(self, cr, uid, request=None, default=None, context=None):
        criteria=None
        modelName=request
        if modelName:
            criteria=[('model','=',modelName),('type','=','tree')]
        return self.getViewArchitecture(cr, uid, criteria, context=context)

    def GetProperties(self, cr, uid, request=None, default=None, context=None):
        """
            Get properties as assigned.
        """
        objectName, editor=request
        context = context or self.pool['res.users'].context_get(cr, uid)
        userType=self.pool[objectName] if objectName in self.pool.models else None
        return packDictionary(self.getEditProperties(cr, uid, userType, editor))

    def GetValues(self, cr, uid, request=None, default=None, context=None):
        """
            Get property values as requested.
        """
        objectName, editor, codeProperties, propNames=unpackDictionary(request)
        codeProperties=getCleanBytesDictionary(codeProperties)
        propNames=getCleanBytesList(propNames)
        context = context or self.pool['res.users'].context_get(cr, uid)
        userType=self.pool[objectName] if objectName in self.pool.models else None
        return packDictionary(self.getValueProperties(cr, uid, userType, editor, codeProperties, propNames))

    def IsAdministrator(self, cr, uid, request=None, default=None, context=None):
        """
            Checks if this user is in PLM Administrator group
        """
        return isAdministrator(self, cr, uid, context=context)
    
    def GetEditorProperties(self, cr, uid, request=["", ""], context=None):
        """
            Get Properties (as dictionary) to be managed in editor.
        """
        editor_properties={}
        objectName, editor=request
        if objectName:
            context = context or self.pool['res.users'].context_get(cr, uid)
            userType=self.pool[objectName] if objectName in self.pool.models else None
            if userType:        
                editor_properties = userType.editorProperties(cr, uid, editor)      # In Extend Client
        return packDictionary(editor_properties)

    def getEditProperties(self, cr, uid, userType=None, editor="", context=None):
        """
            Get Properties (as dictionary) to be managed in editor.
        """
        properties={}
        if userType!=None:
            editor_properties = userType.editorProperties(cr, uid, editor)      # In Extend Client
            base_properties = userType.defineProperties(cr, uid)                # In Extend Client
            if base_properties:
                typeFields=userType._all_columns
                propList=list(set(editor_properties.keys()).intersection(set(base_properties.keys())))
                keyList=list(set(typeFields.keys()).intersection(set(base_properties.keys())))
                for keyName in keyList:
                    tmp_props=dict(zip(base_properties[keyName].keys(), base_properties[keyName].values()))
                    tmp_props['name']=typeFields[keyName].name
                    tmp_props['label']=_(typeFields[keyName].column.string)
                    fieldType=typeFields[keyName].column._type

                    tmp_props['tooltip']=""
                    if typeFields[keyName].column.help:
                        tmp_props['tooltip']=_(typeFields[keyName].column.help)
    
                    if (fieldType in["char","string","text"]):
                        tmp_props['type']="string"
                        tmp_props['value']=""
                        tmp_props['size']=typeFields[keyName].column.size if not typeFields[keyName].column.size==None else 255
                    elif (fieldType in["int","integer"]):
                        tmp_props['type']="int"
                        tmp_props['value']=0
                    elif (fieldType in["bool","boolean"]):
                        tmp_props['type']="bool"
                        tmp_props['value']=False
                    elif (fieldType in["date","datetime"]):
                        tmp_props['type']="datetime"
                        tmp_props['value']=False
                    elif (fieldType in["float","double","decimal"]):
                        tmp_props['type']="float"
                        tmp_props['value']=0.0
                        if typeFields[keyName].column.digits:
                            tmp_props['decimal']=typeFields[keyName].column.digits[1]
                    elif (fieldType=="selection") and typeFields[keyName].column.selection:    
                        tmp_props['type']="string"
                        tmp_props['value']=""
                        tmp_props['selection']=dict(typeFields[keyName].column.selection)
                    elif (fieldType in ["many2one","one2many","many2many"]) and typeFields[keyName].column._obj:    
                        criteria=[('id','!=', False),] 
                        tmp_props['value']=False
                        entityName=typeFields[keyName].column._obj   
                        columns=self.getBaseObject(cr, uid, entityName, context=context)
                        values=[]
                        dictvalues={}
                        if not tmp_props.get('viewonly', False):
                            values,dictvalues=self.getDataObject(cr, uid, entityName, criteria, columns.keys(), context=context)
                        tmp_props['type']='object'
                        tmp_props['object']={
                                             "entity": entityName,
                                             "columns": columns,
                                             "columnnames": columns.keys(),
                                             "values": values,
                                             "dictvalues":dictvalues,
                                            }
 
                    if typeFields[keyName].column.required:
                        tmp_props['mandatory']=True         # If required forces external assignment.
    
                    if keyName in propList:
                        tmp_props['property']=editor_properties[keyName]
 
                    if ('default' in tmp_props) and not ('value' in tmp_props):
                        tmp_props['value']=tmp_props['default']

                    if ('code' in tmp_props) and isinstance(tmp_props['code'], dict):
                        entityName=tmp_props['code'].get('entity', "")
                        if entityName:
                            columns=self.getBaseObject(cr, uid, entityName, context=context)
                            values=[]
                            dictvalues={}
                            if columns:
                                criteria=[('id','!=', False),] 
                                values,dictvalues=self.getDataObject(cr, uid, entityName, criteria, columns.keys(), context=context)
                            tmp_props['code'].update({
                                                "columns": columns,
                                                "columnnames": columns.keys(),
                                                "values": values,
                                                "dictvalues":dictvalues,
                                                })
                      
                    properties[keyName]=tmp_props
        return properties

    def getCodedObject(self, cr, uid, userType=None, codeProperties={}, context=None):
        """
            Gets object responding to the first satisfied criteria, expressed by
            codeProperties dictionary ('name' will be evaluated first , anyway).
        """
        objectID=None
        if userType!=None and codeProperties:
            context = context or self.pool['res.users'].context_get(cr, uid)
            listNames=codeProperties.keys()
            if 'name' in listNames:         # This guitar riff to ensure 'name' is evaluated as first one.
                listNames.remove('name')
                listNames[:0]=['name'] 
            for keyName in listNames:
                value=codeProperties[keyName].get('value', None)
                if value:
                    criteria=[(keyName, '=', value)]
                    objIDs = userType.search(cr, uid, criteria, order='id', context=context)
                    if len(objIDs) > 0:
                        objIDs.sort()
                        tmpobjectIDs=userType.browse(cr, uid, objIDs, context=context)
                        if tmpobjectIDs:
                            objectID=tmpobjectIDs[len(objIDs)-1]
                            break
        return objectID
    
    def getBaseObject(self, cr, uid, userType=False, context=None):
        ret={}
        productXmls=self.GetTreeViewByModel(cr, uid, userType, context=context)
        if productXmls:
            dataModel=self.getDataModel(cr, uid, userType, context=context)
            productXml=fromstring(productXmls[0][0])
            for item in productXml.iter("field"):
                if item.attrib['name'] in dataModel:
                    modelData=dict(dataModel[item.attrib['name']])
                    ret.update( { item.attrib['name']: _(modelData['description']) } )
        return ret

    def getDataObject(self, cr, uid, userType="", criteria=[], columns=[], context=None):
        values,dictvalues=[[],{}]
        if userType and columns:
            objectType=self.pool[userType]
            typeFields=objectType._all_columns
            context = context or self.pool['res.users'].context_get(cr, uid)
            allIDs = objectType.search(cr, uid, criteria, order='id', context=context)
            for objectID in objectType.browse(cr, uid, allIDs, context=context):
                dict_data={}
                row_data=[objectID.id]
                for columnName in columns:
                    if typeFields[columnName].column._type in ["many2one","one2many","many2many"]:
                        dict_data.update({ columnName: objectID[columnName].id })
                        row_data.append(objectID[columnName].name)
#                         else:
#                             row_data.append(objectID[columnName].id)
                    else:
                        dict_data.update({ columnName: objectID[columnName] })
                        row_data.append(objectID[columnName])
                values.append(row_data)
                dictvalues.update({ "{}".format(objectID.id): dict_data })
        return values,dictvalues

    
    def getValueProperties(self, cr, uid, userType=None, editor="", codeProperties={}, propNames=[], context=None):
        """
            Get Properties (as dictionary) to be managed in editor.
        """
        properties={}
        if userType!=None and codeProperties:
            context = context or self.pool['res.users'].context_get(cr, uid)
            objectID=self.getCodedObject(cr, uid, userType, codeProperties)
            if objectID:
                typeFields=userType._all_columns
                base_properties = self.getEditProperties(cr, uid, userType, editor, context=context)               # In Extend Client
                for keyName in base_properties.keys():
                    tmp_props=dict(zip(base_properties[keyName].keys(), base_properties[keyName].values()))
                    tmp_props['value']=objectID[keyName]

                    if (typeFields[keyName].column._type in ["many2one","one2many","many2many"]) and typeFields[keyName].column._obj:
                        entityName=typeFields[keyName].column._obj  
                        rows=[]
                        columns=self.getBaseObject(cr,uid, entityName, context=context)
                        related=getIDs(objectID[keyName]) if objectID[keyName] else []
                        if related:
                            criteria=[('id','in', related),]
                            rows,_=self.getDataObject(cr,uid, entityName, criteria, columns.keys(), context=context)

                        tmp_props['object'].update({
                                             "rows": rows,
                                            })
                        tmp_props['value']=related

                    properties[keyName]=tmp_props

                properties['_serverupdate']={
                                         "_lastupdate": objectID.write_date or objectID.create_date,
                                         "_showdate": DEFAULT_SERVER_DATETIME_FORMAT,
                                        }
        return properties

    def GetServiceNodes(self, cr, uid, oids=[], default=None, context=None):
        """
            Get all Service Ids registered.
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        message=_("Insert your Activation Code as provided by TechSpell.")
        ids=self.GetServiceIds(cr, uid, oids, default=default, context=context)
        return ids, message

    def GetMethodNames(self, cr, uid, request=None, default=None, context=None):
        """
            Get Client method names and translated labels.
        """
        results={
            'About':            _('About'),
            'Login':            _('Execute Login'),
            'CheckIn':          _('Check-In current document'),
            'CheckInRecursive': _('Recursive Check-In from current document'),
            'CheckOut':         _('Check-Out current document'),
            'Save':             _('Upload current document'),
            'EditParts':        _('Edit Part Data'),
            'AssignDocName':    _('Assign Document Data'),
            'DocumentOpen':     _('Open a Document'),
            'DocumentImport':   _('Import a Document'),
            'OpenRelatedDocs':  _('Open Documents related to current one'),
            'ComponentOpen':    _('Open a Document by Component'),
            'ComponentImport':  _('Import a Document by Component'),
            'Clone':            _('Clone Part and Document'),
            'NewRevision':      _('New Revision'),
            'NewMinorRevision': _('New Minor Revision'),
            'NewDocRevision':   _('New Document Revision'),
            'EditDocComment':   _('Edit Document Comment'),
            'PurgePWS':         _('Purge Checked-In files from PWS'),
            'Options':          _('Options and User Settings'),
            }

        return results
 
    def GetClientMessages(self, cr, uid, request=None, default=None, context=None):
        """
            Get Client translated messages.
        """
        results={
            'About01':              _('About'),
            'Login01':              _('Execute Login'),
            'CheckIn01':            _('Check-In current document'),
            'CheckInR01':           _('Recursive Check-In from current document'),
            'CheckOut01':           _('Check-Out current document'),
            'Save01':               _('Upload current document'),
            'EditParts01':          _('Edit Part Data'),
            'AssignDocName01':      _('Assign Document Data'),
            'DocOpen01':            _('Open a Document'),
            'DocImport01':          _('Import a Document'),
            'OpenReldDocs01':       _('Open Documents related to current one'),
            'CompOpen01':           _('Open a Document by Component'),
            'CompImport01':         _('Import a Document by Component'),
            'Clone01':              _('Clone Part and Document'),
            'NewRevision01':        _('New Revision'),
            'NewMinorRevision01':   _('New Minor Revision'),
            'NewDocRevi01':         _('New Document Revision'),
            'EditDocComm01':        _('Edit Document Comment'),
            'PurgePWS01':           _('Purge Checked-In files from PWS'),
            'Options01':            _('Options and User Settings'),
            }

        return results
    
    def getCriteriaNames(self, cr, uid, context=None):
        """
            Gets criteria names and their translated labels.
        """
        return  {
                    "like": _("Like"),
                    "not like": _("Not Like"),
                    "equal": _("Equal"),
                    "not equal": _("Not Equal"),
                    "contains": _("Contains"),
                    "does not contain": _("Doesn't Contain"),
                    "greater": _("Greater"),
                    "greater equal": _("Greater Equal"),
                    "smaller": _("Smaller"),
                    "smaller equal": _("Smaller Equal"),
                    "is null": _("Is Null"),
                    "is not null": _("Is Not Null"),
                }

    def getColumnViews(self, cr, uid, context=None):
        """
            Gets tables and columns (label and visibility) for materialized views.
        """
        tables=[['ext_document','document'],['ext_component','component'],['ext_docbom','docbom'],
                    ['ext_bom','mrpbom'],['ext_checkout','checkout'],['ext_linkdoc','linkdoc']]
        columns = {
                'document':{
                          'id' : {'label':_('ID'), 'visible':True, 'pos':1},
                          'name' : {'label':_('Document Name'), 'visible':True, 'pos':2},
                          'revisionid' : {'label':_('Revision'), 'visible':True, 'pos':3},
                          'minorrevision' : {'label':_('Minor Revision'), 'visible':True, 'pos':4},
                          'state' :  {'label':_('Status'), 'visible':True, 'pos':5},
                          'created' :  {'label':_('Creator'), 'visible':True, 'pos':6},
                          'create_date' :  {'label':_('Created'), 'visible':True, 'pos':7},
                          'changed' :  {'label':_('Modified by'), 'visible':True, 'pos':8},
                          'write_date' :  {'label':_('Changed'), 'visible':True, 'pos':9},
                          'checkedout' :  {'label':_('Checked-Out by'), 'visible':True, 'pos':10},
                          'filename' :  {'label':_('File Name'), 'visible':True, 'pos':11},
                          'preview' :  {'label':_('Preview'), 'visible':False, 'pos':12},
                          },
                
                'component':{
                          'id' : {'label':_('ID'), 'visible':True, 'pos':1},
                          'tmpl_id' : {'label':_('Template ID'), 'visible':False, 'pos':2},
                          'name' : {'label':_('Product Name'), 'visible':True, 'pos':3},
                          'engineering_code' : {'label':_('Engineering Code'), 'visible':True, 'pos':4},
                          'engineering_revision' : {'label':_('Revision'), 'visible':True, 'pos':5},
                          'state' :  {'label':_('Status'), 'visible':True, 'pos':6},
                          'description' : {'label':_('Description'), 'visible':True, 'pos':7},
                          'created' :  {'label':_('Creator'), 'visible':True, 'pos':8},
                          'create_date' :  {'label':_('Created'), 'visible':True, 'pos':9},
                          'changed' :  {'label':_('Modified by'), 'visible':True, 'pos':10},
                          'write_date' :  {'label':_('Modified'), 'visible':True, 'pos':11},
                          },

                'mrpbom':{
                            'id' : {'label':_('Father ID'), 'visible':True, 'pos':1},
                            'father id' : {'label':_('Father ID'), 'visible':False, 'pos':2},
                            'child_id' : {'label':_('Child ID'), 'visible':False, 'pos':3},
                            'father' : {'label':_('Assembly Name'), 'visible':True, 'pos':4},
                            'father_code' : {'label':_('Engineering Code'), 'visible':True, 'pos':5},
                            'father_rv' : {'label':_('Revision'), 'visible':True, 'pos':6},
                            'father_desc' : {'label':_('Description'), 'visible':True, 'pos':7},
                            'child' : {'label':_('Product Name'), 'visible':True, 'pos':8},
                            'child_code' : {'label':_('Engineering Code'), 'visible':True, 'pos':9},
                            'child_rv' : {'label':_('Revision'), 'visible':True, 'pos':10},
                            'child_desc' : {'label':_('Description'), 'visible':True, 'pos':11},
                            'created' :  {'label':_('Creator'), 'visible':True, 'pos':12},
                            'create_date' :  {'label':_('Created'), 'visible':True, 'pos':13},
                            'changed' :  {'label':_('Modified by'), 'visible':True, 'pos':14},
                            'write_date' :  {'label':_('Modified'), 'visible':True, 'pos':15},
                            },
                
                'docbom':{
                            'id' : {'label':_('Father ID'), 'visible':True, 'pos':1},
                            'father_id' : {'label':_('Father ID'), 'visible':False, 'pos':2},
                            'child_id' : {'label':_('Child ID'), 'visible':False, 'pos':3},
                            'father' : {'label':_('Father Document'), 'visible':True, 'pos':4},
                            'father_rv' : {'label':_('Revision'), 'visible':True, 'pos':5},
                            'father_min' : {'label':_('Minor Revision'), 'visible':True, 'pos':6},
                            'father_file' : {'label':_('Father File'), 'visible':True, 'pos':7},
                            'kind' : {'label':_('Kind Relation'), 'visible':True, 'pos':8},
                            'child' : {'label':_('Child Document'), 'visible':False, 'pos':9},
                            'child_rv' : {'label':_('Revision'), 'visible':True, 'pos':10},
                            'child_min' : {'label':_('Minor Revision'), 'visible':True, 'pos':11},
                            'child_file' : {'label':_('Child File'), 'visible':True, 'pos':12},
                            'created' :  {'label':_('Creator'), 'visible':True, 'pos':13},
                            'create_date' :  {'label':_('Created'), 'visible':False, 'pos':14},
                           },

                'linkdoc':{
                            'id' : {'label':_('Father ID'), 'visible':True, 'pos':1},
                            'component_id' : {'label':_('Component ID'), 'visible':False, 'pos':2},
                            'document_id' : {'label':_('Document ID'), 'visible':False, 'pos':3},
                            'component' : {'label':_('Component'), 'visible':True, 'pos':4},                             
                            'code' : {'label':_('Component Code'), 'visible':True, 'pos':5},
                            'component_rv' : {'label':_('Component Revision'), 'visible':True, 'pos':6},
                            'document' : {'label':_('Document'), 'visible':True, 'pos':7},
                            'document_rv' : {'label':_('Document Revision'), 'visible':True, 'pos':8},
                            'document_min' : {'label':_('Document Minor Revision'), 'visible':True, 'pos':9},
                            'create_date' :  {'label':_('Created'), 'visible':False, 'pos':10},
                           },

                 'checkout':{
                            'id' : {'label':_('Internal ID'), 'visible':False, 'pos':1},
                            'document_id' : {'label':_('ID'), 'visible':True, 'pos':2},
                            'create_date' :  {'label':_('Created'), 'visible':False, 'pos':3},
                            'document' : {'label':_('Document'), 'visible':True, 'pos':4},
                            'document_rv' : {'label':_('Document Revision'), 'visible':True, 'pos':5},
                            'document_min' : {'label':_('Document Minor Revision'), 'visible':True, 'pos':6},
                            'user' : {'label':_('Checked-Out by'), 'visible':True, 'pos':7},                             
                            'host' : {'label':_('Hostname'), 'visible':True, 'pos':8},
                            'path' : {'label':_('Directory'), 'visible':True, 'pos':9},
                            'filename' : {'label':_('FileName'), 'visible':True, 'pos':10},
                           },
                }
                   
        return tables, columns

    def Refresh(self, cr, uid, request=None, context=None):
        """
            Refreshes Materialized Views.
        """
#         logging.warning("Refreshing Materialized Views: Start.")
#         cr.execute("REFRESH MATERIALIZED VIEW ext_component")
#         cr.execute("REFRESH MATERIALIZED VIEW ext_document")
#         logging.warning("Refreshing Materialized Views: End.")
        return False

    def init(self, cr):
        """
            Creates views for external Clients.
        """
        cr.execute("DROP VIEW IF EXISTS ext_checkout CASCADE")
        cr.execute("DROP VIEW IF EXISTS ext_bom CASCADE")
        cr.execute("DROP VIEW IF EXISTS ext_docbom CASCADE")
        cr.execute("DROP VIEW IF EXISTS ext_linkdoc CASCADE")
        cr.execute("DROP VIEW IF EXISTS ext_component CASCADE")
        cr.execute("DROP VIEW IF EXISTS ext_document CASCADE")
#         cr.execute("DROP MATERIALIZED VIEW IF EXISTS ext_component CASCADE")
#         cr.execute("DROP MATERIALIZED VIEW IF EXISTS ext_document CASCADE")
        #TODO: To be evaluated if creation can be parametric so to allow view configuration. 
 
        cr.execute("CREATE INDEX IF NOT EXISTS idx_documentid_plm_checkout ON plm_checkout (documentid)")
        cr.execute("CREATE INDEX IF NOT EXISTS idx_userid_plm_checkout ON plm_checkout (userid)")
        cr.execute("CREATE INDEX IF NOT EXISTS idx_create_uid_plm_document ON plm_document (create_uid)")
        cr.execute("CREATE INDEX IF NOT EXISTS idx_write_uid_plm_document ON plm_document (write_uid)")
        cr.execute(
            """
            CREATE OR REPLACE VIEW ext_document AS (
                SELECT a.id, a.name, a.revisionid, a.minorrevision, d.login as created, a.state, a.create_date, d.login as changed, a.write_date, c.login as checkedout, a.datas_fname as filename, a.preview 
                    FROM plm_document a LEFT JOIN plm_checkout b on a.id=b.documentid LEFT JOIN res_users c on c.id=b.userid, res_users d, res_users e
                    WHERE
                         a.id IN
                        (
                            SELECT id FROM plm_document
                        )
                        AND d.id=a.create_uid
                        AND e.id=a.write_uid
                       )
            """
        )
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_id_ext_document ON ext_document (id)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_name_ext_document ON ext_document (name)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_filename_ext_document ON ext_document (filename)")

        cr.execute("CREATE INDEX IF NOT EXISTS idx_product_tmpl_id_product_product ON product_product (product_tmpl_id)")
        cr.execute(
            """
            CREATE OR REPLACE VIEW ext_component AS (
                SELECT a.id, b.id as tmpl_id, b.name,b.engineering_code, b.engineering_revision, b.description, c.login as created, b.state, a.create_date, d.login as changed, a.write_date
                    FROM product_product a, product_template b, res_users c, res_users d 
                    WHERE
                         b.id IN
                        (
                            SELECT product_tmpl_id FROM product_product
                        )
                        AND a.product_tmpl_id=b.id
                        AND c.id=a.create_uid
                        AND d.id=a.write_uid
                        )
            """
        )
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_id_ext_component ON ext_component (id)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx__tmpl_id_ext_component ON ext_component (tmpl_id)")
        
        cr.execute("CREATE INDEX IF NOT EXISTS idx_type_mrp_bom ON mrp_bom (type)")
        cr.execute(
            """
            CREATE OR REPLACE VIEW ext_bom AS (
               SELECT f.id, f.create_date, d.login as created, c.write_date, e.login as changed, a.id as father_id, a.name as father,a.engineering_code as father_code,a.engineering_revision as father_rv,a.description as father_desc,b.id as child_id, b.name as child,b.engineering_code as child_code,b.engineering_revision as child_rv,b.description as child_desc
                    FROM ext_component a, ext_component b, mrp_bom c, res_users d, res_users e, mrp_bom f
                    WHERE
                    b.id IN
                        ( 
                            SELECT distinct(product_id) FROM mrp_bom
                            WHERE
                                type = 'ebom'
                            AND bom_id IS NOT NULL
                        )
                    AND f.product_id = b.id
                    AND c.id = f.bom_id 
                    AND c.type = 'ebom'
                    AND a.id = c.product_id
                    AND d.id = f.create_uid
                    AND e.id = f.create_uid
                    order by a.name,b.name
                )
            """
        )
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_id_ext_bom ON ext_bom (id)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_father_id_ext_bom ON ext_bom (father_id)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_child_id_ext_bom ON ext_bom (child_id)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_father_ext_bom ON ext_bom (father)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_father_code_ext_bom ON ext_bom (father_code)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_father_rv_ext_bom ON ext_bom (father_rv)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_child_ext_bom ON ext_bom (child)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_child_code_ext_bom ON ext_bom (child_code)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_child_rv_ext_bom ON ext_bom (childr_rv)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_create_date_ext_bom ON ext_bom (create_date)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_write_date_ext_bom ON ext_bom (write_date)")

        cr.execute("CREATE INDEX IF NOT EXISTS idx_parent_id_plm_document_relation ON plm_document_relation (parent_id)")
        cr.execute("CREATE INDEX IF NOT EXISTS idx_child_id_plm_document_relation ON plm_document_relation (child_id)")
        cr.execute("CREATE INDEX IF NOT EXISTS idx_create_uid_plm_document_relation ON plm_document_relation (create_uid)")
        cr.execute(
            """
            CREATE OR REPLACE VIEW ext_docbom AS (
                SELECT c.id, c.create_date, d.login as created, a.changed, a.id as father_id, a.name as father,a.revisionid as father_rv,a.minorrevision as father_min,a.filename as father_file,c.link_kind as kind,b.id as child_id, b.name as child,b.revisionid as child_rv,b.minorrevision as child_min,b.filename as child_file
                    FROM ext_document a, ext_document b, plm_document_relation c, res_users d
                    WHERE
                        b.id IN
                        (
                         SELECT distinct(child_id) FROM plm_document_relation 
                         )
                        AND c.child_id = b.id
                        AND a.id = c.parent_id
                        AND d.id = c.create_uid
                        order by c.id
                   )
            """
        )
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_id_ext_bom ON ext_bom (id)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_father_id_ext_bom ON ext_bom (father_id)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_child_id_ext_bom ON ext_bom (child_id)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_father_ext_bom ON ext_bom (father)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_father_code_ext_bom ON ext_bom (father_code)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_father_rv_ext_bom ON ext_bom (father_rv)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_father_min_ext_bom ON ext_bom (father_min)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_father_file_ext_bom ON ext_bom (father_file)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_child_ext_bom ON ext_bom (child)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_child_code_ext_bom ON ext_bom (child_code)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_child_rv_ext_bom ON ext_bom (childr_rv)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_child_min_ext_bom ON ext_bom (child_min)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_child_file_ext_bom ON ext_bom (child_file)")
#         cr.execute("CREATE INDEX IF NOT EXISTS idx_create_date_ext_bom ON ext_bom (create_date)")

        cr.execute(
            """
            CREATE OR REPLACE VIEW ext_docref AS (
                SELECT c.id, c.create_date, d.login as created, a.changed, a.id as father_id, a.name as father,a.revisionid as father_rv,a.minorrevision as father_min,a.filename as father_file,c.link_kind as kind,b.id as child_id, b.name as child,b.revisionid as child_rv,b.minorrevision as child_min,b.filename as child_file
                    FROM ext_document a, ext_document b, plm_document_relation c, res_users d
                    WHERE
                        a.id IN
                        (
                         SELECT parent_id FROM plm_document_relation 
                            WHERE
                               link_kind = 'LyTree'
                            OR link_kind = 'RfTree'
                         )
                        AND c.parent_id = a.id
                        AND b.id = c.child_id
                        AND d.id = c.create_uid
                        order by c.id
                   )
            """
        )

        cr.execute("CREATE INDEX IF NOT EXISTS idx_component_id_plm_component_document_rel ON plm_component_document_rel (component_id)")
        cr.execute("CREATE INDEX IF NOT EXISTS idx_document_id_plm_component_document_rel ON plm_component_document_rel (document_id)")
        cr.execute(
            """
            CREATE OR REPLACE VIEW ext_linkdoc AS (
                SELECT c.id, c.create_date, a.id as component_id, a.name as component,a.engineering_code as code,a.engineering_revision as component_rv,b.id as document_id, b.name as document,b.revisionid as document_rv,b.minorrevision as document_min, b.filename as filename
                    FROM ext_component a, ext_document b, plm_component_document_rel c
                    WHERE
                        a.id IN
                        (
                        SELECT component_id FROM plm_component_document_rel 
                        )
                        AND c.component_id = a.id
                        AND b.id = c.document_id
                        order by c.id
                   )
            """
        )

        cr.execute(
            """
            CREATE OR REPLACE VIEW ext_checkout AS (
                SELECT b.id, b.create_date, c.login as user, a.id as document_id, a.name as document, a.revisionid as document_rv,a.minorrevision as document_min, b.hostname as host, b.hostpws as path, a.filename as filename
                    FROM ext_document a, plm_checkout b, res_users c
                    WHERE
                        a.id IN
                        (
                         SELECT documentid FROM plm_checkout 
                        )
                         AND a.id = b.documentid
                         AND c.id = b.userid
                         order by b.id
                     )
            """
        )

        dbuser = tools_config.get('plm_db_user', False)
        dbname = cr.dbname
        if dbuser and dbname:
            cr.execute("ALTER ROLE {dbuser} LOGIN".format(dbuser=dbuser))
            cr.execute("GRANT CONNECT ON DATABASE {dbname}   TO {dbuser}".format(dbname=dbname,dbuser=dbuser))
            cr.execute("GRANT SELECT  ON TABLE ext_document  TO {dbuser}".format(dbuser=dbuser))
            cr.execute("GRANT SELECT  ON TABLE ext_component TO {dbuser}".format(dbuser=dbuser))
            cr.execute("GRANT SELECT  ON TABLE ext_checkout  TO {dbuser}".format(dbuser=dbuser))
            cr.execute("GRANT SELECT  ON TABLE ext_bom       TO {dbuser}".format(dbuser=dbuser))
            cr.execute("GRANT SELECT  ON TABLE ext_docbom    TO {dbuser}".format(dbuser=dbuser))
            cr.execute("GRANT SELECT  ON TABLE ext_linkdoc   TO {dbuser}".format(dbuser=dbuser))
      
plm_config_settings()


class plm_logging(orm.Model):
    _name = 'plm.logging'
    _description = "PLM Log Activities"
    _table = "plm_logging"
    _order = 'name'

    _columns = {
        'name': fields.char('Name', help="Entity name."),
        'revision': fields.char('Revision', help="Revision involved."),
        'file': fields.char('File', help="File name (in case of documents)."),
        'type': fields.char('Type', help="Entity Type."),
        'op_type': fields.char('Operation Type', help="Operation Type"),
        'op_note': fields.char('Operation Note', help="Description of Operation"),
        'op_date': fields.datetime('Operation Date', help="Operation Date"),
        'userid': fields.many2one('res.users', 'Related User'),
    }

    #######################################################################################################################################33

    #   Overridden methods for this entity

    def unlink(self, cr, uid, ids, context=None):
        return False

    def create(self, cr, uid, values={}, context=None):
        newID=False
        if values and values.get('name', False):
            context = context or self.pool['res.users'].context_get(cr, uid)
            try:
                newID=super(plm_logging, self).create(cr, uid, values, context=context)
            except Exception as ex:
                raise Exception(" (%r). It has tried to create with values : (%r)." % (ex, values))
        return newID

    def getchanges(self, cr, uid, objectID=None, values={}, context=None):
        changes=""
        if objectID and values:
            just2check=objectID._all_columns.keys()
            changes="Changed values: "
            for keyName in values.keys():
                if keyName in just2check:
                    changes+="'{key}' was '{old}' now is '{new}', ".format(key=keyName, old=objectID[keyName], new=values[keyName])
        return changes

plm_logging()
