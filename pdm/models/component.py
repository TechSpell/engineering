# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2016-2018 TechSpell srl (<http://techspell.eu>). All Rights Reserved
#    
#    Created on : 2018-03-01
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

import logging
from datetime import datetime

from odoo  import models, fields, api, _, osv
from odoo.exceptions import UserError

from .common import getListIDs, getCleanList, packDictionary, unpackDictionary, getCleanBytesDictionary, \
                    move_workflow, wf_message_post, isAdministrator, isReleased, \
                    isObsoleted, isUnderModify, isAnyReleased, isDraft, getUpdTime


# USED_STATES=[('draft','Draft'),('confirmed','Confirmed'),('released','Released'),('undermodify','UnderModify'),('obsoleted','Obsoleted')]
# STATEFORRELEASE=['confirmed']
# STATESRELEASABLE=['confirmed','transmitted','released','undermodify','obsoleted']

class plm_component(models.Model):
    _name = 'product.product'
    _inherit = 'product.product'

    create_date     =   fields.Datetime(_('Date Created'),     readonly=True)
    write_date      =   fields.Datetime(_('Date Modified'),    readonly=True)

    #   Internal methods
    def _insertlog(self, ids, changes={}, note={}):
        ret=False
        op_type, op_note=["unknown",""]
        for objID in self.browse(getListIDs(ids)):
            if note:
                op_type="{type}".format(type=note['type'])
                op_note="{reason}".format(reason=note['reason'])
            elif changes:
                op_type='change value'
                op_note=self.env['plm.logging'].getchanges(objID, changes)
            if op_note:
                values={
                        'name': objID.name,
                        'revision': "{major}".format(major=objID.engineering_revision),
                        'type': self._name,
                        'op_type': op_type,
                        'op_note': op_note,
                        'op_date': datetime.now(),
                        'userid': self._uid,
                        }
                objectItem=self.env['plm.logging'].create(values)
                if objectItem:
                    ret=True
        return ret

    def _getbyrevision(self, name, revision):
        return self.search([('engineering_code', '=', name), ('engineering_revision', '=', revision)])

