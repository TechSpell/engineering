# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2016 TechSpell srl (<http://techspell.eu>). All Rights Reserved
#    $Id$
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
import logging
import datetime
from xml.etree.ElementTree import fromstring

from openerp  import models, fields, api, _, osv
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import openerp.tools.config as tools_config

from .common import getIDs, getCleanList, isAdministrator, packDictionary, unpackDictionary, \
                    getCleanBytesDictionary, getCleanBytesList
                    


class plm_config_settings(models.Model):
    _name = 'plm.config.settings'

    @api.multi
    def execute(self):
        pass

    @api.multi
    def cancel(self):
        pass

    plm_service_id  =   fields.Char(_('Service ID'),            size=128,   help=_("Insert the Service ID and register your PLM module. Ask it to TechSpell."))
    activated_id    =   fields.Char(_('Activated PLM client'),  size=128,   help=_("Listed activated Client."))
    active_editor   =   fields.Char(_('Client Editor Name'),    size=128,   help=_("Used Editor Name"))
    active_node     =   fields.Char(_('OS machine name'),       size=128,   help=_("Editor Machine name"))
    expire_date     =   fields.Datetime(_('Expiration Date'),               help=_("Expiration Date"))
    active_os       =   fields.Char(_('OS name'),               size=128,   help=_("Editor OS name"))
    active_os_rel   =   fields.Char(_('OS release'),            size=128,   help=_("Editor OS release"))
    active_os_ver   =   fields.Char(_('OS version'),            size=128,   help=_("Editor OS version"))
    active_os_arch  =   fields.Char(_('OS architecture'),       size=128,   help=_("Editor OS architecture"))
    node_id         =   fields.Char(_('Registered PLM client'), size=128,   help=_("Listed registered Client."))
    domain_id       =   fields.Char(_('Domain Name'),           size=128,   help=_("Listed domain name."))
    active_kind     =   fields.Char(_('Kind of license'),       size=128,   help=_("Kind of license code ('node-locked' = Local individual license, 'domain-assigned' = Domain level license)."))

#   Option fields managed for each Service ID
    opt_editbom             =   fields.Boolean(_("Edit BoM not in 'draft'"),                    help=_("Allows to edit BoM if product is not in 'Draft' status. Default = False."))
    opt_editreleasedbom     =   fields.Boolean(_("Edit BoM in 'released'"),                     help=_("Allows to edit BoM if product is in 'Released' status. Default = False."))
    opt_duplicatedrowsinbom =   fields.Boolean(_("Allow rows duplicated in BoM"),               help=_("Allows to duplicate product rows editing a BoM. Default = True."),                          default = True)
    opt_autonumbersinbom    =   fields.Boolean(_("Allow to assign automatic positions in BoM"), help=_("Allows to assign automatically item positions editing a BoM. Default = False."))
    opt_autostepinbom       =   fields.Integer(_("Assign step to automatic positions in BoM"),  help=_("Allows to use this step assigning item positions, editing a BoM. Default = 5."),            default = 5)
    opt_autotypeinbom       =   fields.Boolean(_("Assign automatically types in BoM"),          help=_("Allows to use the same type of BoM in all new items, editing a BoM. Default = True."),      default = True)
#   Option fields managed for each Service ID

    @api.model
    def GetServiceIds(self, oids=None, default=None):
        """
            Get all Service Ids registered.
        """
        ids = []
        
        for part in self.search([('activated_id', '=', False)]):
            ids.append(part.plm_service_id)
        return getCleanList(ids)

    @api.model
    def RegisterActiveId(self, vals):
        """
            Registers Service Id & Activation infos.  [serviceID, activation, activeEditor, expirationDate, (system, node, release, version, machine, processor), nodeId, domainName ]
        """
        default = {}
        
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

            for partId in self.search([('plm_service_id', '=', serviceID), ('activated_id', '=', activation),
                                            ('active_editor', '=', activeEditor)]):
                partId.write(default)
                return False

            self.create(default)
        return False

    @api.model
    def GetActivationId(self, vals=[], default=None):
        """
            Gets activation codes as registered.
        """
        
        results = []
        found = []
        today = datetime.datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        nodeId, domainID, activeEditor, _ = vals

        if len(domainID) > 0:
            for partId in self.search([('domain_id', '=', domainID), ('expire_date', '>', today)]):
                results.append((partId.plm_service_id, partId.activated_id, partId.domain_id))
                found.append(partId.id)

        for partId in self.search([('node_id', '=', nodeId), ('expire_date', '>', today)]):
            if partId.id not in found:
                results.append((partId.plm_service_id, partId.activated_id, partId.domain_id))

        return results

    def getoptionfields(self):
        ret=[]
        for keyName in self._fields.keys():
            if keyName.startswith('opt_'):
                ret.append(keyName)
        return ret

    @api.model
    def GetOptions(self, request=None, default=None):
        """
            Gets activation codes as registered.
        """
        results = {}
        
        optionNames=self.getoptionfields()
        for optId in self.search([('activated_id', '=', False), ('plm_service_id', '!=', False)]):
            for optionName in optionNames:
                results[optionName]=optId[optionName]
        return results

