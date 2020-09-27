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

import logging
from datetime import datetime

from openerp.osv import fields, orm
from openerp.tools.translate import _

from .common import getListIDs, getCleanList, packDictionary, unpackDictionary, getCleanBytesDictionary, \
                    signal_workflow, get_signal_workflow, move_workflow, wf_message_post, \
                    isAdministrator, isObsoleted, isUnderModify, isAnyReleased, isReleased, isDraft, getUpdTime


# USED_STATES=[('draft','Draft'),('confirmed','Confirmed'),('released','Released'),('undermodify','UnderModify'),('obsoleted','Obsoleted')]
# STATEFORRELEASE=['confirmed']
# STATESRELEASABLE=['confirmed','transmitted','released','undermodify','obsoleted']

class plm_component(orm.Model):
    _name = 'product.product'
    _inherit = 'product.product'
    _columns = {
        'create_date': fields.datetime('Date Created', readonly=True),
        'write_date': fields.datetime('Date Modified', readonly=True),
    }

    @property
    def _default_rev(self):
        field = self.pool['product.template']._fields.get('engineering_revision', None)
        default = field.default('product.template') if not(field == None) else 0
        return default

    #   Internal methods
    def _insertlog(self, cr, uid, ids, changes={}, note={}, context=None):
        newID=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        op_type, op_note=["unknown",""]
        for objID in self.browse(cr, uid, getListIDs(ids), context=context):
            if note:
                op_type="{type}".format(type=note['type'])
                op_note="{reason}".format(reason=note['reason'])
            elif changes:
                op_type='change value'
                op_note=self.pool['plm.logging'].getchanges(cr, uid, objID, changes, context=context)
            if op_note:
                values={
                        'name': objID.name,
                        'revision': "{major}".format(major=objID.engineering_revision),
                        'type': self._name,
                        'op_type': op_type,
                        'op_note': op_note,
                        'op_date': datetime.now(),
                        'userid': uid,
                        }
                newID=self.pool['plm.logging'].create(cr, uid, values, context=context)
        return newID

    def _getbyrevision(self, cr, uid, name, revision, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        return self.search(cr, uid, [('engineering_code', '=', name), ('engineering_revision', '=', revision)], context=context)

#     def _getExplodedBom(self, cr, uid, ids, level=0, currlevel=0, context=None):
#         """
#             Returns a flat list of all children in a Bom ( level = 0 one level only, level = 1 all levels)
#         """
#         result = []
#         context = context or self.pool['res.users'].context_get(cr, uid)
#         if level == 0 and currlevel > 1:
#             return result
#         components = self.browse(cr, uid, ids)
#         relType = self.pool['mrp.bom']
#         for component in components:
#             for bomid in component.bom_ids:
#                 children = relType.GetExplodedBom(cr, uid, [bomid.id], level, currlevel)
#                 result.extend(children)
#         return result

    def _getChildrenBom(self, cr, uid, component, level=0, currlevel=0, context=None):
        """
            Returns a flat list of each child, listed once, in a Bom ( level = 0 one level only, level = 1 all levels)
        """
        result = []
        bufferdata = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        if level == 0 and currlevel > 1:
            return bufferdata
        for bomid in component.product_tmpl_id.bom_ids:
            for bomline in bomid.bom_line_ids:
                children=self._getChildrenBom(cr, uid, bomline.product_id, level, currlevel+1, context=context)
                bufferdata.extend(children)
                bufferdata.append(bomline.product_id.id)
        result.extend(bufferdata)
        return getCleanList(result)

    def RegMessage(self, cr, uid, request, default=None, context=None):
        """
            Registers a message for requested component
        """
        oid, message = request
        wf_message_post(self, cr, uid, [oid], body=message, context=context)
        return False

    def getLastTime(self, cr, uid, oid, default=None, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        return getUpdTime(self.browse(cr, uid, oid, context=context))

    def getUserName(self, cr, uid, context=None):
        """
            Gets the user name
        """
        userType = self.pool['res.users']
        context = context or self.pool['res.users'].context_get(cr, uid)
        uiUser = userType.browse(cr, uid, uid, context=context)
        return uiUser.name

    def getFromTemplateID(self, cr, uid, oid, context=None):
        ret=False
        if oid:
            context = context or self.pool['res.users'].context_get(cr, uid)
            ids = self.search(cr, uid, [('product_tmpl_id', '=', oid)], context=context)
            for prodItem in self.browse(cr, uid, getListIDs(ids), context=context):
                ret=prodItem
                break
        return ret

    def getTemplateItem(self, cr, uid, oid, context=None):
        ret=False
        if oid:
            context = context or self.pool['res.users'].context_get(cr, uid)
            for prodItem in self.browse(cr, uid, getListIDs(oid), context=context):
                ret=prodItem.product_tmpl_id
                break
        return ret

    ##  Customized Automations
    def on_change_name(self, cr, uid, oid, name=False, engineering_code=False, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        if name:
            results = self.search(cr, uid, [('name', '=', name)], context=context)
            if len(results) > 0:
                raise orm.except_orm(_('Update Part Warning'), _(
                    "Part %s already exists.\nClose with OK to reuse, with Cancel to discharge." % (name)))
            if not engineering_code:
                return {'value': {'engineering_code': name}}
        return {}

    ##  External methods
    @api.model
    def CleanStructure(self, request=[]):
        """
            Cleans relations having sourceID (in mrp.bom.line)
        """
        ret=False
        type = "ebom"
        bomLType = self.pool['mrp.bom.line']
        bomType = self.pool['mrp.bom']
        bl_to_delete = bomLType
        for parentID, sourceID in request:
            if not parentID==None:
                if isWritable(self, parentID):
                    for bom_id in bomType.search([('type','=',type),('product_id','=',parentID)]):
                        if not sourceID==None:
                            for bomLine in bomLType.search([('source_id','=',sourceID),('bom_id','=',bom_id.id)]):
                                bl_to_delete |= bomLine
                            bl_to_delete.unlink()                       # Cleans mrp.bom.lines
                        if not bom_id.bom_line_ids:
                            bom_id.unlink()                             # Cleans void mrp.bom
                    ret = True
        return ret                          

    def Clone(self, cr, uid, ids, default=None, context=None):
        """
            Creates a new copy of the component
        """
        default = {}
        exitValues = {}            
        context = context or self.pool['res.users'].context_get(cr, uid)
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            note={
                    'type': 'clone object',
                    'reason': "Creating new cloned entity starting from '{old}'.".format(old=tmpObject.name),
                 }
            self._insertlog(cr, uid, tmpObject.id, note=note, context=context)
            newID = self.copy(cr, uid, tmpObject.id, default, context=context)
            if newID:
                newEnt = self.browse(cr, uid, newID, context=context)
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

    def CloneVirtual(self, cr, uid, ids, default=None, context=None):
        """
            Creates a "false" new copy of the component.
            Really returns only new values avoiding creation of new object.
        """
        exitValues = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            new_name = "Copy of {name}".format(name=tmpObject.name)
            exitValues = {
                          '_id': False,
                          'name': new_name,
                          'engineering_code': new_name,
                          'description': "{desc}".format(desc=tmpObject.description),
                          'engineering_revision': self._default_rev,
                          'engineering_writable': True,
                          'state': 'draft',
                          }
            break
        return packDictionary(exitValues)

    def GetUpdated(self, cr, uid, vals, context=None):
        """
            Gets Last/Requested revision of given items (by name, revision, update time)
        """
        partData, attribNames = vals
        context = context or self.pool['res.users'].context_get(cr, uid)
        ids = self.GetLatestIds(cr, uid, partData, context=context)
        return packDictionary(self.read(cr, uid, getCleanList(ids), attribNames, context=context))

    def GetStdPartName(self, cr, uid, vals, context=None):
        """
            Gets new P/N reading from entity chosen (taking it from new index on sequence).
        """
        ret=""
        entID, entityName = vals
        if entID and entityName:
            context = context or self.pool['res.users'].context_get(cr, uid)
            userType=self.pool.get(entityName)
            if not(userType==None):
                for objID in userType.browse(cr,uid, getListIDs(entID), context=context):
                    ret=self.GetNewPNfromSeq(cr, uid, objID.sequence_id, context=context)
                    break
        return ret

    def GetNewPNfromSeq(self, cr, uid, seqID=None, context=None):
        """
            Gets new P/N from sequence (checks for P/N existence).
        """
        ret=""
        if seqID:
            context = context or self.pool['res.users'].context_get(cr, uid)
            count=0
            while ret=="":
                chkname=self.pool['ir.sequence']._next(cr, uid, [seqID.id], context=context)
                count+=1
                criteria=[('name', '=', chkname)]
                partIds = self.search(cr, uid, criteria, context=context)
                if (partIds==None) or (len(partIds)==0):
                    ret=chkname
                if count>1000:
                    logging.error("GetNewPNfromSeq : Unable to get a new P/N from sequence '{name}'."\
                                  .format(name=seqID.name))
                    break
        return ret

    def GetLatestIds(self, cr, uid, vals, context=None):
        """
            Gets Last/Requested revision of given items (by name, revision, update time)
        """
        ids = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        for request in vals:
            partName, _, updateDate = request
            if updateDate:
                criteria=[('engineering_code', '=', partName), ('write_date', '>', updateDate)]
            else:
                criteria=[('engineering_code', '=', partName)]
    
            partIds = self.search(cr, uid, criteria, order='engineering_revision', context=context)
            if len(partIds) > 0:
                partIds.sort()
                ids.append(partIds[len(partIds) - 1])
        return getCleanList(ids)

    def GetId(self, cr, uid, request, context=None):
        """
            Gets Last/Requested revision of given items (by name, revision, update time)
        """
        idd = False
        context = context or self.pool['res.users'].context_get(cr, uid)
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

        partIds = self.search(cr, uid, criteria, order='engineering_revision', context=context)
        if len(partIds) > 0:
            partIds.sort()
            idd=partIds[len(partIds) - 1]
        return idd

    def IsSaveable(self, cr, uid, ids, context=None):
        """
            Answers about capability to save requested product
        """
        ret=True
        context = context or self.pool['res.users'].context_get(cr, uid)
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            ret=ret and self._iswritable(cr, uid, tmpObject.id)
        return ret

    def IsRevisable(self, cr, uid, ids, context=None):
        """
            Gets if a product is revisable or not.
        """
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            if isAnyReleased(self, cr, uid, tmpObject.id, context=context):
                ret=True
                break
        return ret

    def NewRevision(self, cr, uid, ids, context=None):
        """
            Creates a new revision of current product
        """
        newID, newIndex = [ False, 0 ]
        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing': True, 'new_revision':True})
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            latestIDs = self.GetLatestIds(cr, uid,
                                          [(tmpObject.engineering_code, tmpObject.engineering_revision, False)],
                                          context=context)
            for oldObject in self.browse(cr, uid, latestIDs, context=context):
                if isAnyReleased(self, cr, uid, oldObject.id, context=context):
                    note={
                            'type': 'revision process',
                            'reason': "Creating new revision for '{old}'.".format(old=oldObject.name),
                         }
                    self._insertlog(cr, uid, oldObject.id, note=note, context=context)
                    newIndex = int(oldObject.engineering_revision) + 1
                    productsignal=get_signal_workflow(self, cr, uid, oldObject, 'undermodify', context=context)
                    move_workflow(self, cr, uid, [oldObject.id], productsignal, 'undermodify')
                    default={
                             'name': oldObject.name,
                             'engineering_revision': newIndex,
                             'engineering_writable': True,
                             'state': 'draft',
                             'linkeddocuments': [(5)],  # Clean attached documents for new revision object
                             }
    
                    # Creates a new "old revision" object
                    tmpID = self.copy(cr, uid, oldObject.id, default, context=context)
                    if tmpID:
                        wf_message_post(self, cr, uid, [oldObject.id], body='Created : New Revision.', context=context)
                        newID = tmpID
                        self.write(cr, uid, newID, default, context=context)
                        note={
                                'type': 'revision process',
                                'reason': "Created new revision '{index}' for product '{name}'.".format(index=newIndex,name=oldObject.name),
                             }
                        self._insertlog(cr, uid, tmpID, note=note, context=context)
                        self._copy_productBom(cr, uid, oldObject.id, newID, ["normal","spbom"], context=context)
                        self.write(cr, uid, newID, default, context=context)
                        note={
                                'type': 'revision process',
                                'reason': "Copied BoM to new revision '{index}' for product '{name}'.".format(index=newIndex,name=oldObject.name),
                             }
                        self._insertlog(cr, uid, tmpID, note=note, context=context)
            break
        return (newID, newIndex)

    def CheckProductsToSave(self, cr, uid, request, default=None, context=None):
        """
            Checks if given products has to be saved. 
        """
        listedParts = []
        retValues = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        for part in unpackDictionary(request):
            part=getCleanBytesDictionary(part)
            hasSaved = True
            existingID=False
            order = None
            if not('engineering_code' in part):
                continue
            if part['engineering_code'] in listedParts:
                continue

            if ('engineering_code' in part) and ('engineering_revision' in part):
                criteria = [
                      ('engineering_code', '=', part['engineering_code']),
                      ('engineering_revision', '=', part['engineering_revision'])
                    ]
            elif ('engineering_code' in part) and not('engineering_revision' in part):
                    criteria = [
                        ('engineering_code', '=', part['engineering_code'])
                    ]
                    order='engineering_revision'
            existingIDs = self.search(cr, uid,  criteria, order=order, context=context)
            if existingIDs:
                existingIDs.sort()
                existingID = existingIDs[len(existingIDs) - 1]
            if existingID:
                hasSaved = False
                objPart = self.browse(cr, uid, existingID, context=context)
                part['engineering_revision']=objPart.engineering_revision
                if ('_lastupdate' in part) and part['_lastupdate']:
                    if (getUpdTime(objPart) < datetime.strptime(part['_lastupdate'], '%Y-%m-%d %H:%M:%S')):
                        if self._iswritable(cr, uid, objPart):
                            hasSaved = True

            retValues[part['engineering_code']]={
                        'componentID':existingID,
                        'hasSaved':hasSaved}                                                                                              
            listedParts.append(part['engineering_code'])
        return packDictionary(retValues)

    
    def SaveOrUpdate(self, cr, uid, request, default=None, context=None):
        """
            Saves or Updates Parts
        """
        listedParts = []
        retValues = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        modelFields=self.pool['plm.config.settings'].GetFieldsModel(cr, uid,self._name, context=context)
        for part in unpackDictionary(request):
            context.update({'internal_writing': False})
            part=getCleanBytesDictionary(part)
            hasSaved = False
            existingID=False
            order=None
            
            if not ('engineering_code' in part) or (not 'engineering_revision' in part):
                part['componentID'] = False
                part['hasSaved'] = hasSaved
                continue

            if not ('name' in part) and (('engineering_code' in part) and part['engineering_code']):
                part['name'] = part['engineering_code'] 

            if (('name' in part) and not(part['name'])) and (('engineering_code' in part) and part['engineering_code']):
                part['name'] = part['engineering_code'] 
 
            if part['engineering_code'] in listedParts:
                continue

            if not('componentID' in part) or not(part['componentID']):
                if ('engineering_code' in part) and ('engineering_revision' in part):
                    criteria = [
                        ('engineering_code', '=', part['engineering_code']),
                        ('engineering_revision', '=', part['engineering_revision'])
                    ]
                elif ('engineering_code' in part) and not('engineering_revision' in part):
                    criteria = [
                        ('engineering_code', '=', part['engineering_code']) 
                    ]
                    order = 'engineering_revision'
                existingIDs = self.search(cr, uid, criteria, order=order, context=context)
                if existingIDs:
                    existingIDs.sort()
                    existingID = existingIDs[len(existingIDs) - 1].id
            else:
                existingID=part['componentID']
 
            lastupdate=datetime.strptime(str(part['_lastupdate']),'%Y-%m-%d %H:%M:%S') if ('_lastupdate' in part) else datetime.now()
            for fieldName in list(set(part.keys()).difference(set(modelFields))):
                del (part[fieldName])
            if not existingID:
                context.update({'internal_writing': True})
                logging.debug("[SaveOrUpdate] Part {name} is creating.".format(name=part['engineering_code']))
                tmpID = self.create(cr, uid, part, context=context)
                if tmpID!=None:
                    existingID=tmpID
                    hasSaved = True
            else:
                objPart = self.browse(cr, uid, existingID, context=context)
                if objPart:
                    part['name'] = objPart.name
                    part['engineering_revision']=objPart.engineering_revision
                    if (getUpdTime(objPart) < lastupdate):
                        if self._iswritable(cr, uid, objPart):
                            logging.debug("[SaveOrUpdate] Part {name}/{revi} is updating.".format(name=part['engineering_code'],revi=part['engineering_revision']))
                            hasSaved = True
                            if not self.write(cr, uid, [existingID], part, context=context):
                                logging.error("[SaveOrUpdate] Part {name}/{revi} cannot be updated.".format(name=part['engineering_code'],revi=part['engineering_revision']))
                                hasSaved = False
                else:
                    logging.error("[SaveOrUpdate] Part {name}/{revi} doesn't exist anymore.".format(name=part['engineering_code'],revi=part['engineering_revision']))

            retValues[part['engineering_code']]={
                        'componentID':existingID,
                        'hasSaved':hasSaved}                                                                                              
            listedParts.append(part['engineering_code'])
        return packDictionary(retValues)

    def QueryLast(self, cr, uid, request=([], []), default=None, context=None):
        """
            Queries to return values based on columns selected.
        """
        objId = False
        expData = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        queryFilter, columns = request
        if len(columns) < 1:
            return expData
        if 'engineering_revision' in queryFilter:
            del queryFilter['engineering_revision']
        allIDs = self.search(cr, uid, queryFilter, order='engineering_revision', context=context)
        if len(allIDs) > 0:
            allIDs.sort()
            objId = allIDs[len(allIDs) - 1]
        if objId:
            tmpData = self.export_data(cr, uid, [objId], columns)
            if 'datas' in tmpData:
                expData = tmpData['datas']
        return expData

    ##  Menu action Methods
    def _create_normalBom(self, cr, uid, idd, context=None):
        """
            Creates a new Normal Bom (recursive on all EBom children)
        """
        default = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        if idd in self.processedIds:
            return False
        checkObj=self.browse(cr, uid, idd, context=context)
        if not checkObj:
            return False
        bomType = self.pool['mrp.bom']
        bomLType=self.pool['mrp.bom.line']
        objBoms = bomType.search(cr, uid, [('product_tmpl_id', '=', checkObj.product_tmpl_id.id), ('type', '=', 'normal'), ('active', '=', True)], context=context)
        idBoms = bomType.search(cr, uid, [('product_tmpl_id', '=', checkObj.product_tmpl_id.id), ('type', '=', 'ebom'), ('active', '=', True)], context=context)

        if not objBoms:
            if idBoms:
                oldBomID=bomType.browse(cr, uid, idBoms[0], context=context)
                context.update({'internal_writing':True})
                default={'product_tmpl_id': oldBomID.product_tmpl_id.id,
                         'type': 'normal', 'active': True,
                         'name': oldBomID.product_tmpl_id.name}
                if oldBomID.product_id:
                    default.update({'product_id': oldBomID.product_id.id})
                self.processedIds.append(idd)
                newidBom = bomType.copy(cr, uid, idBoms[0], default, context=context)
                if newidBom:
                    default.update({'name':oldBomID.product_tmpl_id.name})
                    bomType.write(cr, uid, [newidBom], default, context=context)
                    oidBom = bomType.browse(cr, uid, newidBom, context=context)
                    ok_rows = self._summarizeBom(cr, uid, oidBom.bom_line_ids)
                    for bom_line in list(set(oidBom.bom_line_ids) ^ set(ok_rows)):
                        bomLType.unlink(cr, uid, [bom_line.id], context=context)
                    for bom_line in ok_rows:
                        bomLType.write(cr, uid, [bom_line.id],
                                      {'type': 'normal', 'source_id': False, 'product_qty': bom_line.product_qty, }, context=context)
                        self._create_normalBom(cr, uid, bom_line.product_id.id, context=context)
        else:
            for bom_line in bomType.browse(cr, uid, objBoms[0], context=context).bom_line_ids:
                self._create_normalBom(cr, uid, bom_line.product_id.id, context=context)
        return False

    def _copy_productBom(self, cr, uid, idStart, idDest=None, bomTypes=["normal"], context=None):
        """
            Creates a new 'bomType' BoM (arrested at first level BoM children).
        """
        default = {}
        if not idDest:
            idDest=idStart
        context = context or self.pool['res.users'].context_get(cr, uid)
        checkObjDest = self.browse(cr, uid, idDest, context=context)
        if checkObjDest:
            objBomType = self.pool['mrp.bom']
            bomLType=self.pool['mrp.bom.line']
            for bomType in bomTypes:
                objBoms = objBomType.search(cr, uid, [('product_id', '=', idDest), ('type', '=', bomType), ('active', '=', True)], context=context)
                idBoms = objBomType.search(cr, uid, [('product_id', '=', idStart), ('type', '=', bomType), ('active', '=', True)], context=context)
                if not objBoms:
                    context.update({'internal_writing':True})
                    for oldObj in objBomType.browse(cr, uid, getListIDs(idBoms), context=context):
                        newidBom = objBomType.copy(cr, uid, oldObj.id, default, context=context)
                        if newidBom:
                            objBomType.write(cr, uid, [newidBom],
                                          {'name': checkObjDest.name, 'product_tmpl_id': checkObjDest.product_tmpl_id.id, 'type': bomType, 'active': True, }, context=context)
                            oidBom = objBomType.browse(cr, uid, newidBom, context=context)
                            ok_rows = self._summarizeBom(cr, uid, oidBom.bom_line_ids)
                            for bom_line in list(set(oidBom.bom_line_ids) ^ set(ok_rows)):
                                bomLType.unlink(cr, uid, [bom_line.id], context=context)
                            for bom_line in ok_rows:
                                bomLType.write(cr, uid, [bom_line.id],
                                              {'type': bomType, 'source_id': False, 'name': bom_line.product_id.name,
                                               'product_qty': bom_line.product_qty, }, context=context)
        return False

    def _summarizeBom(self, cr, uid, datarows):
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
    def _get_recursive_parts(self, cr, uid, ids, excludeStatuses, includeStatuses, release=False, context=None):
        """
           Gets all ids related to current one as children
        """
        stopFlag = False
        tobeReleasedIDs = getListIDs(ids)
        context = context or self.pool['res.users'].context_get(cr, uid)
        options=self.pool['plm.config.settings'].GetOptions(cr,uid)
        children = []
        for oic in self.browse(cr, uid, ids, context=context):
            children = self.browse(cr, uid, self._getChildrenBom(cr, uid, oic, 1, context=context), context=context)
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

    def action_create_normalBom_WF(self, cr, uid, ids, context=None):
        """
            Creates a new Normal Bom if doesn't exist (action callable from code)
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        for idd in ids:
            self.processedIds = []
            self._create_normalBom(cr, uid, idd, context=context)
        wf_message_post(self, cr, uid, ids, body='Created Normal Bom.', context=context)
        return False

    def _action_ondocuments(self, cr, uid, ids, signal="", status="", context=None):
        """
            Moves workflow on documents having the same state of component 
        """
        ret=[]
        docIDs = []
        documents=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        check=context.get('no_move_documents', False)
        if not check:
            documentType = self.pool['plm.document']
            for oldObject in self.browse(cr, uid, ids, context=context):
                for document in oldObject.linkeddocuments:
                    if (document.id not in docIDs):
                        if documentType.ischecked_in(cr, uid, document.id, context=context):
                            docIDs.append(document.id)
                            documents.append(document)
            for document in documents:
                docsignal=get_signal_workflow(self, cr, uid, document, status, context=context)
                if docsignal:
                    move_workflow(documentType, cr, uid, [document.id], docsignal, status)
                    ret.append(document.id)
        return ret

    def _iswritable(self, cr, user, oid):
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

    def ActionUpload(self,cr,uid,ids,context=None):
        """
            Action to be executed after automatic upload
        """
        signal='upload'
        signal_workflow(self, cr, uid, ids, signal)
        return False

    def action_upload(self,cr,uid,ids,context=None):
        """
            Action to be executed for Uploaded state
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        status = 'uploaded'
        action = 'upload'
        operationParams = {
                            'status': status,
                            'statusName': _('Uploaded'),
                            'action': action,
                            'docaction': 'uploaddoc',
                            'excludeStatuses': ['uploaded', 'confirmed', 'transmitted','released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['draft'],
                            }
        default = {
                   'engineering_writable': False,
                   'state': status,
                   }
        context['internal_writing']=True
        self.logging_workflow(cr, uid, ids, action, status, context=context)
        return self._action_to_perform(cr, uid, ids, operationParams, default, context=context)

    def action_draft(self, cr, uid, ids, context=None):
        """
            Action to be executed for Draft state
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        status = 'draft'
        action = 'draft'
        operationParams = {
                            'status': status,
                            'statusName': _('Draft'),
                            'action': action,
                            'docaction': 'draft',
                            'excludeStatuses': ['draft', 'released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['confirmed', 'uploaded', 'transmitted'],
                            }
        default = {
                   'engineering_writable': True,
                   'state': status,
                   }
        context['internal_writing']=True
        self.logging_workflow(cr, uid, ids, action, status, context=context)
        return self._action_to_perform(cr, uid, ids, operationParams, default, context=context)

    def action_confirm(self, cr, uid, ids, context=None):
        """
            Action to be executed for Confirmed state
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        status = 'confirmed'
        action = 'confirm'
        operationParams = {
                            'status': status,
                            'statusName': _('Confirmed'),
                            'action': action,
                            'docaction': 'confirm',
                            'excludeStatuses': ['confirmed', 'transmitted', 'released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['draft'],
                            }
        default = {
                   'engineering_writable': False,
                   'state': status,
                   }
        context['internal_writing']=True
        self.logging_workflow(cr, uid, ids, action, status, context=context)
        return self._action_to_perform(cr, uid, ids, operationParams, default, context=context)

    def action_correct(self, cr, uid, ids, context=None):
        """
            Action to be executed for Draft state (signal "correct")
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        status='draft'
        action = 'correct'
        operationParams = {
                            'status': status,
                            'statusName': _('Draft'),
                            'action': action,
                            'docaction': 'correct',
                            'excludeStatuses': ['draft', 'transmitted', 'released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['confirmed'],
                            }
        default = {
                    'engineering_writable': True,
                    'state': status,
                    }
        context['internal_writing']=True
        self.logging_workflow(cr, uid, ids, action, status, context=context)
        return self._action_to_perform(cr, uid, ids, operationParams, default, context=context)

    def action_release(self, cr, uid, ids, context=None):
        excludeStatuses = ['released', 'undermodify', 'obsoleted']
        includeStatuses = ['confirmed']
        return self._action_to_release(cr, uid, ids, excludeStatuses, includeStatuses, context=context)

    def action_obsolete(self, cr, uid, ids, context=None):
        """
            Action to be executed for Obsoleted state
        """
        status = 'obsoleted'
        action = 'obsolete'

#         context = context or self.pool['res.users'].context_get(cr, uid)
#         context.update({'internal_writing':True})
# 
#         for oldObject in self.browse(cr, uid, ids, context=context):
#             move_workflow(self, cr, uid, oldObject.id, action, status)
        wf_message_post(self, cr, uid, ids, body='Status moved to: {status}.'.format(status=status), context=context)
        self._action_ondocuments(cr, uid, ids, action, status, context=context)
        return True

    def action_modify(self, cr, uid, ids, context=None):
        """
            action to be executed for UnderModify state (signal "modify")
        """
        status = 'undermodify'
        action = 'modify'
        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing':True})

        for oldObject in self.browse(cr, uid, ids, context=context):
            move_workflow(self, cr, uid, oldObject.id, action, status, context=context)
#        self._action_ondocuments(cr, uid, ids, action, status, context=context)
        return True

    def logging_workflow(self, cr, uid, ids, action, status, context=None):
        note={
                'type': 'workflow movement',
                'reason': "Applying workflow action '{action}', moving to status '{status}.".format(action=action, status=status),
             }
        self._insertlog(cr, uid, ids, note=note, context=context)

    def _action_to_perform(self, cr, uid, ids, operationParams , default={}, context=None):
        """
            Executes on cascade to children products the required workflow operations.
        """
        ret=False
        full_ids=[]
        status=operationParams['status'] 
        action=operationParams['action']
        docaction=operationParams['docaction']
        excludeStatuses=operationParams['excludeStatuses']
        includeStatuses=operationParams['includeStatuses']
        context.update({'internal_writing':True})
        stopFlag,allIDs=self._get_recursive_parts(cr, uid, ids, excludeStatuses, includeStatuses, context=context)
        self._action_ondocuments(cr, uid, allIDs, docaction, status, context=context)
        actIDs=list(set(allIDs)-set(ids))       # Force to obtain only related documents
        for currObj in self.browse(cr,uid,actIDs,context=context):
            productsignal=get_signal_workflow(self, cr, uid, currObj, status, context=context)
            move_workflow(self, cr, uid, [currObj.id], productsignal, status)
        ret=self.write(cr, uid, ids, default, context=context)
        self.logging_workflow(cr, uid, ids, action, status, context=context)
        if (ret):
            wf_message_post(self, cr, uid, ids, body=_('Status moved to: {status}.'.format(status=status)))
        return ret

    def _action_to_release(self, cr, uid, ids, excludeStatuses, includeStatuses, context=None):
        """
             Action to be executed for Released state
        """
        ret=False
        full_ids = []
        status='released'
        action='release'
        default={
                'state': status,
                'engineering_writable': False,
                }
        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing':True})
        stopFlag, allIDs = self._get_recursive_parts(cr, uid, ids, excludeStatuses, includeStatuses, release=True, context=context)
        if len(allIDs) < 1 or stopFlag:
            raise orm.except_orm(_('WorkFlow Error'), _("Part cannot be released."))
        allProdObjs = self.browse(cr, uid, allIDs, context=context)
        for oldObject in allProdObjs:
            last_ids = self._getbyrevision(cr, uid, oldObject.engineering_code, oldObject.engineering_revision - 1)
            if last_ids:
                for currObj in self.browse(cr, uid, last_ids, context=context):
                    productsignal=get_signal_workflow(self, cr, uid, currObj, 'obsoleted', context=context)
                    move_workflow(self, cr, uid, [currObj.id], productsignal, 'obsoleted')
        self._action_ondocuments(cr, uid, allIDs, action, status, context=context)
        actIDs=list(set(allIDs)-set(ids))       # Force to obtain only related documents
        for currObj in self.browse(cr,uid,actIDs,context=context):
            productsignal=get_signal_workflow(self, cr, uid, currObj, status, context=context)
            move_workflow(self, cr, uid, [currObj.id], productsignal, status)
        ret=self.write(cr, uid, ids, default, context=context)
        self.logging_workflow(cr, uid, ids, action, status, context=context)
        if (ret):
            wf_message_post(self, cr, uid, allIDs, body='Status moved to: {status}.'.format(status=status), context=context)
        return ret

    #######################################################################################################################################33

    #   Overridden methods for this entity

    def create(self, cr, uid, vals, context=None):
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        if vals and vals.get('name', False):
            existingIDs = self.search(cr, uid, [('name', '=', vals['name'])],
                                      order='engineering_revision',
                                      context=context)
            if (vals.get('engineering_code', False)==False) or (vals['engineering_code'] == ''):
                vals['engineering_code'] = vals['name']
            if (vals.get('engineering_revision', False)==False):
                vals['engineering_revision'] = self._default_rev

            if existingIDs:
                existingID = existingIDs[len(existingIDs) - 1]
                if ('engineering_revision' in vals):
                    existObj = self.browse(cr, uid, existingID, context=context)
                    if existObj:
                        if (vals['engineering_revision'] > existObj.engineering_revision):
                            vals['name'] = existObj.name
                        else:
                            return existingID
                else:
                    return existingID

            try:
                ret=super(plm_component, self).create(cr, uid, vals, context=context)
                values={
                        'name': vals['name'],
                        'revision': vals['engineering_revision'],
                        'type': self._name,
                        'op_type': 'creation',
                        'op_note': 'Create new entity on database',
                        'op_date': datetime.now(),
                        'userid': uid,
                        }
                self.pool['plm.logging'].create(cr, uid, values, context=context)
            except Exception as ex:
                raise Exception(" (%r). It has tried to create with values : (%r)." % (ex, vals))
        return ret

    def write(self, cr, uid, ids, vals, context=None):
        ret=True
        if vals:
            context = context or self.pool['res.users'].context_get(cr, uid)
            check=context.get('internal_writing', False)
            thisprocess=context.get('internal_process', False)
            if not check:
                for prodItem in self.browse(cr, uid, ids, context=context):
                    if not isDraft(self,cr, uid, prodItem.id, context=context):
                        if not thisprocess:
                            raise orm.except_orm(_('Edit Entity Error'),
                                             _("The entity '{name}-{rev}' is in a status that does not allow you to make save action".format(name=prodItem.name,rev=prodItem.engineering_revision)))
                        ret=False
                        break
                    if not prodItem.engineering_writable:
                        if not thisprocess:
                            raise orm.except_orm(_('Edit Entity Error'),
                                             _("The entity '{name}-{rev}' cannot be written.".format(name=prodItem.name,rev=prodItem.engineering_revision)))
                        ret=False
                        break
            if ret:
                self._insertlog(cr, uid, ids, changes=vals, context=context)
                ret=super(plm_component, self).write(cr, uid, ids, vals, context=context)
        return ret
    
    def copy(self, cr, uid, oid, default={}, context=None):
        newID=False
        override=False
        previous_name=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing':True})
        if not context.get('new_revision', False):
            previous_name = self.browse(cr, uid, oid, context=context).name
            new_name=default.get('name', 'Copy of %s'%previous_name)
            if 'name' in default:
                tmpIds = self.search(cr, uid, [('name', 'like', new_name)], context=context)
                if len(tmpIds) > 0:
                    new_name = '%s (%s)' % (new_name, len(tmpIds) + 1)
                default.update({
                    'name': new_name,
                    'engineering_code': new_name,
                    'engineering_revision': self._default_rev,
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
            self._insertlog(cr, uid, oid, note=note, context=context)

            tmpID=super(plm_component, self).copy(cr, uid, oid, default, context=context)
            if tmpID!=None:
                newID=tmpID
                if override:
                    values={
                        'name': new_name,
                        'engineering_code': new_name,
                        'engineering_revision': self._default_rev,
                        }
                    self.write(cr, uid, [newID], values, context=context)
        else:
            tmpID=super(plm_component, self).copy(cr, uid, oid, default, context=context)
            if tmpID:
                newID=tmpID
                self.write(cr, uid, [newID], default, context=context) 
        if newID and previous_name:
            wf_message_post(self, cr, uid, [newID], body='Copied starting from : {value}.'.format(value=previous_name), context=context)
        return newID

    def unlink(self, cr, uid, ids, context=None):
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        isAdmin = isAdministrator(self, cr, uid, context=context)

        if not self.pool['mrp.bom'].IsChild(cr, uid, ids, context=context):
            note={
                    'type': 'unlink object',
                    'reason': "Removed entity from database.",
                 }
            for checkObj in self.browse(cr, uid, ids, context=context):
                checkApply=False
                if isReleased(self, cr, uid, checkObj.id, context=context):
                    if isAdmin:
                        checkApply=True
                elif isDraft(self, cr, uid, checkObj.id, context=context):
                    checkApply=True

                if not checkApply:
                    continue            # Apply unlink only if have respected rules.
    
                existingIDs = self.search(cr, uid, [('engineering_code', '=', checkObj.engineering_code),
                                                       ('engineering_revision', '=', checkObj.engineering_revision - 1)], context=context)
                if len(existingIDs) > 0:
                    status='released'
                    context.update({'internal_writing':True, 'no_move_documents':True})
                    for product in self.browse(cr, uid, getListIDs(existingIDs), context=context):
                        productsignal=get_signal_workflow(self, cr, uid, product, status, context=context)
                        move_workflow(self, cr, uid, [product.id], productsignal, status)
                self._insertlog(cr, uid, checkObj.id, note=note, context=context)
                item=super(plm_component, self).unlink(cr, uid, [checkObj.id], context=context)
                if item:
                    ret=ret | item
        context.update({'no_move_documents':False})
        return ret


# Overridden methods for this entity