#     def _getExplodedBom(self, ids, level=0, currlevel=0):
#         """
#             Returns a flat list of all children in a Bom ( level = 0 one level only, level = 1 all levels)
#         """
#         result = []
#         
#         if level == 0 and currlevel > 1:
#             return result
#         components = self.browse(ids)
#         relType = self.env['mrp.bom']
#         for component in components:
#             for bomid in component.bom_ids:
#                 children = relType.GetExplodedBom([bomid.id], level, currlevel)
#                 result.extend(children)
#         return result

    def _getChildrenBom(self, component, level=0, currlevel=0):
        """
            Returns a flat list of each child, listed once, in a Bom ( level = 0 one level only, level = 1 all levels)
        """
        result = []
        bufferdata = []
        if level == 0 and currlevel > 1:
            return bufferdata
        for bomid in component.product_tmpl_id.bom_ids:
            for bomline in bomid.bom_line_ids:
                children=self._getChildrenBom(bomline.product_id, level, currlevel+1)
                bufferdata.extend(children)
                bufferdata.append(bomline.product_id.id)
        result.extend(bufferdata)
        return getCleanList(result)

    @api.model
    def RegMessage(self, request=[], default=None):
        """
            Registers a message for requested component
        """
        oid, message = request
        wf_message_post(self, [oid], body=message)
        return False

    def getUserName(self):
        """
            Gets the user name
        """
        userType = self.env['res.users']
        
        uiUser = userType.browse(self._uid)
        return uiUser.name

    def getFromTemplateID(self, oid):
        ret=False
        if oid:
            for prodItem in self.search([('product_tmpl_id', '=', oid)]):
                ret=prodItem
                break
        return ret

    def getTemplateItem(self, oid):
        ret=False
        if oid:
            
            for prodItem in self.browse(getListIDs(oid)):
                ret=prodItem.product_tmpl_id
                break
        return ret

    ##  Customized Automations
    def on_change_name(self, oid, name=False, engineering_code=False):
        
        if name:
            results = self.search([('name', '=', name)])
            if len(results) > 0:
                raise UserError(_("Update Part Error.\n\nPart {} already exists.\nClose with OK to reuse, with Cancel to discharge.".format(name)))
            if not engineering_code:
                return {'value': {'engineering_code': name}}
        return {}

    ##  External methods
    @api.model
    def Clone(self, ids=[], default=None):
        """
            Creates a new copy of the component
        """
        default = {}
        exitValues = {}            
        
        for tmpObject in self.browse(getListIDs(ids)):
            note={
                    'type': 'clone object',
                    'reason': "Creating new cloned entity starting from '{old}'.".format(old=tmpObject.name),
                 }
            self._insertlog(tmpObject.id, note=note)
            newID = self.copy(tmpObject.id, default)
            if newID:
                newEnt = self.browse(newID)
                exitValues = {
                              '_id': newID,
                              'name': newEnt.name,
                              'engineering_code': newEnt.engineering_code,
                              'engineering_revision': newEnt.engineering_revision,
                              'engineering_writable': True,
                              'state': 'draft',
                            }
                break
        return packDictionary(exitValues)

    @api.model
    def CloneVirtual(self, ids=[], default=None):
        """
            Creates a "false" new copy of the component.
            Really returns only new values avoiding creation of new object.
        """
        exitValues = {}
        
        for tmpObject in self.browse(getListIDs(ids)):
            new_name = "Copy of {name}".format(name=tmpObject.name)
            exitValues = {
                          '_id': False,
                          'name': new_name,
                          'engineering_code': new_name,
                          'description': "{desc}".format(desc=tmpObject.description),
                          'engineering_revision': 0,
                          'engineering_writable': True,
                          'state': 'draft',
                          }
            break
        return packDictionary(exitValues)

    @api.model
    def GetUpdated(self, vals=[], default=None):
        """
            Gets Last/Requested revision of given items (by name, revision, update time)
        """
        partData, attribNames = vals
        
        ids = self.GetLatestIds(partData)
        return packDictionary(self.read(getCleanList(ids), attribNames))

    @api.model
    def GetStdPartName(self, vals=[], default=None):
        """
            Gets new P/N reading from entity chosen (taking it from new index on sequence).
        """
        ret=""
        entID, objectName = vals
        if entID and objectName:
            
            userType=self.env[objectName] if (objectName in self.env) else None
            if not(userType==None):
                for objID in userType.browse(getListIDs(entID)):
                    ret=self.GetNewPNfromSeq(objID.sequence_id)
                    break
        return ret

    @api.model
    def GetNewPNfromSeq(self, seqID=None, default=None):
        """
            Gets new P/N from sequence (checks for P/N existence).
        """
        ret=""
        if seqID:
            
            count=0
            while ret=="":
                chkname=self.env['ir.sequence'].browse(seqID.id)._next()
                count+=1
                criteria=[('name', '=', chkname)]
                partIds = self.search(criteria)
                if (partIds==None) or (len(partIds)==0):
                    ret=chkname
                if count>1000:
                    logging.error("GetNewPNfromSeq : Unable to get a new P/N from sequence '{name}'."\
                                  .format(name=seqID.name))
                    break
        return ret

    @api.model
    def GetLatestIds(self, vals=[], default=None):
        """
            Gets Last/Requested revision of given items (by name, revision, update time)
        """
        ids = []
        
        for request in vals:
            partName, _, updateDate = request
            if updateDate:
                criteria=[('engineering_code', '=', partName), ('write_date', '>', updateDate)]
            else:
                criteria=[('engineering_code', '=', partName)]
    
            partIds = self.search(criteria, order='engineering_revision')
            if len(partIds) > 0:
                ids.append(partIds[len(partIds) - 1].id)
        return getCleanList(ids)

    @api.model
    def GetId(self, request=[], default=None):
        """
            Gets Last/Requested revision of given items (by name, revision, update time)
        """
        idd = False
        
        partName, partRev, _ = request