###################################################################
#                        C R U D  Methods                         #
###################################################################

    @api.model
    def Create(self, request=[], default=None):
        """
            Creates items on DB.
        """
        results=[]
        
        objectName, values=request
        userType=self.env[objectName] if objectName in self.env else None
        
        if userType!=None:
            for valueSet in values:
                results.append(userType.create(valueSet))
        return results

    @api.model
    def Read(self, request=[], default=None):
        """
            Read given fields on items on DB.
        """
        results=[]
        
        objectName, criteria, fields = request        
        if len(fields)<1:
            return results
        
        userType=self.env[objectName] if objectName in self.env else None
        
        if userType!=False and userType!=None:
            ids=userType.search(criteria)
            if ids:
                tmpData=ids.export_data(fields)
                if 'datas' in tmpData:
                    results=tmpData['datas']
        return results

    @api.model
    def Update(self, request=[], default=None):
        """
            Updates items on DB.
        """
        
        objectName, criteria, values = request        
        if len(values)<1:
            return False        
        userType=self.env[objectName] if objectName in self.env else None
        
        if userType!=None:
            ids=userType.search(criteria)
            for oid in ids:
                oid.write(values)
        return False

    @api.model
    def Delete(self, request=[], default=None):
        """
            Remove items from DB.
        """
        
        objectName, criteria, values = request        
        if len(values)<1:
            return False        
        userType=self.env[objectName] if objectName in self.env else None
        
        if userType!=None:
            objIDs=userType
            objIDs |= userType.search(criteria)
            objIDs.unlink()
        return False
    
