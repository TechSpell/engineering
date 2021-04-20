# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2011-2015 OmniaSolutions srl (<http://www.omniasolutions.eu>). All Rights Reserved
#    Copyright (C) 2016-2020 Techspell srl (<http://www.techspell.eu>). All Rights Reserved
#    Copyright (C) 2020-2021 Didotech srl (<http://www.didotech.com>). All Rights Reserved
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
        'opt_obsoletedinbom': fields.boolean("Allow Obsoleted in BoM", help="Allow Obsoleted products releasing a BoM. Default = False."),
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
        tableViews, quickTables, columnViews=self.getColumnViews(cr, uid)
        criteria=self.getCriteriaNames(cr, uid)
        user = tools_config.get('plm_db_user', False) or tools_config.get('db_user', False) or ''
        pwd = tools_config.get('plm_db_password', False) or tools_config.get('db_password', False) or ''
        host = tools_config.get('plm_db_host', False) or tools_config.get('db_host', False) or socket.gethostname()
        port = tools_config.get('plm_db_port', False) or tools_config.get('db_port', False) or 5432
        dbname = cr.dbname
        if (host=="127.0.0.1") or (host=="localhost") or (host==""):
            host=socket.gethostname()
        return ([user,pwd,host,port,dbname],tableViews,quickTables,columnViews,criteria)

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
        return packDictionary(self.getValueProperties(cr, uid, userType, editor, codeProperties, propNames, context=context))

    def GetValuesByID(self, cr, uid, request=None, context=None):
        """
            Get property values passing object to query, editor, property names as dictionary.
        """
        objectID, editor, propNames=request
        propNames=getCleanBytesList(propNames)
        
        return packDictionary(self.getValuePropertiesbyObject(cr, uid, objectID, editor, propNames, context=context))

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
        ret={}
        if userType!=None and codeProperties:
            context = context or self.pool['res.users'].context_get(cr, uid)
            objectID=self.getCodedObject(cr, uid, userType, codeProperties)
            if objectID:
                ret=self.getValuePropertiesbyObject(cr, uid, objectID, editor, propNames, context=context)
        return ret

    def getValuePropertiesbyObject(self, cr, uid, objectID=None, editor="", propNames=[], context=None):
        """
            Get Properties (as dictionary) to be managed in editor.
        """
        properties={}
        context = context or self.pool['res.users'].context_get(cr, uid)
        if objectID:
            typeFields=objectID._all_columns
            base_properties = self.getEditProperties(cr, uid, objectID._model, editor, context=context)               # In Extend Client
            for keyName in base_properties.keys():
                tmp_props=dict(zip(base_properties[keyName].keys(), base_properties[keyName].values()))
                tmp_props['value']=objectID[keyName]

                if (typeFields[keyName].column._type in ["many2one","one2many","many2many"]) and typeFields[keyName].column._obj:
                    entityName=typeFields[keyName].column._obj  
                    rows=[]
                    columns=self.getBaseObject(cr,uid, entityName, context=context)
                    if (typeFields[keyName].column._type in ["one2many","many2many"]):
                        related=objectID[keyName].ids if objectID[keyName] else []
                    else:
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
        context = context or {}
        user_id = self.pool['res.users'].browse(cr, uid, uid, context=context)
        context.update({'lang': user_id.lang})
        
        results={
            'About':            _('About'),
            'Login':            _('Execute Login'),
            'CheckIn':          _('Check-In current document'),
            'CheckInRecursive': _('Recursive Check-In from current document'),
            'CheckOut':         _('Check-Out current document'),
            'Upload':           _('Upload current document'),
            'EditParts':        _('Edit Part Data'),
            'EditDocuments':    _('Edit Document Data'),
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
        return packDictionary(results)
 
    def GetClientMessages(self, cr, uid, request=None, default=None, context=None):
        """
            Get Client translated messages.
        """
        context = context or {}
        user_id = self.pool['res.users'].browse(cr, uid, uid, context=context)
        context.update({'lang': user_id.lang})
        results={
            'About00':              _("About Ringer"),
            'About01':              _("LibrePLM Embedded Client"),
            'About02':              _("LibrePLM Embedded Client Not Activated"),
            'Login00':              _("You are already logged.\nWould you continue?"),
            'Login01':              _("Information"),
            'CheckIn00':            _("Check-In Paused"),
            'CheckIn01':            _("Current document seems to be changed.\nWould you continue?"),
            'CheckIn02':            _("You are going to Check-In current document.\nWould you continue?"),
            'CheckIn03':            _("Performing Check-In..."),
            'CheckIn04':            _("Completing operations..."),
            'CheckIn05':            _("Refreshing Data..."),
            'CheckIn06':            _("Current document has not Checked-In."),
            'CheckIn07':            _("Check-In"),
            'CheckIn08':            _("Current document has Checked-In."),
            'CheckIn09':            _("Current document is already Checked-In."),
            'CheckIn10':            _("Current document has not Uploaded."),
            'CheckIn11':            _("Error"),
            'CheckIn12':            _("Information"),
            'CheckOut00':           _("Check-Out Paused"),
            'CheckOut01':           _("Current document seems to be changed.\nWould you continue?"),
            'CheckOut02':           _("You are going to Check-Out current document.\nWould you continue?"),
            'CheckOut03':           _("Performing Check-Out..."),
            'CheckOut04':           _("Completing operations..."),
            'CheckOut05':           _("Refreshing Data..."),
            'CheckOut06':           _("Current document has not Checked-Out."),
            'CheckOut07':           _("Check-Out"),
            'CheckOut08':           _("Current document has Checked-Out."),
            'CheckOut09':           _("Current document is not Checked-In."),
            'CheckOut10':           _("Current document has not Uploaded."),
            'CheckOut11':           _("Error"),
            'CheckOut12':           _("Information"),
            'CheckInR00':           _("Recursive Check-In Paused"),
            'CheckInR01':           _("Current document seems to be changed.\nWould you continue?"),
            'CheckInR02':           _("You are going to Check-In recursively current document.\nWould you continue?"),
            'CheckInR03':           _("Performing Recursive Check-In..."),
            'CheckInR04':           _("Completing operations..."),
            'CheckInR05':           _("Refreshing Data..."),
            'CheckInR06':           _("Current document has not been recursively Checked-In."),
            'CheckInR07':           _("Check-In"),
            'CheckInR08':           _("Current document has been recursively Checked-In."),
            'CheckInR09':           _("Current document is already Checked-In."),
            'CheckInR10':           _("Current document has not Uploaded."),
            'CheckInR11':           _("Error"),
            'CheckInR12':           _("Information"),
            'CheckOutR00':          _("Recursive Check-Out Paused"),
            'CheckOutR01':          _("Current document seems to be changed.\nWould you continue?"),
            'CheckOutR02':          _("You are going to Check-Out recursively from current document.\nWould you continue?"),
            'CheckOutR03':          _("Performing Recursive Check-Out..."),
            'CheckOutR04':          _("Completing operations..."),
            'CheckOutR05':          _("Refreshing Data..."),
            'CheckOutR06':          _("Current document has not been recursively Checked-Out."),
            'CheckOutR07':          _("Check-Out"),
            'CheckOutR08':          _("Current document has been recursively Checked-Out."),
            'CheckOutR09':          _("Current document is not Checked-In."),
            'CheckOutR10':          _("Current document has not Uploaded."),
            'CheckOutR11':          _("Error"),
            'CheckOutR12':          _("Information"),
            'Upload00':             _("Upload stopped. Current document has been modifying and has to be saved locally, before uploading it to server."),
            'Upload01':             _("Warning"),
#             'EditParts00':          _(""),
            'EditDocuments00':      _("This is not Default configuration.\nEdit document data is not allowed."),
            'EditDocuments01':      _("Warning"),
            'AssignDocName00':      _("Preparing to Assign Document Name..."),
            'AssignDocName01':      _("Assigning document Name..."),
            'AssignDocName02':      _("No Part data are available.\nPerhaps you would assign manually current document data.\nWould you continue?"),
            'AssignDocName03':      _("Information"),
            'DocumentOpen00':       _("Preparing Download..."),
            'DocumentOpen01':       _("Downloading document..."),
            'DocumentImport00':     _("Preparing Download..."),
            'DocumentImport01':     _("Downloading document..."),
            'OpenRelatedDocs00':    _("Preparing Download..."),
            'OpenRelatedDocs01':    _("Downloading document..."),
            'ComponentOpen00':      _("Preparing Download..."),
            'ComponentOpen01':      _("Downloading document..."),
            'ComponentImport00':    _("Preparing Download..."),
            'ComponentImport01':    _("Downloading document..."),
            'Clone00':              _("You are working with a CAD system that requires to edit manually links to model."),
            'Clone01':              _("\nDid you link this layout to its new 3D model?"),
            'Clone02':              _("\nWould you continue?"),
            'Clone03':              _("You are going to Clone current Part and Document data.\nWould you continue?"),
            'Clone04':              _("No Part data are available.\nPerhaps you would Clone manually current document data.\nWould you continue?"),
            'Clone05':              _("You are cloning a layout with 3D model not yet saved."),
            'Clone06':              _("Warning"),
            'Clone07':              _("Information"),
            'NewRevision00':        _("You are going to execute New Revision both on current Product and Document data.\nAre you sure to continue?"),
            'NewRevision01':        _("Performing New Revision..."),
            'NewRevision02':        _("You cannot execute New Revision on current Product and Document.\nCheck on DB for status of Product or Document."),
            'NewRevision03':        _("You cannot execute New Revision on current Document.\nCheck on DB for status of Document."),
            'NewRevision04':        _("You cannot execute New Revision on current Product.\nCheck on DB for status of Product."),
            'NewRevision05':        _("You cannot execute New Revision on Layout Document.\nYou have to execute 'New Document Revision' instead."),
            'NewRevision06':        _("Warning"),
            'NewRevision07':        _("Information"),
            'NewDocRevision00':     _("You are going to execute New Revision on current Document.\nAre you sure to continue?"),
            'NewDocRevision01':     _("Performing New Revision..."),
            'NewDocRevision02':     _("You cannot execute New Revision on current Document.\nCheck on DB for status of Document."),
            'NewDocRevision03':     _("You cannot execute New Revision on current Document.\nCheck on DB for status of Document."),
            'NewDocRevision04':     _("Warning"),
            'NewDocRevision05':     _("Information"),
            'NewMinorRevision00':   _("You are going to execute New Minor Revision on current Document.\nAre you sure to continue?"),
            'NewMinorRevision01':   _("Performing New Revision..."),
            'NewMinorRevision02':   _("You cannot execute New Revision on current Document.\nCheck on DB for status of Document."),
            'NewMinorRevision03':   _("You cannot execute New Revision on current Document.\nCheck on DB for status of Document."),
            'NewMinorRevision04':   _("Warning"),
            'NewMinorRevision05':   _("Information"),
            'PurgePWS00':           _("You are going to execute Purge operation on\nyour Private WorkSpace.\nAre you sure to continue?"),
            'PurgePWS01':           _("Information"),
            'activationMessage00':  _("LibrePLM Client is not Activated"),
            'activationMessage01':  _("Information"),
            'clone00':              _("Performing Clone..."),
            'editParts00':          _("This is a 2D Layout, it's not allowed to use 'EditParts'.\nUse 'AssigndocName' instead 'EditParts' to assign document data."),
            'editParts01':          _("Information"),
            'saveCurDocument00':    _("Assigning properties to current document..."),
            'getNewDocumentName00': _("Acquiring a new Document Name..."),
            'assignDocName00':      _("Assigning properties to current document..."),
            'assignDocName01':      _("Error assigning new file name"),
            'assignDocName02':      _("already exists"),
            'assignDocName03':      _("Warning"),
            'assignDocName04':      _("Information"),
            'assignDocName10':      _("You are going to assign document data.\nWould you continue?"),
            'assignDocName11':      _("Current document has already saved in DB.\n\n It will be created a new document."),
            'assignDocName12':      _("Current document has reference not yet saved in DB.\n\n Save it before, then retry to save this one."),
            'analysisUpload00':     _("Collecting data for Upload evaluation."),
            'analysisUpload01':     _("Collected data."),
            'analysisUpload02':     _("Preparing Upload..."),
            'analysisUpload03':     _("Deferring Upload..."),
            'analysisUpload04':     _("Upload"),
            'analysisUpload05':     _("Current document will be uploaded to server."),
            'analysisUpload06':     _("Upload stopped. Current document was modified and/or it has to be regenerated before to Upload it.\nPlease, regenerate and save it locally before to perform Upload again."),
            'analysisUpload07':     _("Refreshing Data..."),
            'analysisUpload08':     _("Upload stopped. Some error occurred during execution.\nPlease, try regenerating current document and save it locally before to perform Upload again."),
            'analysisUpload09':     _("Upload interface object is not running.\nPlease, restart the O.S. then try to perform Upload again."),
            'analysisUpload10':     _("Warning"),
            'analysisUpload11':     _("Error"),
            'blindUpload00':        _("Upload stopped"),
            'blindUpload01':        _("Current document"),
            'blindUpload02':        _("was modified but it has Checked-Out to user"),
            'blindUpload03':        _("on host"),
            'blindUpload04':        _("You cannot upload changes"),
            'blindUpload05':        _("was modified and you are going to upload data to server"),
            'blindUpload06':        _("Would you continue?"),
            'blindUpload07':        _("is not newer of the one already uploaded to server"),
            'blindUpload08':        _("Upload stopped. Current document was modified but it has Checked-In.\nTake it in check-out for you before to upload changes."),
            'blindUpload09':        _("You are going to upload data to server as a new document.\nWould you continue?"),
            'blindUpload10':        _("Preparing Upload..."),
            'blindUpload11':        _("Deferring Upload..."),
            'blindUpload12':        _("Upload"),
            'blindUpload13':        _("Current document will be uploaded to server."),
            'blindUpload14':        _("Upload stopped. Current document was modified and/or it has to be regenerated before to Upload it.\nPlease, regenerate and save it locally before to perform Upload again."),
            'blindUpload15':        _("Refreshing Data..."),
            'blindUpload16':        _("Upload stopped. Some error occurred during execution.\nPlease, try regenerating current document and save it locally before to perform Upload again."),
            'blindUpload17':        _("Upload interface object is not running.\nPlease, restart the O.S. then try to perform Upload again."),
            'blindUpload18':        _("Error"),
            'blindUpload19':        _("Warning"),
            'blindUpload20':        _("Information"),
            'closingMessage00':     _("Error"),

            'internalProcess00':    _("Requested file"),
            'internalProcess01':    _("was uploaded successfully on server"),
            'prepareRequest00':     _("Nothing to do"),
            'prepareRequest01':     _("Document unchanged."),
            'prepareRequest02':     _("Local part."),
            'prepareRequest03':     _("To Upload"),
            'prepareRequest04':     _("Document managed as attached."),
            'prepareRequest05':     _("Part without a proper Document Name."),
            'prepareRequest06':     _("Part without a proper Document Revision."),
            'prepareRequest07':     _("Part without a proper Document Minor Revision."),
            'prepareRequest08':     _("Part without a proper Product Part Number."),
            'prepareRequest09':     _("Part without a proper Product Part Revision."),
            'prepareRequest10':     _("To Upload as new document."),
            'prepareRequest11':     _("To Refuse"),
            'prepareRequest12':     _("Cannot execute Upload. Missing filename"),
            'prepareRequest13':     _("To Update"),
            'prepareRequest14':     _("Document changed locally but Upload has denied because checked-in."),
            'prepareRequest15':     _("Document changed locally but Upload has denied because checked-out to a different user."),
            'prepareRequest16':     _("Document changed locally and checked-out."),
            'prepareRequest17':     _("Document Upload has denied because checked-in."),
            'prepareRequest18':     _("Document checked-out to a different user."),
            'prepareRequest19':     _("Refused"),
            'prepareRequest20':     _("Cannot execute Upload. Status doesn't allow uploading."),
            'prepareRequest21':     _("Document Upload has denied because checked-in."),
            'postSaveDocuments00':  _("Counted files"),
            'postSaveDocuments01':  _("Uploaded documents"),
            'postSaveDocuments02':  _("Completed upload of"),

            'CreatePopupMenu00':    _("Activation"),
            'CreatePopupMenu01':    _("Ready to Process"),
            'CreatePopupMenu02':    _("Processing Requests"),
            'CreatePopupMenu03':    _("Options"),
            'CreatePopupMenu04':    _("Force Refresh"),
            'CreatePopupMenu05':    _("Server is Unreachable"),
            'CreatePopupMenu06':    _("Login"),
            'CreatePopupMenu07':    _("About"),
            'CreatePopupMenu08':    _("Attention"),
            'CreatePopupMenu09':    _("Waiting for connection/syncronization to Server."),
            'CreatePopupMenu10':    _("Exit"),
            
            'SetIconTrayMessages00':_("PageBoy Tray Servant is Syncronizing"),
            'SetIconTrayMessages01':_("PageBoy Tray Servant is Starting Up"),
            'SetIconTrayMessages02':_("PageBoy Tray Servant Started"),
            'SetIconTrayMessages03':_("PageBoy Tray Servant has failed"),

            'LeftTrayMessages00':   _("Servant"),
            'LeftTrayMessages01':   _("not"),
            'LeftTrayMessages02':   _("Info"),
            'LeftTrayMessages03':   _("logged on Odoo server"),
            'LeftTrayMessages04':   _("with user"),

            'AboutMessages00':      _("License"),
            'AboutMessages01':      _("Expire Date"),
            'AboutMessages02':      _("Tray Application to assist background operations."),

            'optionsDialog00':      _("Client Options"),
            'optionsDialog01':      _("Successfully Saved."),

            'downMessage00':        _("Warning"),
            'downMessage001':       _("Server doesn't answer or network has errors."),

            'pboyMessages00':       _("Warning"),
            'pboyMessages01':       _("Your PLM Client is not activated."),
            'pboyMessages02':       _("Error"),
            'pboyMessages03':       _("Some issue accessing to Part Data."),
            'pboyMessages04':       _("Some issue accessing to Document Data."),
            'pboyMessages05':       _("User"),
            'pboyMessages06':       _("is not logged on server"),
            'pboyMessages07':       _("Some issue accessing to Knowledge interface."),
            'pboyMessages08':       _("Server doesn't answer or network has errors. Please, contact your IT administrator."),

            'LoginDialog':      {
                'TITLE':        {'title': _("Server Login"), 'pageTitle': _("Connection Parameters")},
                'SERVER_NAME':  {'label': _("Server Name"), 'tooltip': _("Insert the Server Name.")},
                'DB_NAME':      {'label': _("DB Name"), 'tooltip': _("Insert the database Name.")},
                'PORT':         {'label': _("Port No"), 'tooltip': _("Insert the port number.")},
                'PROTOCOL':     {'label': _("Protocol"), 'tooltip': _("Insert the protocol")},
                'USER':         {'label': _("User"), 'tooltip': _("Insert the user account")},
                'PWD':          {'label': _("Password"), 'tooltip': _("Insert the password")},
                },

            'OptionsDialog':      {
                'TITLE':                     {'title': _("Options"), 'pageTitle': _("Optional Parameters")},
                'DEFERREDOPEN':              {'label': _("Deferred Open"), 'tooltip': _("Deferred downloading for files if their size or number exceeds limits. Default is False.")},
                'DATAPACKAGE':               {'label': _("Data package [MB]"), 'tooltip': _("Dimensions (in MegaBytes) to automatically decide downloading of files from server. Used with 'Deferred Open.")},
                'FILEPACKAGE':               {'label': _("File package number"), 'tooltip': _("Number of files involved to automatically decide downloading  from server. Used with 'Deferred Open' active.")},
                'DEFERREDUPLOAD':            {'label': _("Executes Background Upload"), 'tooltip': _("Deferred uploading. This option allows to execute document Upload using a background job queue (True), rather a foreground on-line process (False). Default is True.")},
                'WAIT1STUPLOAD':             {'label': _("Wait for initial upload [seconds]"), 'tooltip': _("Time (in seconds) to wait before to start initial uploading of files to server. Used with 'Deferred Upload' active.")},
                'DEFAULTCONFIGURATIONNAME':  {'label': _("Default Configuration Name"), 'tooltip': _("Name of the configuration has to be considered as default. Used to distinguish active configuration.")},
                'AUTOASSIGNDOCNAME':         {'label': _("Automatic Document P/N from Product"), 'tooltip': _("This option avoids to edit document data, assigning them automatically from product. Default is False.")},
                'FORCEDOCUMENTNAME':         {'label': _("Force to assign Document P/N"), 'tooltip': _("This option avoids to reuse document file name (if any) as document P/N. Default is True.")},
                'ANALYSISUPLOAD':            {'label': _("Analysis before to perform Upload"), 'tooltip': _("This option allows to execute document analysis before Upload, to show how document will be managed uploading to database. Default is False.")},
                'SAVEOPENSETTINGS':          {'label': _("Save settings used for Open Documents"), 'tooltip': _("This option allows to store settings used in Component or Document Open and Import interfaces. Default is False.")},
                'PERMANENTLIST':             {'label': _("Maintains opening list"), 'tooltip': _("This option allows to store latest opened document name. Default is False.")},
                'FORCESAVE':                 {'label': _("Force to execute upload Document"), 'tooltip': _("This option allows to force uploading a file also if seems changed. Default is False.")},
                },
 
            'componentDialog':      {
                'TITLE':                     {'title': _("Search on Products"), 'pageTitle': _("Search on Products")},
                'name':                      _("Name"),
                'description':               _("Description"),
                'nofilters':                 _("No filters applied."),
                'printout':                  _("PrintOut"),
                'force':                     _("Force Download in PWS"),
                'opening':                   _("Opening Options"),
                'saved':                     _("As Saved"),
                'updated':                   _("All Updated"),
                'save':                      _("Save"),
                'reload':                    _("Reload"),
                'addcriteria':               _("Add Filter Criteria"),
                'applycriteria':             _("Apply Filter Criteria"),
                'namecriteria':              _("Name"),
                'criteria':                  _("Criteria"),
                'valuecriteria':             _("Value"),
                'cancel':                    _("Cancel"),
                'ok':                        _("OK"),
                'ttip01':                    _("It will be applied only to Checked-In files."),
                'ttip02':                    _("Download files updated to latest revision or as saved."),
                'ttip03':                    _("Preloaded filter name."),
                'filtertitle':               _("Filter Conditions"),
                'options':                   _("Options"),
                'qfilters':                  _("Quick Filters"),
                'opsession':                 _("Opened in session"),
                'explosion':                 _("Explosion"),
                'whereused':                 _("Where Used"),
                'search':                    _("Search"),
                'filters':                   _("Filters"),
                'results':                   _("Results found"),
                'filtersappd':               _("Filters applied"),
                 },

            'documentDialog':      {
                'TITLE':                     {'title': _("Search on Documents"), 'pageTitle': _("Search on Documents")},
                'name':                      _("Name"),
                'nofilters':                 _("No filters applied."),
                'printout':                  _("PrintOut"),
                'force':                     _("Force Download in PWS"),
                'opening':                   _("Opening Options"),
                'saved':                     _("As Saved"),
                'updated':                   _("All Updated"),
                'save':                      _("Save"),
                'reload':                    _("Reload"),
                'addcriteria':               _("Add Filter Criteria"),
                'applycriteria':             _("Apply Filter Criteria"),
                'namecriteria':              _("Name"),
                'criteria':                  _("Criteria"),
                'valuecriteria':             _("Value"),
                'cancel':                    _("Cancel"),
                'ok':                        _("OK"),
                'ttip01':                    _("It will be applied only to Checked-In files."),
                'ttip02':                    _("Download files updated to latest revision or as saved."),
                'ttip03':                    _("Preloaded filter name."),
                'filtertitle':               _("Filter Conditions"),
                'options':                   _("Options"),
                'qfilters':                  _("Quick Filters"),
                'opsession':                 _("Opened in session"),
                'search':                    _("Search"),
                'filters':                   _("Filters"),
                'results':                   _("Results found"),
                'filtersappd':               _("Filters applied"),
                 },

            'openRelDialog':      {
                'TITLE':                     {'title': _("Choose a Document"), 'pageTitle': _("Choose a Document")},
                'document':                  _("Document"),
                'revision':                  _("Revision"),
                'checkedto':                 _("Checked-Out By"),
                'created':                   _("Create Date"),
                'changed':                   _("Change Date"),
                 },

            'knowledgeDialog':      {
                'TITLE':                     {'title': _("Analysis on document"), 'pageTitle': _("Analysis on document")},
                'online':                    _("Online Uploading"),
                'all':                       _("All"),
                'allowed':                   _("Allowed"),
                'requested':                 _("Requested"),
                'cancel':                    _("Cancel"),
                'ok':                        _("OK"),
                'report':                    _("Print Report"),
                'checkout':                  _("Check-Out"),
                'knowledge':                 _("Knowledge Upload"),
                'ttip01':                    _("Documents contained in current one."),
                'ttip02':                    _("Documents related to current one."),
                'ttip03':                    _("Check this flag, forcing the upload operation to be performed foreground."),
                'ttip04':                    _("Remove all filters."),
                'ttip05':                    _("Filter on documents 'Allowed' to be uploaded."),
                'ttip06':                    _("Filter on documents 'Requested' to be uploaded but not yet allowed."),
                'ttip07':                    _("Execute all check-out operations as allowed."),
                'ttip08':                    _("Print a report on text file."),
                'contained':                 _("Documents Contained"),
                'related':                   _("Documents Related"),
                'filters':                   _("Filters"),
                'actions':                   _("Actions"),
                'nothing':                   _("Nothing to do"),
                'docunchanged':              _("Document unchanged."),
                'toupload':                  _("To Upload"),
                'docum01':                   _("Part without a proper Document Name."),
                'docum02':                   _("Part without a proper Document Revision."),
                'docum03':                   _("Part without a proper Document Minor Revision."),
                'partm01':                   _("Part without a proper Product Part Number."),
                'partm02':                   _("Part without a proper Product Part Revision."),
                'touploaddoc':               _("To Upload as new document."),
                'torefuse':                  _("To Refuse"),
                'torefusedoc':               _("Cannot execute Upload. Missing filename"),
                'toupdate':                  _("To Update"),
                'updcheckedin':              _("Document changed locally but Upload has denied because checked-in."),
                'updcheckedout':             _("Document changed locally but Upload has denied because checked-out to a different user."),
                'updchecked':                _("Document changed locally and checked-out."),
                'reporttitle':               _("Knowledge Upload Report"),
                'reportclose':               _("End Report"),
                },
            }
        return packDictionary(results)
    
    def getCriteriaNames(self, cr, uid, context=None):
        """
            Gets criteria names and their translated labels.
        """
        context = context or {}
        user_id = self.pool['res.users'].browse(cr, uid, uid, context=context)
        context.update({'lang': user_id.lang})
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
        context = context or {}
        user_id = self.pool['res.users'].browse(cr, uid, uid, context=context)
        context.update({'lang': user_id.lang})
        tables=[['ext_document','document'],['ext_component','component'],['ext_docbom','docbom'],
                    ['ext_bom','mrpbom'],['ext_checkout','checkout'],['ext_linkdoc','linkdoc']]
        quick_tables=[['ext_document','document'],['ext_checkout','checkout']]
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
                   
        return tables, quick_tables, columns

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
        cr.execute("CREATE INDEX IF NOT EXISTS idx_create_date_plm_document_relation ON plm_document_relation (create_date)")

        cr.execute(
            """
            CREATE OR REPLACE VIEW ext_docbom AS (
                SELECT c.id, c.create_date, d.login as created, e.login as changed, a.id as father_id, a.name as father,a.revisionid as father_rv,a.minorrevision as father_min,a.datas_fname as father_file,c.link_kind as kind,b.id as child_id, b.name as child,b.revisionid as child_rv,b.minorrevision as child_min,b.datas_fname as child_file
                    FROM plm_document a, plm_document b, plm_document_relation c, res_users d, res_users e
                    WHERE
                        b.id IN
                        (
                         SELECT distinct(child_id) FROM plm_document_relation 
                         )
                        AND c.child_id = b.id
                        AND a.id = c.parent_id
                        AND d.id = c.create_uid
                        AND e.id = c.write_uid
                        ORDER BY c.id
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
                if keyName in just2check and not(keyName in ['datas','printout','preview']):
                    changes+="'{key}' was '{old}' now is '{new}', ".format(key=keyName, old=objectID[keyName], new=values[keyName])
        return changes

plm_logging()