#         partName, partRev, updateDate = request
#         if updateDate:
#             if partRev:
#                 criteria=[('engineering_code', '=', partName), ('engineering_revision', '=', partRev),
#                                         ('write_date', '>', updateDate)]
#             else:
#                 criteria=[('engineering_code', '=', partName), ('write_date', '>', updateDate)]
#         else:
#             if partRev:
#                 criteria=[('engineering_code', '=', partName), ('engineering_revision', '=', partRev)]
#             else:
#                 criteria=[('engineering_code', '=', partName)]
        if isinstance(partRev, int):
            criteria=[('engineering_code', '=', partName), ('engineering_revision', '=', partRev)]
        else:
            criteria=[('engineering_code', '=', partName)]

        partIds = self.search(criteria, order='engineering_revision')
        if len(partIds) > 0:
            idd=partIds[len(partIds) - 1].id
        return idd

    @api.model
    def IsSaveable(self, ids=[], default=None):
        """
            Answers about capability to save requested product
        """
        ret=True
        
        for tmpObject in self.browse(getListIDs(ids)):
            ret=ret and self._iswritable(tmpObject)
        return ret

    @api.model
    def IsRevisable(self, ids=[], default=None):
        """
            Gets if a product is revisable or not.
        """
        ret=False
        
        for tmpObject in self.browse(getListIDs(ids)):
            if isAnyReleased(self, tmpObject.id):
                ret=True
                break
        return ret

    
    @api.model
    def NewRevision(self, ids=[], default=None):
        """
            Creates a new revision of current product
        """
        newID, newIndex = [ False, 0 ]
        
        thisContext={ 'internal_writing':True, 'new_revision':True, }
        for tmpObject in self.browse(getListIDs(ids)):
            latestIDs = self.GetLatestIds( [(tmpObject.engineering_code, tmpObject.engineering_revision, False)] )
            for oldObject in self.browse(latestIDs):
                if isAnyReleased(self, oldObject.id):
                    note={
                            'type': 'revision process',
                            'reason': "Creating new revision for '{old}'.".format(old=oldObject.name),
                         }
                    self._insertlog(oldObject.id, note=note)
                    newIndex = int(oldObject.engineering_revision) + 1
                    default = {
                                'engineering_writable': False,
                                'state': 'undermodify',
                                }
                    oldObject.with_context(thisContext).write(default)
                    default={
                             'name': oldObject.name,
                             'engineering_revision': newIndex,
                             'engineering_writable': True,
                             'state': 'draft',
                             'linkeddocuments': [(5)],  # Clean attached documents for new revision object
                             }
    
                    # Creates a new "old revision" object
                    tmpID = oldObject.with_context(thisContext).copy(default)
                    if tmpID:
                        wf_message_post(self, [oldObject.id], body='Created : New Revision.')
                        newID = tmpID.id
                        tmpID.write({'name': oldObject.name, })
                        note={
                                'type': 'revision process',
                                'reason': "Created new revision '{index}' for product '{name}'.".format(index=newIndex,name=oldObject.name),
                             }
                        self._insertlog(newID, note=note)
                        oldObject.with_context(thisContext)._copy_productBom(newID, ["normal","spbom"])
                        tmpID.with_context(thisContext).write( {'name': oldObject.name, } )
                        note={
                                'type': 'revision process',
                                'reason': "Copied BoM to new revision '{index}' for product '{name}'.".format(index=newIndex,name=oldObject.name),
                             }
                        self._insertlog(newID, note=note)
            break
        return (newID, newIndex)

    @api.model
    def CheckProductsToSave(self, request="", default=None):
        """
            Checks if given products has to be saved. 
        """
        listedParts = []
        retValues = {}
        
        for part in unpackDictionary(request):
            part=getCleanBytesDictionary(part)
            hasSaved = True
            existingID=False
            if not('engineering_code' in part):
                continue
            if part['engineering_code'] in listedParts:
                continue

            if ('engineering_code' in part) and ('engineering_revision' in part):
                existingIDs = self.search([
                      ('engineering_code', '=', part['engineering_code'])
                    , ('engineering_revision', '=', part['engineering_revision'])])
            elif ('engineering_code' in part) and not('engineering_revision' in part):
                existingIDs = self.search([
                    ('engineering_code', '=', part['engineering_code']) ]
                    , order='engineering_revision')
            if existingIDs:
                ids=sorted(existingIDs.ids)
                existingID = ids[len(ids) - 1]
            if existingID:
                hasSaved = False
                objPart = self.browse(existingID)
                part['engineering_revision']=objPart.engineering_revision
                if ('_lastupdate' in part) and part['_lastupdate']:
                    if (getUpdTime(objPart) < datetime.strptime(part['_lastupdate'], '%Y-%m-%d %H:%M:%S')):
                        if self._iswritable(objPart):
                            hasSaved = True

            retValues[part['engineering_code']]={
                        'componentID':existingID,
                        'hasSaved':hasSaved}                                                                                              
            listedParts.append(part['engineering_code'])
        return packDictionary(retValues)

    
    @api.model
    def SaveOrUpdate(self, request=[], default=None):
        """
            Saves or Updates Parts
        """
        listedParts = []
        retValues = {}
        modelFields=self.env['plm.config.settings'].GetFieldsModel(self._name)
        
        for part in unpackDictionary(request):
            part=getCleanBytesDictionary(part)
            hasSaved = False
            existingID=False
            
            if not ('engineering_code' in part) or (not 'engineering_revision' in part):
                part['componentID'] = False
                part['hasSaved'] = hasSaved
                continue

            if not ('name' in part) and (('engineering_code' in part) and part['engineering_code']):
                part['name'] = part['engineering_code'] 
 
            if part['engineering_code'] in listedParts:
                continue

            if not('componentID' in part) or not(part['componentID']):
                if ('engineering_code' in part) and ('engineering_revision' in part):
                    existingIDs = self.search([
                          ('engineering_code', '=', part['engineering_code'])
                        , ('engineering_revision', '=', part['engineering_revision'])])
                elif ('engineering_code' in part) and not('engineering_revision' in part):
                    existingIDs = self.search([
                        ('engineering_code', '=', part['engineering_code']) ]
                        , order='engineering_revision')
                if existingIDs:
                    ids=sorted(existingIDs.ids)
                    existingID = ids[len(ids) - 1]
            else:
                existingID=part['componentID']
 
            lastupdate=datetime.strptime(str(part['_lastupdate']),'%Y-%m-%d %H:%M:%S') if ('_lastupdate' in part) else datetime.now()
            for fieldName in list(set(part.keys()).difference(set(modelFields))):
                del (part[fieldName])
            if not existingID:
                logging.debug("[SaveOrUpdate] Part {name} is creating.".format(name=part['engineering_code']))
                objectItem=self.with_context({'internal_writing':True}).create(part)
                if objectItem:
                    existingID=objectItem.id
                    hasSaved = True
            else:
                objPart = self.browse(existingID)
                if objPart:
                    part['name'] = objPart.name
                    part['engineering_revision']=objPart.engineering_revision
                    if (getUpdTime(objPart) < lastupdate):
                        if self._iswritable(objPart):
                            logging.debug("[SaveOrUpdate] Part {name}/{revi} is updating.".format(name=part['engineering_code'],revi=part['engineering_revision']))
                            hasSaved = True
                            if not objPart.with_context({'internal_writing':False}).write(part):
                                logging.error("[SaveOrUpdate] Part {name}/{revi} cannot be updated.".format(name=part['engineering_code'],revi=part['engineering_revision']))
                                hasSaved = False
                else:
                    logging.error("[SaveOrUpdate] Part {name}/{revi} doesn't exist anymore.".format(name=part['engineering_code'],revi=part['engineering_revision']))

            retValues[part['engineering_code']]={
                        'componentID':existingID,
                        'hasSaved':hasSaved}                                                                                              
            listedParts.append(part['engineering_code'])
        return packDictionary(retValues)

    @api.model
    def QueryLast(self, request=([], []), default=None):
        """
            Queries to return values based on columns selected.
        """
        objId = False
        expData = []
        
        queryFilter, columns = request
        if len(columns) < 1:
            return expData
        if 'engineering_revision' in queryFilter:
            del queryFilter['engineering_revision']
        allIDs = self.search(queryFilter, order='engineering_revision')
        if len(allIDs) > 0:
            objId = allIDs[len(allIDs) - 1]
        if objId:
            tmpData = objId.export_data(columns)
            if 'datas' in tmpData:
                expData = tmpData['datas']
        return expData

    ##  Menu action Methods
    def _create_normalBom(self, idd):
        """
            Creates a new Normal Bom (recursive on all EBom children)
        """
        default = {}
        
        if idd in self.processedIds:
            return False
        checkObj=self.browse(idd)
        if not checkObj:
            return False
        bomType = self.env['mrp.bom']
        objBoms = bomType.search([('product_tmpl_id', '=', checkObj.product_tmpl_id.id), ('type', '=', 'normal'), ('active', '=', True)])
        idBoms = bomType.search([('product_tmpl_id', '=', checkObj.product_tmpl_id.id), ('type', '=', 'ebom'), ('active', '=', True)])

        if not objBoms:
            if idBoms:
                default={'product_tmpl_id': idBoms[0].product_tmpl_id.id,
                         'type': 'normal', 'active': True, }
                if idBoms[0].product_id:
                    default.update({'product_id': idBoms[0].product_id.id})
                self.processedIds.append(idd)
                newidBom = idBoms[0].with_context({'internal_writing':True}).copy(default)
                if newidBom:
                    newidBom.with_context({'internal_writing':True}).write(default)
                    ok_rows = self._summarizeBom(newidBom.bom_line_ids)
                    for bom_line in list(set(newidBom.bom_line_ids) ^ set(ok_rows)):
                        bom_line.unlink()
                    for bom_line in ok_rows:
                        bom_line.with_context({'internal_writing':True}).write(
                                    {  'type': 'normal', 'source_id': False, 
                                       'product_qty': bom_line.product_qty, } )
                        self._create_normalBom(bom_line.product_id.id)
        else:
            for bom_line in bomType.browse(objBoms[0].id).bom_line_ids:
                self._create_normalBom(bom_line.product_id.id)
        return False

    def _copy_productBom(self, idStart, idDest=None, bomTypes=["normal"]):
        """
            Creates a new 'bomType' BoM (arrested at first level BoM children).
        """
        default = {}
        if not idDest:
            idDest=idStart
        
        checkObjDest = self.browse(idDest)
        if checkObjDest:
            objBomType = self.env['mrp.bom']
            for bomType in bomTypes:
                objBoms = objBomType.search([('product_id', '=', idDest), ('type', '=', bomType), ('active', '=', True)])
                idBoms = objBomType.search([('product_id', '=', idStart), ('type', '=', bomType), ('active', '=', True)])
                if not objBoms:
                    for oldObj in idBoms:
                        newidBom = oldObj.with_context({'internal_writing':True}).copy(default)
                        if newidBom:
                            newidBom.with_context({'internal_writing':True}).write( 
                                            {'name': checkObjDest.name, 
                                             'product_tmpl_id': checkObjDest.product_tmpl_id.id, 
                                             'type': bomType, 'active': True, })
                            ok_rows = self._summarizeBom(newidBom.bom_line_ids)
                            for bom_line in list(set(newidBom.bom_line_ids) ^ set(ok_rows)):
                                bom_line.unlink()
                            for bom_line in ok_rows:
                                bom_line.with_context({'internal_writing':True}).write(
                                               {'type': bomType, 'source_id': False, 
                                                'name': bom_line.product_id.name,
                                                'product_qty': bom_line.product_qty, })
        return False

    def _summarizeBom(self, datarows):
        dic = {}
        for datarow in datarows:
            key = datarow.product_id.name
            if key in dic:
                dic[key].product_qty = float(dic[key].product_qty) + float(datarow.product_qty)
            else:
                dic[key] = datarow
        retd = dic.values()
        return retd

    ##  Work Flow Internal Methods
    def _get_recursive_parts(self, ids, excludeStatuses, includeStatuses, release=False):
        """
           Gets all ids related to current one as children
        """
        stopFlag = False
        tobeReleasedIDs = getListIDs(ids)
        options=self.env['plm.config.settings'].GetOptions()
        children = []
        for oic in self.browse(ids):
            children = self.browse(self._getChildrenBom(oic, 1))
            for child in children:
                if ((not child.state in excludeStatuses) and (not child.state in includeStatuses)) \
                        and (release and not(options.get('opt_obsoletedinbom', False))):
                    logging.warning("Part (%r - %d) is in a status '%s' not allowed."
                                    %(child.engineering_code, child.engineering_revision, child.state))
                    stopFlag = True
                    continue
                if child.state in includeStatuses:
                    if not child.id in tobeReleasedIDs:
                        tobeReleasedIDs.append(child.id)
        return (stopFlag, getCleanList(tobeReleasedIDs))

    def action_create_normalBom_WF(self, ids):
        """
            Creates a new Normal Bom if doesn't exist (action callable from code)
        """
        
        for idd in ids:
            self.processedIds = []
            self._create_normalBom(idd)
        wf_message_post(self, ids, body='Created Normal Bom.')
        return False

    def _action_ondocuments(self, ids, action, status):
        """
            Moves workflow on documents having the same state of component 
        """
        docIDs = []