###################################################################
#                        C R U D  Methods                         #
###################################################################

    @api.model
    def GetDocumentByName(self, request=None, default=None):
        """
            Gets content of document named <docName> (latest revision).          
        """
        docID, nameFile, contentFile, writable, lastupdate=[False, "","", False, False]
        
        docName=request
        if docName:
            docType=self.env["plm.document"]
            docIds = docType.search([('name','=',docName),('type','=','binary')], order='revisionid')
            if docIds:
                oid=docIds[len(docIds)-1].id
                docID, nameFile, contentFile, writable, lastupdate = docType._data_get_files([oid])[0]
        return docID, nameFile, contentFile, writable, lastupdate

    @api.model
    def GetCustomProcedure(self, request=None, default=None):
        """
            Gets document named 'CustomProcedure'           
        """
        
        _, _, contentFile, _, _ = self.GetDocumentByName('CustomProcedure', default)
        return contentFile

    @api.model
    def GetAttachedPDF(self, request=[], default=None):
        """
            Gets attached PDF.          
        """
        ids=request
        if ids:
            from pdm.reports.report.document_report import create_report
            ret, _ =create_report(self, ids, datas=None)         
        return ret

    @api.model
    def GetDataConnection(self, request=None, default=None):
        """
            Gets data for external connection to DB.
        """
        
        tableViews,columnViews=self.getColumnViews()
        criteria=self.getCriteriaNames()
        user = tools_config.get('plm_db_user', False) or tools_config.get('db_user', False) or ''
        pwd = tools_config.get('plm_db_password', False) or tools_config.get('db_password', False) or ''
        host = tools_config.get('plm_db_host', False) or tools_config.get('db_host', False) or socket.gethostname()
        port = tools_config.get('plm_db_port', False) or tools_config.get('db_port', False) or 5432
        dbname = self._cr.dbname
        if (host=="127.0.0.1") or (host=="localhost") or (host==""):
            host=socket.gethostname()
        return ([user,pwd,host,port,dbname],tableViews,columnViews,criteria)

    @api.model
    def GetServerTime(self):
        """
            calculate the server db time 
        """
        return datetime.datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT), DEFAULT_SERVER_DATETIME_FORMAT

    @api.model
    def GetUserSign(self):
        """
            Gets the user login, name and signature
        """
        ret=["","",""]
        
        for uiUser in self.env['res.users'].browse([self._uid]):
            ret=[uiUser.login, uiUser.name, uiUser.signature]
            break
        return ret

    @api.model
    def GetFieldsModel(self, objectName=""):
        ret=[]
        if objectName:
            ret = list(self.env[objectName]._fields.keys())
        return ret

    @api.model
    def GetDataModel(self, request=None, default=None):
        """
            Get properties as assigned.
        """
        return packDictionary(self.getDataModel(request, default))

    def getDataModel(self, request=None, default=None):
        """
            Get properties as assigned.
        """
        retValues={}
        if request:
            objectName=request
            
            objType=self.env['ir.model']
            for model in objType.search([('model','=',objectName)]):
                for field in model.field_id:
                    retValues.update({field.name:[
                                                   ('description', _(field.field_description)),
                                                   ('type', field.ttype),
                                                   ('relation', field.relation),
                                                   ('required', field.required)
                                                ] })
        return retValues

    def getViewArchitecture(self, criteria=None):
        ret=None
        if criteria:
            
            #TODO: To be implemented inheritance on views.
            ret=self.Read(['ir.ui.view', criteria, ["arch_db"]]) 
        return ret

    @api.model
    def GetFormView(self, request=None, default=None):
        criteria=None
        viewName=request
        if viewName:
            criteria=[('name','=',viewName),('type','=','form')]
        return self.getViewArchitecture(criteria)

    @api.model
    def GetTreeView(self, request=None, default=None):
        criteria=None
        viewName=request
        if viewName:
            criteria=[('name','=',viewName),('type','=','tree')]
        return self.getViewArchitecture(criteria)

    @api.model
    def GetFormViewByModel(self, request=None, default=None):
        criteria=None
        modelName=request
        if modelName:
            criteria=[('model','=',modelName),('type','=','form')]
        return self.getViewArchitecture(criteria)
        
    @api.model
    def GetTreeViewByModel(self, request=None, default=None):
        criteria=None
        modelName=request
        if modelName:
            criteria=[('model','=',modelName),('type','=','tree')]
        return self.getViewArchitecture(criteria)

    @api.model
    def GetProperties(self, request=None, default=None):
        """
            Get properties as assigned.
        """
        objectName, editor=request
        
        userType=self.env[objectName] if objectName in self.env else None
        return packDictionary(self.getEditProperties(userType, editor))

    @api.model
    def GetValues(self, request=None, default=None):
        """
            Get property values as requested.
        """
        objectName, editor, codeProperties, propNames=unpackDictionary(request)
        codeProperties=getCleanBytesDictionary(codeProperties)
        propNames=getCleanBytesList(propNames)
        
        userType=self.env[objectName] if objectName in self.env else None        
        return packDictionary(self.getValueProperties(userType, editor, codeProperties, propNames))

    @api.model
    def IsAdministrator(self, request=None, default=None):
        """
            Checks if this user is in PLM Administrator group
        """
        return isAdministrator(self)
    
    @api.model
    def GetEditorProperties(self, request=["", ""]):
        """
            Get Properties (as dictionary) to be managed in editor.
        """
        editor_properties={}
        objectName, editor=request
        if objectName:
            
            userType=self.env[objectName] if objectName in self.env else None
            if userType!=None:        
                editor_properties = userType.editorProperties(editor)   # In Extend Client
        return packDictionary(editor_properties)

    def getEditProperties(self, userType=None, editor=""):
        """
            Get Properties (as dictionary) to be managed in editor.
        """
        properties={}
        if userType!=None:
            editor_properties = userType.editorProperties(editor)       # In Extend Client
            base_properties = userType.defineProperties()               # In Extend Client
            if base_properties:
                typeFields=userType._fields
                propList=list(set(base_properties.keys()).intersection(editor_properties.keys()))
                keyList=list(set(typeFields.keys()).intersection(set(base_properties.keys())))
                for keyName in keyList:
                    tmp_props=dict(zip(base_properties[keyName].keys(), base_properties[keyName].values()))
                    tmp_props['name']=typeFields[keyName].name
                    tmp_props['label']=_(typeFields[keyName].string)
                    fieldType=typeFields[keyName].type

                    tmp_props['tooltip']=""
                    if typeFields[keyName].help:
                        tmp_props['tooltip']=_(typeFields[keyName].help)
    
                    if (fieldType in["char","string","text"]):
                        tmp_props['type']="string"
                        tmp_props['value']=""
                        try:
                            tmp_props['size']=typeFields[keyName].size if not typeFields[keyName].size==None else 255
                        except:
                            tmp_props['size']=4096
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
                        tmp_props['decimal']=typeFields[keyName].digits[1]
                    elif (fieldType=="selection"):    
                        tmp_props['type']="string"
                        tmp_props['value']=""
                        tmp_props['selection']={}
                        try:
                            if typeFields[keyName].related:
                                tmp_props['selection']=dict(typeFields[keyName].related_field.selection)
                            else:
                                tmp_props['selection']=dict(typeFields[keyName].selection)
                        except:
                            tmp_props['selection']={"", "No valid values"}
                    elif (fieldType in ["many2one","one2many","many2many"]) and typeFields[keyName]._related_comodel_name:    
                        criteria=[('id','!=', False),] 
                        tmp_props['value']=False
                        entityName=typeFields[keyName]._related_comodel_name
                        columns=self.getBaseObject(entityName)
                        values=[]
                        dictvalues={}
                        if not tmp_props.get('viewonly', False):
                            values,dictvalues=self.getDataObject(entityName, criteria, columns.keys())
                        tmp_props['type']='object'
                        tmp_props['object']={
                                             "entity": entityName,
                                             "columns": columns,
                                             "columnnames": columns.keys(),
                                             "values": values,
                                             "dictvalues":dictvalues,
                                            }
 
                    if typeFields[keyName].required:
                        tmp_props['mandatory']=True         # If required forces external assignment.
    
                    if keyName in propList:
                        tmp_props['property']=editor_properties[keyName]
 
                    if ('default' in tmp_props) and not ('value' in tmp_props):
                        tmp_props['value']=tmp_props['default']

                    if ('code' in tmp_props) and isinstance(tmp_props['code'], dict):
                        entityName=tmp_props['code'].get('entity', "")
                        if entityName:
                            columns=self.getBaseObject(entityName)
                            values=[]
                            dictvalues={}
                            if columns:
                                criteria=[('id','!=', False),] 
                                values,dictvalues=self.getDataObject(entityName, criteria, columns.keys())
                            tmp_props['code'].update({
                                                "columns": columns,
                                                "columnnames": columns.keys(),
                                                "values": values,
                                                "dictvalues":dictvalues,
                                                })
                      
                    properties[keyName]=tmp_props
        return properties

    def getCodedObject(self, userType=None, codeProperties={}):
        """
            Gets object responding to the first satisfied criteria, expressed by
            codeProperties dictionary ('name' will be evaluated first , anyway).
        """
        objectID=None
        if userType!=None and codeProperties:
            
            listNames=codeProperties.keys()
            if 'name' in listNames:         # This guitar riff to ensure 'name' is evaluated as first one.
                listNames.remove('name')
                listNames[:0]=['name'] 
            for keyName in listNames:
                value=codeProperties[keyName].get('value', None)
                if value:
                    criteria=[(keyName, '=', value)]
                    objIDs = userType.search(criteria, order='id')
                    if len(objIDs) > 0:
                        objectID=objIDs[len(objIDs)-1]
                        break
        return objectID
    
    def getBaseObject(self, userType=False):
        ret={}
        productXmls=self.GetTreeViewByModel(userType)
        if productXmls:
            dataModel=self.getDataModel(userType)
            productXml=fromstring(productXmls[0][0])
            for item in productXml.iter("field"):
                if item.attrib['name'] in dataModel:
                    modelData=dict(dataModel[item.attrib['name']])
                    ret.update( { item.attrib['name']: _(modelData['description']) } )
        return ret

    def getDataObject(self, userType="", criteria=[], columns=[]):
        values,dictvalues=[[],{}]
        if userType and columns:
            objectType=self.env[userType]
            typeFields=objectType._fields
            for objectID in objectType.search(criteria, order='id'):
                dict_data={}
                row_data=[objectID.id]
                for columnName in columns:
                    if typeFields[columnName].type in ["many2one","one2many","many2many"]:
                        dict_data.update({ columnName: objectID[columnName].id })
                        if 'name' in objectID[columnName]._fields:
                            row_data.append(objectID[columnName].name)