#         documents=[]
        documentType = self.env['plm.document']
        check=self._context.get('no_move_documents', False)
        if not check:
            for oldObject in self.browse(ids):
                for document in oldObject.linkeddocuments:
                    if (document.id not in docIDs):
                        if documentType.ischecked_in(document.id):
                            docIDs.append(document.id)
            idMoves=move_workflow(documentType, docIDs, action, status)
            documentType.logging_workflow(idMoves, action, status)
        return docIDs

    def _iswritable(self, oid):
        checkState = ('draft')
        if not oid.engineering_writable:
            logging.warning(
                "_iswritable : Part (%r - %d) is not writable." % (oid.engineering_code, oid.engineering_revision))
            return False
        if not oid.state in checkState:
            logging.warning("_iswritable : Part (%r - %d) is in status %r." % (oid.engineering_code, oid.engineering_revision, oid.state))
            return False
        if oid.engineering_code == False:
            logging.warning(
                "_iswritable : Part (%r - %d) is without Engineering P/N." % (oid.name, oid.engineering_revision))
            return False
        return True

    @api.model
    def ActionUpload(self, request=[], default=None):
        """
            Action to be executed after automatic upload
        """
        signal='upload'
        move_workflow(self, self._ids, signal)
        return False

    
    def action_upload(self):
        """
            Action to be executed for Uploaded state
        """
        
        status = 'uploaded'
        action = 'upload'
        ids=self._ids
        operationParams = {
                            'status': status,
                            'statusName': _('Uploaded'),
                            'action': action,
                            'docaction': 'uploaddoc',
                            'excludeStatuses': ['uploaded', 'confirmed', 'transmitted','released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['draft'],
                            }
        default = {
                   'state': status,
                   'engineering_writable': False,
                   }
        self.logging_workflow(ids, action, status)
        return self._action_to_perform(ids, operationParams, default)

    
    def action_draft(self):
        """
            Action to be executed for Draft state
        """
        status = 'draft'
        action = 'draft'
        ids=self._ids
        operationParams = {
                            'status': status,
                            'statusName': _('Draft'),
                            'action': action,
                            'docaction': 'draft',
                            'excludeStatuses': ['draft', 'released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['confirmed', 'uploaded', 'transmitted'],
                            }
        default = {
                   'state': status,
                   'engineering_writable': True,
                   }
        self.logging_workflow(ids, action, status)
        return self._action_to_perform(ids, operationParams, default)

    
    def action_confirm(self):
        """
            Action to be executed for Confirmed state
        """
        
        status = 'confirmed'
        action = 'confirm'
        ids=self._ids
        operationParams = {
                            'status': status,
                            'statusName': _('Confirmed'),
                            'action': action,
                            'docaction': 'confirm',
                            'excludeStatuses': ['confirmed', 'transmitted', 'released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['draft'],
                            }
        default = {
                   'state': status,
                   'engineering_writable': False,
                   }
        self.logging_workflow(ids, action, status)
        return self._action_to_perform(ids, operationParams, default)

    
    def action_correct(self):
        """
            Action to be executed for Draft state (signal "correct")
        """
        
        status='draft'
        action = 'correct'
        ids=self._ids
        operationParams = {
                            'status': status,
                            'statusName': _('Draft'),
                            'action': action,
                            'docaction': 'correct',
                            'excludeStatuses': ['draft', 'transmitted', 'released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['confirmed'],
                            }
        default = {
                   'state': status,
                   'engineering_writable': True,
                   }
        self.logging_workflow(ids, action, status)
        return self._action_to_perform(ids, operationParams, default)

    
    def action_release(self):
        excludeStatuses = ['released', 'undermodify', 'obsoleted']
        includeStatuses = ['confirmed']
        return self._action_to_release(self._ids, excludeStatuses, includeStatuses)

    
    def action_obsolete(self):
        """
            Action to be executed for Obsoleted state
        """
        ids=self._ids
        status = 'obsoleted'
        action = 'obsolete'
        operationParams = {
                            'status': status,
                            'statusName': _('Obsoleted'),
                            'action': action,
                            'docaction': 'obsolete',
                            'excludeStatuses': ['draft', 'confirmed', 'transmitted', 'obsoleted'],
                            'includeStatuses': ['undermodify', 'released'],
                            }
        default={
                'engineering_writable': False,
                'state': status,
                }
        return self._action_to_perform(ids, operationParams, default)

    
    def action_reactivate(self):
        """
            action to be executed for Released state (signal "reactivate")
        """
        
        status = 'released'
        action = 'reactivate'
        ids=self._ids
        operationParams = {
                            'status': status,
                            'statusName': _('Released'),
                            'action': action,
                            'docaction': 'reactivate',
                            'excludeStatuses': ['draft', 'confirmed', 'transmitted', 'released'],
                            'includeStatuses': ['undermodify', 'obsoleted'],
                            }
        default={
                'engineering_writable': False,
                'state': status,
                }
        return self._action_to_perform(ids, operationParams, default)

    def logging_workflow(self, ids, action, status):
        note={
                'type': 'workflow movement',
                'reason': "Applying workflow action '{action}', moving to status '{status}.".format(action=action, status=status),
             }
        self._insertlog(ids, note=note)

    def _action_to_perform(self, ids, operationParams , default={}):
        """
            Executes on cascade to children products the required workflow operations.
        """
        full_ids=[]
        status=operationParams['status'] 
        action=operationParams['action']
        docaction=operationParams['docaction']
        excludeStatuses=operationParams['excludeStatuses']
        includeStatuses=operationParams['includeStatuses']
        
        stopFlag,allIDs=self._get_recursive_parts(ids, excludeStatuses, includeStatuses)
        self._action_ondocuments(allIDs,docaction, status)
        if action:
            idMoves=move_workflow(self, allIDs, action, status)
            self.logging_workflow(idMoves, action, status)
            objId=self.browse(allIDs).with_context({'internal_writing':True}).write(default)
            if objId:
                wf_message_post(self, allIDs, body='Status moved to: {status}.'.format(status=status))
        return objId

    def _action_to_release(self, ids, excludeStatuses, includeStatuses):
        """
             Action to be executed for Released state
        """
        full_ids = []
        last_ids=[]
        status='released'
        action='release'
        default={
                'engineering_writable': False,
                'state': status
                }
        
        stopFlag, allIDs = self._get_recursive_parts(ids, excludeStatuses, includeStatuses, release=True)
        if len(allIDs) < 1 or stopFlag:
            raise UserError(_("WorkFlow Error.\n\nOne or more parts cannot be released."))
        allProdObjs = self.browse(allIDs)
        for oldObject in allProdObjs:
            objObsolete=self._getbyrevision(oldObject.engineering_code, oldObject.engineering_revision - 1)
            if objObsolete and objObsolete.id:
                last_ids.append(objObsolete.id)
        
        idMoves=move_workflow(self, last_ids, 'obsolete', 'obsoleted')
        self.logging_workflow(idMoves, 'obsolete', 'obsoleted')
        self._action_ondocuments(last_ids, 'obsolete', 'obsoleted')

        self._action_ondocuments(allIDs, action, status)
        for currId in allProdObjs:
            if not (currId.id in ids):
                full_ids.append(currId.id)

        idMoves=move_workflow(self, allIDs, action, status)
        self.logging_workflow(idMoves, action, status)
        objId=self.browse(idMoves).with_context({'internal_writing':True}).write(default)
        if objId and idMoves:
            wf_message_post(self, allIDs, body='Status moved to: {status}.'.format(status=status))
        return objId

    #######################################################################################################################################33

    #   Overridden methods for this entity

    @api.model
    def create(self, vals):
        ret=False
        if vals and vals.get('name', False):
            existingIDs = self.search([('name', '=', vals['name'])],
                                      order='engineering_revision')
            if (vals.get('engineering_code', False)==False) or (vals['engineering_code'] == ''):
                vals['engineering_code'] = vals['name']
            if (vals.get('engineering_revision', False)==False):
                vals['engineering_revision'] = 0

            if existingIDs:
                existingID = existingIDs[len(existingIDs) - 1]
                if ('engineering_revision' in vals):
                    existObj = existingID
                    if existObj:
                        if (vals['engineering_revision'] > existObj.engineering_revision):
                            vals['name'] = existObj.name
                        else:
                            return existingID
                else:
                    return existingID

            try:
                objectItem=super(plm_component, self).create(vals)
                if objectItem:
                    ret=objectItem                  # Returns the objectItem instead the id to be coherent
                    values={
                            'name': vals['name'],
                            'revision': vals['engineering_revision'],
                            'type': self._name,
                            'op_type': 'creation',
                            'op_note': 'Create new entity on database',
                            'op_date': datetime.now(),
                            'userid': self._uid,
                            }
                    self.env['plm.logging'].create(values)
            except Exception as ex:
                raise Exception(" (%r). It has tried to create with values : (%r)." % (ex, vals))
        return ret

    
    def write(self, vals):
        ret=True
        if vals:
            check=self._context.get('internal_writing', False)
            thisprocess=self._context.get('internal_process', False)    # Avoids messages during internal processes.
            if not check:
                for prodItem in self.browse(self._ids):
                    if not isDraft(self,prodItem.id):
                        if not thisprocess:
                            logging.error("The entity '{name}-{rev}' is in a status that does not allow you to make save action".format(name=prodItem.name,rev=prodItem.engineering_revision))
                        ret=False
                        break
                    if not prodItem.engineering_writable:
                        if not thisprocess:
                            logging.error("The entity '{name}-{rev}' cannot be written.".format(name=prodItem.name,rev=prodItem.engineering_revision))
                        ret=False
                        break
            if ret:
                self._insertlog(self._ids, changes=vals)
                ret=super(plm_component, self).write(vals)
        return ret
     
    
    def copy(self, default={}):
        newID=False
        override=False
        previous_name=False
        oid=self.id
        
        if not self._context.get('new_revision', False):
            previous_name = self.browse(oid).name
            new_name=default.get('name', 'Copy of %s'%previous_name)
            if 'name' in default:
                tmpIds = self.search([('name', 'like', new_name)])
                if len(tmpIds) > 0:
                    new_name = '%s (%s)' % (new_name, len(tmpIds) + 1)
                default.update({
                    'name': new_name,
                    'engineering_code': new_name,
                    'engineering_revision': 0,
                })
                override=True
    
            default.update({
                'state': 'draft',
                'engineering_writable': True,
                'write_date': None,
                'linkeddocuments': []
            })
    
            note={
                    'type': 'copy object',
                    'reason': "Previous name was '{old} new one is '{new}'.".format(old=previous_name,new=new_name),
                 }
            self._insertlog(oid, note=note)

            tmpID=super(plm_component, self.browse(oid).with_context({'internal_writing':True})).copy(default)
            if tmpID!=None:
                newID=tmpID
                if override:
                    values={
                        'name': new_name,
                        'engineering_code': new_name,
                        'engineering_revision': 0,
                        }
                    newID.write(values)
        else:
            tmpID=super(plm_component, self.browse(oid).with_context({'internal_writing':True})).copy(default)
            if tmpID:
                newID=tmpID
                newID.with_context({'internal_writing':True}).write(default) 
        if newID and previous_name:
            wf_message_post(self, getListIDs(newID), body='Copied starting from : {value}.'.format(value=previous_name))
        return newID

    
    def unlink(self):
        ret=False
        ids=self._ids
        
        values = {'state': 'released', }
        isAdmin = isAdministrator(self)

        if not self.env['mrp.bom'].IsChild(ids):
            for checkObj in self.browse(ids):
                checkApply=False
                if isReleased(self, checkObj.id):
                    if isAdmin:
                        checkApply=True
                elif isDraft(self, checkObj.id):
                    checkApply=True

                if not checkApply:
                    continue            # Apply unlink only if have respected rules.
    
                existingIDs = self.with_context({'no_move_documents':True}).search([
                                    ('engineering_code', '=', checkObj.engineering_code),
                                    ('engineering_revision', '=', checkObj.engineering_revision - 1)])
                if len(existingIDs) > 0:
                    obsoletedIds=[]
                    undermodifyIds=[]
                    for existID in getListIDs(existingIDs):
                        if isObsoleted(self, existID.id):
                            obsoletedIds.append(existID.id)
                        elif isUnderModify(self, existID.id):
                            undermodifyIds.append(existID.id)
                    move_workflow (self, obsoletedIds, 'reactivate', 'released')
                    if undermodifyIds:
                        move_workflow (self, undermodifyIds, 'reactivate', 'released')

                note={
                        'type': 'unlink object',
                        'reason': "Removed entity from database.",
                     }
                self._insertlog(checkObj.id, note=note)
                item = super(plm_component, checkObj.with_context({'no_move_documents':False})).unlink()
                if item:
                    ret=ret | item
        return ret

# Overridden methods for this entity