#                         else:
#                             row_data.append(objectID[columnName].id)
                    else:
                        dict_data.update({ columnName: objectID[columnName] })
                        row_data.append(objectID[columnName])
                values.append(row_data)
                dictvalues.update({ "{}".format(objectID.id): dict_data })
        return values,dictvalues

    
    def getValueProperties(self, userType=False, editor="", codeProperties={}, propNames=[]):
        """
            Get Properties (as dictionary) to be managed in editor.
        """
        properties={}
        if (userType!=None and userType!=False) and codeProperties:
            
            objectID=self.getCodedObject(userType, codeProperties)
            if objectID:
                typeFields=userType._fields
                base_properties = self.getEditProperties(userType, editor)               # In Extend Client
                for keyName in base_properties.keys():
                    tmp_props=dict(zip(base_properties[keyName].keys(), base_properties[keyName].values()))
                    tmp_props['value']=objectID[keyName]

                    if (typeFields[keyName].type in ["many2one","one2many","many2many"]) and typeFields[keyName]._related_comodel_name:
                        entityName=typeFields[keyName]._related_comodel_name  
                        rows=[]
                        columns=self.getBaseObject(entityName)
                        related=getIDs(objectID[keyName])
                        if related:
                            criteria=[('id','in', related),]
                            rows,_=self.getDataObject(entityName, criteria, columns.keys())

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

    @api.model
    def GetServiceNodes(self, oids=[], default=None):
        """
            Get all Service Ids registered.
        """
        
        message=_("Insert your Activation Code as provided by TechSpell.")
        ids=self.GetServiceIds(oids, default=default)
        return ids, message

    @api.model
    def GetMethodNames(self, request=None, default=None):
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
 
    @api.model
    def GetClientMessages(self, request=None, default=None):
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
    
    def getCriteriaNames(self):
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

    def getColumnViews(self):
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
                          'created' :  {'label':_('Creator'), 'visible':True, 'pos':5},
                          'create_date' :  {'label':_('Created'), 'visible':True, 'pos':6},
                          'changed' :  {'label':_('Modified by'), 'visible':True, 'pos':7},
                          'write_date' :  {'label':_('Changed'), 'visible':True, 'pos':8},
                          'checkedout' :  {'label':_('Checked-Out by'), 'visible':True, 'pos':9},
                          'filename' :  {'label':_('File Name'), 'visible':True, 'pos':10},
                          'preview' :  {'label':_('Preview'), 'visible':False, 'pos':11},
                          },
                
                'component':{
                          'id' : {'label':_('ID'), 'visible':True, 'pos':1},
                          'tmpl_id' : {'label':_('Template ID'), 'visible':False, 'pos':2},
                          'name' : {'label':_('Product Name'), 'visible':True, 'pos':3},
                          'engineering_code' : {'label':_('Engineering Code'), 'visible':True, 'pos':4},
                          'engineering_revision' : {'label':_('Revision'), 'visible':True, 'pos':5},
                          'description' : {'label':_('Description'), 'visible':True, 'pos':6},
                          'created' :  {'label':_('Creator'), 'visible':True, 'pos':7},
                          'create_date' :  {'label':_('Created'), 'visible':True, 'pos':8},
                          'changed' :  {'label':_('Modified by'), 'visible':True, 'pos':9},
                          'write_date' :  {'label':_('Modified'), 'visible':True, 'pos':10},
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
        #TODO: To be evaluated if creation can be parametric so to allow view configuration. 
 
        cr.execute("CREATE INDEX IF NOT EXISTS idx_documentid_plm_checkout ON plm_checkout (documentid)")
        cr.execute("CREATE INDEX IF NOT EXISTS idx_userid_plm_checkout ON plm_checkout (userid)")
        cr.execute("CREATE INDEX IF NOT EXISTS idx_create_uid_plm_document ON plm_document (create_uid)")
        cr.execute("CREATE INDEX IF NOT EXISTS idx_write_uid_plm_document ON plm_document (write_uid)")
        cr.execute(
            """
            CREATE OR REPLACE VIEW ext_document AS (
                SELECT a.id, a.name, a.revisionid, a.minorrevision, d.login as created, a.create_date, d.login as changed, a.write_date, c.login as checkedout, a.datas_fname as filename, a.preview 
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
                SELECT a.id, b.id as tmpl_id, b.name,b.engineering_code, b.engineering_revision, b.description, c.login as created, a.create_date, d.login as changed, a.write_date
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
        
        cr.execute("CREATE INDEX IF NOT EXISTS idx_product_tmpl_id_mrp_bom ON mrp_bom (product_tmpl_id)")
        cr.execute("CREATE INDEX IF NOT EXISTS idx_type_mrp_bom ON mrp_bom (type)")
        cr.execute(
            """
            CREATE OR REPLACE VIEW ext_bom AS (
               SELECT f.id, f.create_date, d.login as created, f.write_date, e.login as changed, a.id as father_id, a.name as father,a.engineering_code as father_code,a.engineering_revision as father_rv,a.description as father_desc,b.id as child_id, b.name as child,b.engineering_code as child_code,b.engineering_revision as child_rv,b.description as child_desc
                    FROM ext_component a, ext_component b, mrp_bom c, res_users d, res_users e, mrp_bom_line f
                    WHERE
                    b.id IN
                        ( 
                            SELECT distinct(product_id) FROM mrp_bom_line
                            WHERE
                            type = 'ebom'
                        )
                    AND f.product_id = b.id
                    AND d.id = f.create_uid
                    AND e.id = f.write_uid
                    AND c.id=f.bom_id 
                    AND c.type = 'ebom'
                    AND a.tmpl_id = c.product_tmpl_id
                    ORDER BY a.name,b.name
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
       

class plm_logging(models.Model):
    _name = 'plm.logging'
    _description = "PLM Log Activities"
    _table = "plm_logging"
    _order = 'name'

    name        = fields.Char     (             string=_('Name'),           size=64, help=_("Entity name."))
    revision    = fields.Char     (             string=_('Revision'),       size=64, help=_("Revision involved."))
    file        = fields.Char     (             string=_('File'),           size=64, help=_("File name (in case of documents)."))
    type        = fields.Char     (             string=_('Type'),           size=64, help=_("Entity Type."))
    op_type     = fields.Char     (             string=_('Operation Type'), size=64, help=_("Operation Type."))
    op_note     = fields.Char     (             string=_('Operation Note'), size=64, help=_("Description of Operation."))
    op_date     = fields.Datetime (             string=_('Operation Date'),          help=_("Operation Date."))
    userid      = fields.Many2one ('res.users', string=_('Related User'),            help=_("Related User."))

    #######################################################################################################################################33

    #   Overridden methods for this entity

    @api.multi
    def unlink(self):
        return False

    @api.model
    def create(self, values={}):
        newID=False
        if values and values.get('name', False):
            try:
                newID=super(plm_logging, self).create(values)
            except Exception as ex:
                logging.error("(%r). It has tried to create with values : (%r)." % (ex, values))
        return newID

    def getchanges(self, objectID=None, values={}):
        changes=""
        if objectID and values:
            just2check=objectID._proper_fields
            for keyName in values.keys():
                if keyName in just2check:
                    changes+="'{key}' was '{old}' now is '{new}', ".format(key=keyName, old=objectID[keyName], new=values[keyName])
            if changes:
                changes="Changed values: "+changes
        return changes

