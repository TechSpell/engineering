# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2020-2020 Didotech srl (<http://www.didotech.com>). All Rights Reserved
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

import random
import string
import base64
import logging
import os, stat
import time
from datetime import datetime

from odoo import models, fields, api, _, osv
from odoo.exceptions import UserError
from odoo.tools import config as tools_config

from .common import getListIDs, getCleanList, packDictionary, unpackDictionary, getCleanBytesDictionary, \
                        move_workflow, wf_message_post, isVoid, isAdministrator, isIntegratorUser, isReleased, \
                        isObsoleted, isUnderModify, isAnyReleased, isDraft, isWritable, getUpdTime

# To be adequated to plm.component class states
USED_STATES = [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('released', 'Released'), ('undermodify', 'UnderModify'),
               ('obsoleted', 'Obsoleted')]


# STATEFORRELEASE=['confirmed']
# STATESRELEASABLE=['confirmed','released','undermodify','UnderModify']

def random_name():
    random.seed()
    d = [random.choice(string.ascii_letters) for x in range(20)]
    return ("".join(d))

def create_directory(path):
    dir_name = random_name()
    path = os.path.join(path, dir_name)
    os.makedirs(path)
    return dir_name

def getFileName(fileName):
    return os.path.basename(fileName.replace('\\','/')).strip()

def getnewminor(minorString):
    if not minorString:
        minorString="A"
    else:
        count=0
        maxlen=index=len(minorString)-1
        while index >= 0:
            count=maxlen-index
            thisChar=ord(minorString[index])
            if thisChar==90:
                minorString=minorString[:(maxlen-count)]+chr(65)
                minorString="A{value}".format(value=minorString)
            else:
                minorString=minorString[:(maxlen-count)]+chr(thisChar+1)
            index=-1
    return minorString

def getprevminor(minorString):
    if not minorString:
        minorString="A"
    else:
        count=0
        maxlen=index=len(minorString)-1
        while index >= 0:
            count=maxlen-index
            thisChar=ord(minorString[index])
            if thisChar>65:
                minorString=minorString[:(maxlen-count)]+chr(thisChar-1)
            else:
                if ((maxlen-count)-1)>=0:
                    minorString=minorString[:(maxlen-count)-1]+chr(90)
            index=-1
    return minorString


class plm_document(models.Model):
    _name = 'plm.document'
    _description = 'Documents Revised'
    _table = 'plm_document'
    _inherit = ['mail.thread']

    @property
    def _default_rev(self):
        field = self.env['product.template']._fields.get('engineering_revision', None)
        default = field.default('product.template') if not(field == None) else 0
        return default

    def _insertlog(self, ids, changes={}, note={}):
        ret=False
        
        op_type, op_note=["unknown",""]
        for objID in self.browse(getListIDs(ids)):
            if note:
                op_type="{type}".format(type=note['type'])
                op_note="{reason}".format(reason=note['reason'])
            elif changes:
                op_type='change value'
                thischanges=dict(zip(changes.keys(),changes.values()))
                op_note=self.env['plm.logging'].getchanges(objID, thischanges)
            if op_note:
                values={
                        'name': objID.name,
                        'revision': "{major}-{minor}".format(major=objID.revisionid,minor=objID.minorrevision),
                        'file': objID.datas_fname,
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

    def _is_checkedout_for_me(self, oid):
        """
            Get if given document (or its latest revision) is checked-out for the requesting user
        """
        act = False
        
        checkType = self.env['plm.checkout']
        for lastDoc in self._getlastrev([oid]):
            for objectCheck in checkType.search([('documentid', '=', lastDoc)]):
                if objectCheck.userid.id== self._uid:
                    act = True
                    break
        return act

    def _getlastrev(self, ids):
        result = []
        for objDoc in self.browse(getCleanList(ids)):
            if objDoc and hasattr(objDoc, 'name'):
                docIds = self.search([('name', '=', objDoc.name),
                                      ('type', '=', 'binary')], order='revisionid, minorrevision' )
                result.append(docIds[len(docIds) - 1].id)
        return getCleanList(result)

    def _data_get_files(self, ids, listedFiles=([], []), forceFlag=False):
        """
            Get Files to return to Client as list: [ docID, nameFile, contentFile, writable, lastupdate ]
        """
        result = []
        
        datefiles, listfiles = listedFiles
        for objDoc in self.browse(ids):
            if objDoc.type == 'binary':
                timeDoc = getUpdTime(objDoc)
                timeSaved = time.mktime(timeDoc.timetuple())
                timeStamp=timeDoc.strftime('%Y-%m-%d %H:%M:%S')
                try:
                    isCheckedOutToMe = self._is_checkedout_for_me(objDoc.id)
                    if not (objDoc.datas_fname in listfiles):
                        if (not objDoc.store_fname) and (objDoc.db_datas):
                            value = objDoc.db_datas
                        else:
                            value = open(os.path.join(self._get_filestore(), objDoc.store_fname), 'rb').read()
                        result.append(
                            (objDoc.id, objDoc.datas_fname, base64.encodebytes(value), isCheckedOutToMe, timeStamp))
                    else:
                        if forceFlag:
                            isNewer = True
                        else:
                            timefile = time.mktime(
                                datetime.strptime(str(datefiles[listfiles.index(objDoc.datas_fname)]),
                                                  '%Y-%m-%d %H:%M:%S').timetuple())
                            isNewer = (timeSaved - timefile) > 5
                        if (isNewer and not (isCheckedOutToMe)):
                            if (not objDoc.store_fname) and (objDoc.db_datas):
                                value = objDoc.db_datas
                            else:
                                value = open(os.path.join(self._get_filestore(), objDoc.store_fname), 'rb').read()
                            result.append(
                                (objDoc.id, objDoc.datas_fname, base64.encodebytes(value), isCheckedOutToMe, timeStamp))
                        else:
                            result.append((objDoc.id, objDoc.datas_fname, False, isCheckedOutToMe, timeStamp))
                except Exception as ex:
                    logging.error("[_data_get_files] : Unable to access to document '{}'.".format(objDoc.name))
                    logging.error("Exception raised was : %r" %(ex))
                    result.append((objDoc.id, objDoc.datas_fname, False, True, self.GetServerTime().strftime('%Y-%m-%d %H:%M:%S')))
        return result

    @api.depends('store_fname', 'db_datas')
    def _data_get(self):
        result = {}
        value = False
        for objDoc in self:
            if objDoc.type == 'binary':
                if not objDoc.store_fname:
                    value = objDoc.db_datas
                    if not value or len(value) < 1:
                        raise UserError(_("Stored Document Error\nDocument '{}-{}' cannot be accessed.".format(objDoc.name,objDoc.revisionid)))
                else:
                    filestore = os.path.join(self._get_filestore(), objDoc.store_fname)
                    if os.path.exists(filestore):
                        value = open(filestore, 'rb').read()
                if value and len(value) > 0:
                    objDoc.datas = base64.encodebytes(value)
                    result[objDoc.id] = objDoc.datas
                else:
                    result[objDoc.id] = ''
        return result

    def _data_set(self):
        oid=self.id
        oiDocument=self
        value=oiDocument.datas
        if oiDocument.type == 'binary':
            if not value:
                filename = oiDocument.store_fname
                try:
                    os.unlink(os.path.join(self._get_filestore(), filename))
                except:
                    pass
                self.env.cr.execute('update plm_document set store_fname=NULL WHERE id=%s', (oid,))
                return True
            try:
                printout = False
                preview = False
                if oiDocument.printout:
                    printout = oiDocument.printout
                if oiDocument.preview:
                    preview = oiDocument.preview
                db_datas = b''  # Clean storage field.
                fname, filesize = self._manageFile(oid, binvalue=value)
                oiDocument.with_context({'internal_writing':True}).write({
                    'store_fname':fname, 
                    'file_size':filesize,
                    'db_datas':False
                    })
                self.env['plm.backupdoc'].with_context({'internal_writing':True}).create({
                    'userid': self._uid,
                    'existingfile': fname,
                    'documentid': oid,
                    'printout': printout,
                    'preview': preview
                    })

                return True
            except Exception as ex:
                logging.error("[_data_set] Error processing values.")
                logging.error("Exception raised was: %r" %(ex))
        else:
            return True

    def _explodedocs(self, oid, kinds, listed_documents=[], recursion=True):
        result = []
        if not(oid in listed_documents):
            
            documentRelation = self.env['plm.document.relation']
            for child in documentRelation.search([('parent_id', '=', oid), ('link_kind', 'in', kinds)]):
                if recursion:
                    listed_documents.append(oid)
                    result.extend(self._explodedocs(child.child_id.id, kinds, listed_documents, recursion))
                result.append(child.child_id.id)
        return result

    def _relateddocs(self, oid, kinds, listed_documents=[], recursion=True):
        """
            Returns fathers (recursively) of this document.
        """
        result = []
        if not (oid in listed_documents):
            
            documentRelation = self.env['plm.document.relation']
            docRelIds=documentRelation.GetFathers(oid, kinds)
            for fthID in docRelIds.keys():
                for father in documentRelation.browse(docRelIds[fthID]):
                    if recursion:
                        listed_documents.append(oid)
                        result.extend(self._relateddocs(father.parent_id.id, kinds, listed_documents, recursion))
                    if father.parent_id:
                        result.append(father.parent_id.id)
        return getCleanList(result)

    def _data_check_files(self, ids, listedFiles=([], []), forceFlag=False, otherFlag=False):
        result = []
        
        multiplyFactor = 1
        datefiles, listfiles = listedFiles
        for objDoc in self.browse(getCleanList(ids)):
            if objDoc.type == 'binary':
                timeDoc = getUpdTime(objDoc)
                timeSaved = time.mktime(timeDoc.timetuple())

                if not otherFlag:
                    isCheckedOutToMe = self._is_checkedout_for_me(objDoc.id)
                elif otherFlag == 1:
                    isCheckedOutToMe = False
                elif otherFlag == 2:
                    multiplyFactor = -1
                    isCheckedOutToMe = True
                    collectable = True
                    isNewer = True
                else:
                    isCheckedOutToMe = self._is_checkedout_for_me(objDoc.id)

                if otherFlag < 2:
                    if (objDoc.datas_fname in listfiles):
                        if forceFlag:
                            isNewer = True
                        else:
                            timefile = time.mktime(
                                datetime.strptime(str(datefiles[listfiles.index(objDoc.datas_fname)]),
                                                  '%Y-%m-%d %H:%M:%S').timetuple())
                            isNewer = (timeSaved - timefile) > 5
                        collectable = isNewer and not (isCheckedOutToMe)
                    else:
                        collectable = True

                objDatas = False
                file_size = 0
                localName=os.path.join(self._get_filestore(), objDoc.store_fname)
                if os.path.exists(localName):
                    statinfo = os.stat(localName)
                    file_size = objDoc.file_size if objDoc.file_size else statinfo.st_size
                else:
                    try:
                        objDatas = objDoc.datas
                        if (objDoc.file_size < 1) and (objDatas):
                            file_size = len(objDoc.datas)
                    except Exception as msg:
                        logging.warning('[_data_check_files] Document with "id":{idd}  and "name":{name} may contains no data!!'.format(idd=objDoc.id, name=objDoc.name))

                if file_size < 1:
                    collectable = False
                result.append((objDoc.id, objDoc.datas_fname, file_size, collectable * multiplyFactor, isCheckedOutToMe, timeDoc.strftime('%Y-%m-%d %H:%M:%S')))
        return getCleanList(result)

    def _manageFile(self, oid, binvalue=None):
        """
            use given 'binvalue' to save it on physical repository and to read size (in bytes).
        """
        
        path = self._get_filestore()
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except:
                raise UserError(_("Document Error\nPermission denied or directory '{}' cannot be created.".format(path)))
        flag = None
        # This can be improved
        for dirs in os.listdir(path):
            if os.path.isdir(os.path.join(path, dirs)) and len(os.listdir(os.path.join(path, dirs))) < 4000:
                flag = dirs
                break
        if binvalue == None:
            fileStream = self._data_get([oid], name=None, arg=None)
            binvalue = fileStream[list(fileStream.keys())[0]]

        flag = flag or create_directory(path)
        filename = random_name()
        fname = os.path.join(path, flag, filename)
        fobj = open(fname, 'wb')
        value = base64.b64decode(binvalue)
        fobj.write(value)
        fobj.close()
        return (os.path.join(flag, filename), len(value))

    @api.model
    def _iswritable(self):
        if self:
            checkState = ('draft')
            if not self.type == 'binary':
                logging.warning("_iswritable : Document (" + str(self.name) + "-" + str(
                    self.revisionid) + ") not writable as hyperlink.")
                return False
            if not self.writable:
                logging.warning("_iswritable : Document (" + str(self.name) + "-" + str(
                    self.revisionid) + ") not writable.")
                return False
            if not self.state in checkState:
                logging.warning("_iswritable : Document (" + str(self.name) + "-" + str(
                    self.revisionid) + ") in status ; " + str(self.state) + ".")
                return False
        return True

    @api.model
    def GetCheckDocumentName(self, request=[], default=None):
        """
            Gets current document name or a newer one from part name
        """
        ret= ""
        docName, partName, length=request
        if docName and partName and length:
            if self._getDocumentID({'name': docName}):  # Check existence,
                ret=self.GetNextDocumentName((partName, length))
            else:
                ret=docName
            return ret

    @api.model
    def GetNextDocumentName(self, request=[], default=None):
        """
            Gets new document name from a an initial part name
        """
        ret= ""
        partName, length=request
        if partName and length:
            count=len(self.search([('name', 'like', "{name}-".format(name=partName) + "_"*length )] ))
            while ret=="":
                chkname="{name}-%0{length}d".format(name=partName,length=length)%(count)
                count+=1
                docuIds = self.search([('name', '=', chkname)] )
                if (docuIds==None) or (len(docuIds)==0):
                    ret=chkname
                if count>1000:
                    logging.error("GetNextDocumentName : Unable to get a new P/N from sequence '{name}'."\
                                  .format(name=partName))
                    break
        return ret

    @api.model
    def CheckIn(self, ids=[], default=None):
        """
            Executes Check-In on requested document
        """
        objCheckOut=self.env['plm.checkout']
        for tmpObject in self.browse(getListIDs(ids)):
            for checkObj in objCheckOut.search([('documentid', '=', tmpObject.id)] ):
                checkObj.with_context({'internal_writing':True}).unlink()
        return True

    @api.model
    def CheckOut(self, request=[], default=None):
        """
            Executes Check-In on requested document
        """
        ret=False
        ids, hostName, pwsPath=request
        objCheckOut=self.env['plm.checkout']
        for tmpObject in self.browse(getListIDs(ids)):
            if objCheckOut.with_context({'internal_writing':True}).create({
                            'documentid':tmpObject.id, 'userid':self._uid, 'hostname':hostName, 'hostpws':pwsPath
                            }):
                ret=True
        return ret

    @api.model
    def CheckInRecursive(self, ids=[], default=None):
        """
             Executes recursive Check-In starting from requested document.
              Returns list of involved files.
       """
        ret=[]
        
        for idDoc,namefile,_,_,_,_ in self.checkAllFiles([getListIDs(ids),[[],[]],False]):
            if self.CheckIn(idDoc):
                ret.append(namefile)
        return getCleanList(ret)

    @api.model
    def CheckOutRecursive(self, request=[], default=None):
        """
             Executes recursive Check-Out starting from requested document.
              Returns list of involved files.
       """
        ret=[]
        
        ids, hostName, pwsPath=request
        for idDoc,namefile,_,_,_,_ in self.checkAllFiles([getListIDs(ids),[[],[]],False]):
            if self.CheckOut([idDoc, hostName, pwsPath]):
                ret.append(namefile)
        return getCleanList(ret)

    @api.model
    def IsSaveable(self, ids=[], default=None):
        """
            Answers about capability to save requested document
        """
        ret=True
        
        for tmpObject in self.browse(getListIDs(ids)):
            ret=ret and tmpObject._iswritable()
        return ret

    @api.model
    def IsRevisable(self, ids=[], default=None):
        """
            Answers about capability to create a new revision of current document
        """
        ret=False
        
        for tmpObject in self.browse(getListIDs(ids)):
            if isAnyReleased(self, tmpObject.id):
                ret=True
                break
        return ret

    @api.model
    def GetProductRelated(self, request=[], default=None):
        """
            Get Product related to this document
        """
        product_id=None
        ids, latest, editor, propNames=request
        prodType=self.env['product.product']
        for oldObject in self.browse(getListIDs(ids)):
            for linked_product_id in oldObject.linkedcomponents:
                if latest:
                    product_ids=prodType.GetLatestIds( [(linked_product_id.name, False, False)] )
                    if product_ids and len(product_ids)>0:
                        product_id=prodType.browse(product_ids[0])
                else:
                    product_id=linked_product_id
                break
        if product_id:
            newID=product_id.id
            newIndex=product_id.engineering_revision
            properties=self.env['plm.config.settings'].GetValuesByID((product_id, editor, propNames))
            ret=((newID, newIndex), properties)
        else:
            ret=[(False, False),packDictionary({})]

        return ret

    @api.model
    def NewRevision(self, request=[], default=None):
        """
            Creates a new revision of the document
        """
        newID = False
        newIndex = 0
        ids, hostName, pwsPath=request
        thisContext={ 'internal_writing':True, 'new_revision':True, }        
        for tmpObject in self.browse(getListIDs(ids)):
            latestIDs = self.GetLatestIds([(tmpObject.name, tmpObject.revisionid, False)] )
            for oldObject in self.browse(latestIDs):
                if isAnyReleased(self, oldObject.id):
                    note={
                            'type': 'revision process',
                            'reason': "Creating new revision for '{old}'.".format(old=oldObject.name),
                         }
                    self._insertlog(oldObject.id, note=note)
#                     docsignal=get_signal_workflow(oldObject, 'undermodify')
                    move_workflow(self, [oldObject.id], 'modify', 'undermodify')
                    newIndex=int(oldObject.revisionid) + 1
                    default = {
                                'name': oldObject.name,
                                'revisionid': newIndex,
                                'minorrevision':"A",
                                'writable': True,
                                'state': 'draft',
                                'linkedcomponents': [],  # Clean attached products for new revision object
                               }
                    tmpID = oldObject.with_context(thisContext).copy(default)
                    if tmpID!=None:
                        wf_message_post(self, [oldObject.id], body='Created : New Revision.')
                        newID = tmpID.id
                        note={
                                'type': 'revision process',
                                'reason': "Created new revision '{index}' for document '{name}'.".format(index=newIndex,name=oldObject.name),
                             }
                        self._insertlog(newID, note=note)
                        self.CheckOut([[newID], hostName, pwsPath])             # Take in Check-Out the new Document revision.
                        self._copy_DocumentBom(oldObject.id, newID)
                        self._cleanComponentLinks([(newID,False)])
                        tmpID.with_context(thisContext).write(default)
                        note={
                                'type': 'revision process',
                                'reason': "Copied Document Relations to new revision '{index}' for document '{name}'.".format(index=newIndex,name=oldObject.name),
                             }
                        self._insertlog(newID, note=note)
            break
        return (newID, newIndex)

    @api.model
    def NewMinorRevision(self, request=[], default=None):
        """
            create a new revision of the document
        """
        newID=False
        thisContext={ 'internal_writing':True, 'new_revision':True, }
        ids, hostName, pwsPath=request
        for tmpObject in self.browse(ids):
            latestIDs=self.GetLatestIds([(tmpObject.name,tmpObject.revisionid,False)] )
            for oldObject in self.browse(latestIDs):
                if isAnyReleased(self, oldObject.id):
                    note={
                            'type': 'minor revision process',
                            'reason': "Creating new revision for '{old}'.".format(old=oldObject.name),
                         }
                    self._insertlog(oldObject.id, note=note)
#                     docsignal=get_signal_workflow(oldObject, 'undermodify')
                    move_workflow(self, [oldObject.id], 'modify', 'undermodify')
                    newminor=getnewminor(oldObject.minorrevision)
                    default={
                            'name':oldObject.name,
                            'revisionid':int(oldObject.revisionid),
                            'minorrevision':newminor,
                            'datas':oldObject.datas,
                            'res_id':oldObject.id,
                            'writable':True,
                            'state':'draft',
                    }
                    tmpID=oldObject.with_context(thisContext).copy(default)
                    if tmpID!=None:
                        wf_message_post(self, [oldObject.id], body='Created : New Minor Revision.')
                        newID = tmpID.id
                        note={
                                'type': 'minor revision process',
                                'reason': "Created new minor revision '{index}' for '{old}'.".format(index=newminor,old=oldObject.name),
                             }
                        self._insertlog(newID, note=note)
                        self.CheckOut([[newID], hostName, pwsPath])             # Take in Check-Out the new Document revision.
                        self._copy_DocumentBom(oldObject.id, newID)
                        self._cleanComponentLinks([(newID,False)])
                        tmpID.with_context(thisContext).write(default)
            break
        return (newID, default['revisionid'], default['minorrevision']) 

    @api.model
    def Clone(self, request=[], default=None):
        """
             Creates a new copy of the document
       """
        exitValues = {}
        ids, hostName, pwsPath, default=request
        for tmpObject in self.browse(getListIDs(ids)):
            note={
                    'type': 'clone object',
                    'reason': "Creating new cloned entity starting from '{old}'.".format(old=tmpObject.name),
                 }
            self._insertlog(tmpObject.id, note=note)
            tmpID=tmpObject.with_context({'internal_writing':True}).copy(default)
            if tmpID!=None:
                newID = tmpID.id
                exitValues = {
                            '_id': newID,
                            'name': "Copy of {name}".format(name=tmpID.name),
                            'revisionid': self._default_rev,
                            'minorrevision':"A",
                            'writable': True,
                            'state': 'draft',
                            }
                wf_message_post(self, [newID], body="Cloned : starting from '{name}-{rev}'.".format(name=tmpID.name, rev=tmpID.revisionid))
                self.CheckOut([[newID], hostName, pwsPath])             # Take in Check-Out the new Document revision.
                break
        return packDictionary(exitValues)

    @api.model
    def CloneVirtual(self, ids=[], default={}):
        """
            Creates a false new copy of the document
        """
        exitValues = {}
        
        for tmpObject in self.browse(getListIDs(ids)):
            new_name = "Copy of {name}".format(name=tmpObject.name)
            exitValues['_id'] = False
            exitValues['name'] = new_name
            exitValues['revisionid'] = self._default_rev
            exitValues['writable'] = True
            exitValues['state'] = 'draft'
            exitValues['store_fname'] = ""
            exitValues['file_size'] = 0
            break
        return packDictionary(exitValues)

    def getDocumentID(self, document):
        """
            Gets ExistingID from document values.
        """
        existingID=False
        execution=False
 
        fullNamePath='full_file_name'
        if (fullNamePath in document) and document[fullNamePath]:
            execution=True
        else:
            fullNamePath='datas_fname'
            if (fullNamePath in document) and document[fullNamePath]:
                execution=True

        if execution:
            existingID = self._getDocumentID(document)
                    
        return existingID
 
    def _getDocumentID(self, document={}):
        """
            Gets ExistingID from document values.
        """
        existingID=False
        if document:
            order='revisionid, minorrevision'
            criteria=[]
            fullNamePath='full_file_name'
            if (fullNamePath in document) and document[fullNamePath]:
                criteria.append( ('datas_fname', '=', getFileName(document[fullNamePath])) )
            else:
                fullNamePath='datas_fname'
                if (fullNamePath in document) and document[fullNamePath]:
                    criteria.append( ('datas_fname', '=', getFileName(document[fullNamePath])) )
                                    
#               These statements can cover document already saved without document data
            if document['name']:
                criteria.append( ('name', '=', document['name']) )
                order='revisionid, minorrevision'

                if ('revisionid' in document) and int(document['revisionid'])>=0:
                    criteria.append( ('revisionid', '=', document['revisionid']) )
                    order='minorrevision'

                if ('minorrevision' in document) and document['minorrevision']:
                    criteria.append( ('minorrevision', '=', document['minorrevision']) )
                    order=None
            if criteria:
                existingIDs = self.search(criteria, order=order)
                if existingIDs:
                    ids=sorted(existingIDs.ids)
                    existingID = ids[len(ids) - 1]
        return existingID

    @api.model
    def CheckDocumentsToSave(self, documents="", default=None):
        """
            Save or Update Documents
        """
        retValues = {}
        
        listedDocuments=[]
        fullNamePath='full_file_name'
        for document in unpackDictionary(documents):
            document=getCleanBytesDictionary(document)
            hasSaved = True
            hasCheckedOut=True
            existingID=False

            if not (fullNamePath in document) or not document[fullNamePath]:
                continue

            if not ('name' in document):
#               These statements can cover document already saved without document data
                filename=getFileName(document[fullNamePath])
                document['name']=filename

            if document['name'] in listedDocuments:
                continue

            existingID=self.getDocumentID(document)

            if existingID:
                hasSaved = False
                hasCheckedOut=self._is_checkedout_for_me(existingID)
                if hasCheckedOut:
                    objDocument = self.browse(existingID)
                    if ('_lastupdate' in document) and document['_lastupdate']:
                        lastupdate=datetime.strptime(str(document['_lastupdate']),'%Y-%m-%d %H:%M:%S')
                        timedb=getUpdTime(objDocument)
                        logging.debug("CheckDocumentsToSave : time db : {timedb} time file : {timefile}".format(timedb=timedb.strftime('%Y-%m-%d %H:%M:%S'), timefile=document['_lastupdate']))
                        if objDocument._iswritable() and timedb < lastupdate:
                            hasSaved = True
                if ('CADComponentID' in document):
                    #TODO: To be inserted other references to manage the file as attached and no more.
                    if(document['CADComponentID'] in ['ROOTCFG',]):
                        hasSaved = True
                        hasCheckedOut = True                        # Managed as SolidEdge cfg files.

            retValues[getFileName(document[fullNamePath])]={
                        'hasCheckedOut':hasCheckedOut,
                        'documentID':existingID,
                        'hasSaved':hasSaved}                                                                                              
            listedDocuments.append(document['name'])
        return packDictionary(retValues)


    @api.model
    def SaveOrUpdate(self, request=[], default=None):
        """
            Save or Update Documents
        """
        retValues = {}
        listedDocuments=[]
        fullNamePath='datas_fname'
        documents, [hostName,pwsPath]=unpackDictionary(request)
        modelFields=self.env['plm.config.settings'].GetFieldsModel(self._name)
        for document in documents:
            document=getCleanBytesDictionary(document)
            hasSaved = False
            hasCheckedOut=False
            autocheckout=True
            existingID=False
           
            if not (fullNamePath in document) or not document[fullNamePath]:
                continue

            if not ('name' in document):
#               These statements can cover document already saved without document data
                filename=getFileName(document[fullNamePath])
                document['name']=filename
#               These statements can cover document already saved without document data
 
            if document['name'] in listedDocuments:
                continue

            if ('documentID' in document) and(int(document['documentID'])>0):
                existingID=document['documentID']

            if ('CADComponentID' in document):
                #TODO: To be inserted other references to manage the file as attached and no more.
                if(document['CADComponentID'] in ['ROOTCFG',]):
                    autocheckout=False                      # Managed as SolidEdge cfg files.

            lastupdate=datetime.strptime(str(document['_lastupdate']),'%Y-%m-%d %H:%M:%S') if ('_lastupdate' in document) else datetime.now()
            for fieldName in list(set(document.keys()).difference(set(modelFields))):
                del (document[fieldName])
            document['is_integration']=True
            document['public']=True
            if not existingID:
                logging.debug("[SaveOrUpdate] Document {name} is creating.".format(name=document['name']))
                objectItem=self.with_context({'internal_writing':True}).create(document)
                if objectItem:
                    existingID=objectItem.id
                    if autocheckout:
                        hasCheckedOut=self.CheckOut([existingID, hostName, pwsPath])
                    hasSaved = True
            else:
                if autocheckout:
                    hasCheckedOut=self._is_checkedout_for_me(existingID)
                else:
                    hasCheckedOut=True
                if hasCheckedOut:
                    objDocument = self.browse(existingID)
                    if objDocument:
                        document['revisionid']=objDocument.revisionid
                        document['minorrevision']=objDocument.minorrevision
                        if objDocument._iswritable() and (getUpdTime(objDocument) < lastupdate):
                            logging.debug("[SaveOrUpdate] Document {name}/{revi} is updating.".format(name=document['name'],revi=document['revisionid']))
                            hasSaved = True
                            if not objDocument.with_context({'internal_writing':False}).write(document):
                                logging.error("[SaveOrUpdate] Document {name}/{revi} cannot be updated.".format(name=document['name'],revi=document['revisionid']))
                                hasSaved = False
                    else:
                        logging.error("[SaveOrUpdate] Document {name}/{revi} doesn't exist anymore.".format(name=document['name'],revi=document['revisionid']))
                else:
                    userName=self.getUserSign(self._uid)
                    logging.error("[SaveOrUpdate] Document {name}/{revi} was not checked-out for {user}.".format(name=document['name'],revi=document['revisionid'],user=userName))
   
            retValues[getFileName(document[fullNamePath])]={
                        'hasCheckedOut':hasCheckedOut,
                        'documentID':existingID,
                        'hasSaved':hasSaved}                                                                                              
            listedDocuments.append(document['name'])
        return packDictionary(retValues)

    @api.model
    def RegMessage(self, request=[], default=None):
        """
            Registers a message for requested document
        """
        oid, message = request
        self.wf_message_post([oid], body=message)
        return False

    @api.model
    def CleanUp(self, request=[], default=None):
        """
            Remove faked documents
        """
        self.env.cr.execute("delete from plm_document where store_fname=NULL and type='binary'")
        return True

    @api.model
    def QueryLast(self, request=([], []), default=None):
        """
            Query to return values based on columns selected.
        """
        expData = []
        queryFilter, columns = request
        if len(columns) < 1:
            return expData
        if 'revisionid' in queryFilter:
            del queryFilter['revisionid']
        allIDs=self.search(queryFilter, order='revisionid')
        if len(allIDs) > 0:
            tmpData = allIDs.export_data(columns)
            if 'datas' in tmpData:
                expData = tmpData['datas']
        return expData

    @api.model
    def IsCheckedOutForMe(self, oid=None):
        """
            Get if given document (or its latest revision) is checked-out for the requesting user
        """
        return self._is_checkedout_for_me(oid)

    def _cleanComponentLinks(self, relations=[]):
        """
            Clean document component relations..
        """
        objType = self.env['plm.component.document.rel']
        objType.CleanStructure(relations=relations)

    def _copy_DocumentBom(self, idStart, idDest=None):
        """
            Create a new 'bomType' BoM (arrested at first level BoM children).
        """
        default = {}
        if not idDest:
            idDest=idStart
        
        checkObjDest = self.browse(idDest)
        if checkObjDest:
            objBomType = self.env['plm.document.relation']
            objBoms = objBomType.search([('parent_id', '=', idDest), ])
            idBoms = objBomType.search([('parent_id', '=', idStart), ])
            if not objBoms:
                for oldObj in idBoms:
                    default={
                             'parent_id': idDest,
                             'child_id': oldObj.child_id.id,
                             'link_kind': oldObj.link_kind,
                             'configuration': '',
                             }
                    objBomType.create(default)
        return False
                    
    def ischecked_in(self, ids):
        """
            Check if a document is checked-in 
        """
        
        checkoutType = self.env['plm.checkout']

        for document in self.browse(getListIDs(ids)):
            if checkoutType.search([('documentid', '=', document.id)]):
                logging.warning(
                    _("The document %s - %s has not checked-in" % (str(document.name), str(document.revisionid))))
                return False
        return True

    def logging_workflow(self, ids, action, status):
        note={
                'type': 'workflow movement',
                'reason': "Applying workflow action '{action}', moving to status '{status}.".format(action=action, status=status),
             }
        self._insertlog(ids, note=note)

    def _action_onrelateddocuments(self, ids, default={}, action="", status="", checkact=False):
        """
            Move workflow on documents related to given ones.
        """
        ret=False
        fthkindList = ['RfTree', 'LyTree']          # Get relation names due to fathers
        chnkindList = ['HiTree','RfTree', 'LyTree'] # Get relation names due to children
        
        allIDs=getCleanList(ids)
        relIDs = self.getRelatedDocs(ids, fthkindList, chnkindList)
        allIDs.extend(relIDs)                   # Force to obtain involved documents
        if allIDs:
            tmpIDs=[]
            for idd in allIDs:
                if checkact and not self.ischecked_in(idd):
                    continue
                tmpIDs.append(idd)
            idMoves=move_workflow(self, tmpIDs, action, status)
            self.logging_workflow(idMoves, action, status)
            wf_message_post(self, tmpIDs, body='Status moved to: {status}.'.format(status=status))
        return ret
 
    @api.model
    def ActionUpload(self, ids=[], default=None):
        """
            action to be executed after automatic upload
        """
        signal='uploaddoc'
        move_workflow(self, ids, signal,'upload')
        return False

    def action_upload(self):
        """
            action to be executed after automatic upload
        """
        options=self.env['plm.config.settings'].GetOptions()
        status='uploaded'
        action = 'upload'
        default = {
                    'engineering_writable': False,
                    'state': status,
                    }
        doc_default = {
                   'writable': False,
                   'state': status
                   }
        operationParams = {
                            'status': status,
                            'statusName': _('Uploaded'),
                            'action': action,
                            'docaction': 'uploaddoc',
                            'excludeStatuses': ['uploaded', 'confirmed', 'released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['draft'],
                            'default': default,
                            'doc_default': doc_default,
                            }
        
        if options.get('opt_showWFanalysis', False):
            return self.action_check_workflow(operationParams)
        else:
            ids=self._ids
            self.logging_workflow(ids, doc_default, action, status)
            return self.browse(ids).with_context({'internal_writing':True}).write(doc_default)

    def action_draft(self):
        """
            release the object
        """
        options=self.env['plm.config.settings'].GetOptions()
        status='draft'
        action = 'draft'
        default = {
                    'engineering_writable': True,
                    'state': status,
                    }
        doc_default = {
                   'writable': True,
                   'state': status
                   }
        operationParams = {
                            'status': status,
                            'statusName': _('Draft'),
                            'action': action,
                            'docaction': 'draft',
                            'excludeStatuses': ['draft', 'released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['confirmed', 'uploaded', 'transmitted'],
                            'default': default,
                            'doc_default': doc_default,
                            }
        if options.get('opt_showWFanalysis', False):
            return self.action_check_workflow(operationParams)
        else:
            return self._action_onrelateddocuments(self._ids, doc_default, action, status)

    def action_correct(self):
        """
            release the object
        """
        options=self.env['plm.config.settings'].GetOptions()
        status='draft'
        action = 'correct'
        default = {
                    'engineering_writable': True,
                    'state': status,
                    }
        doc_default = {
                   'writable': True,
                   'state': status
                   }
        operationParams = {
                            'status': status,
                            'statusName': _('Draft'),
                            'action': action,
                            'docaction': 'correct',
                            'excludeStatuses': ['draft', 'released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['confirmed', 'uploaded'],
                            'default': default,
                            'doc_default': doc_default,
                            }
        if options.get('opt_showWFanalysis', False):
            return self.action_check_workflow(operationParams)
        else:
            return self._action_onrelateddocuments(self._ids, doc_default, action, status)

    def action_confirm(self):
        """
            action to be executed for Draft state
        """
        ret=False
        options=self.env['plm.config.settings'].GetOptions()
        status='confirmed'
        action='confirm'
        default = {
                   'engineering_writable': False,
                   'state': status
                   }
        doc_default = {
                   'writable': False,
                   'state': status
                   }
        operationParams = {
                            'status': status,
                            'statusName': _('Confirmed'),
                            'action': action,
                            'docaction': 'confirm',
                            'excludeStatuses': ['confirmed', 'released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['draft'],
                            'default': default,
                            'doc_default': doc_default,
                            }
        if options.get('opt_showWFanalysis', False):
            ret = self.action_check_workflow(operationParams)
        else:
            ids=self._ids
            if self.ischecked_in(ids):
                ret = self._action_onrelateddocuments(ids, doc_default, action, status, checkact=True)
            else:
                move_workflow(self, ids, 'correct')
        return ret

    def action_release(self):
        """
            release the object
        """
        options=self.env['plm.config.settings'].GetOptions()
        status='released'
        action = 'release'
        default = {
                    'engineering_writable': False,
                    'state': status,
                    }
        doc_default = {
                   'writable': False,
                   'state': status
                   }
        operationParams = {
                            'status': status,
                            'statusName': _('Released'),
                            'action': action,
                            'docaction': 'release',
                            'excludeStatuses': ['released', 'undermodify', 'obsoleted'],
                            'includeStatuses': ['confirmed'],
                            'default': default,
                            'doc_default': doc_default,
                            }
        if options.get('opt_showWFanalysis', False):
            return self.action_check_workflow(operationParams)
        else:
            ids=self._ids
            for oldObject in self.browse(ids):
                for last_id in self._getbyaltminorevision(oldObject):
                    move_workflow(self, last_id.id, 'obsolete', 'obsoleted')
                for last_id in self._getbyrevision(oldObject.name, oldObject.revisionid - 1):
                    move_workflow(self, last_id.id, 'obsolete', 'obsoleted')
            return self._action_onrelateddocuments(ids, doc_default, action, status, checkact=True)

    def action_obsolete(self):
        """
            obsolete the object
        """
        options=self.env['plm.config.settings'].GetOptions()
        status='obsoleted'
        action = 'obsolete'
        default = {
                    'engineering_writable': False,
                    'state': status,
                    }
        doc_default = {
                   'writable': False,
                   'state': status
                   }
        operationParams = {
                            'status': status,
                            'statusName': _('Obsoleted'),
                            'action': action,
                            'docaction': 'obsolete',
                            'excludeStatuses': ['draft', 'confirmed', 'obsoleted'],
                            'includeStatuses': ['undermodify', 'released'],
                            'default': default,
                            'doc_default': doc_default,
                            }
        if options.get('opt_showWFanalysis', False):
            return self.action_check_workflow(operationParams)
        else:
            ids=self._ids
            self.logging_workflow(ids, action, status)
            wf_message_post(self, ids, body='Status moved to: {status}.'.format(status=status))
            return self.browse(ids).with_context({'internal_writing':True}).write(doc_default)

    def action_reactivate(self):
        """
            reactivate the object
        """
        options=self.env['plm.config.settings'].GetOptions()
        status='released'
        action = 'reactivate'
        default = {
                   'engineering_writable': False,
                   'state': status,
                   }
        doc_default = {
                   'writable': False,
                   'state': status
                   }
        operationParams = {
                            'status': status,
                            'statusName': _('Released'),
                            'action': action,
                            'docaction': 'reactivate',
                            'excludeStatuses': ['draft', 'confirmed', 'released'],
                            'includeStatuses': ['undermodify', 'obsoleted'],
                            'default': default,
                            'doc_default': doc_default,
                            }
        if options.get('opt_showWFanalysis', False):
            return self.action_check_workflow(operationParams)
        else:
            ids=self._ids
            self.logging_workflow(ids, action, status)
            return self.browse(ids).with_context({'internal_writing':True}).write(doc_default)

    def _get_filesize(self):
        for doc_id in self:
            doc_id.file_size_mb = float(doc_id.file_size) / (1024.0 * 1024.0)

    def _get_checkout_name(self):
        for doc_id in self:
            chechRes = self.getCheckedOut(doc_id.id, None)
            self.checkout_user = ''
            if chechRes:
                self.checkout_user = str(chechRes[2])
                
        
    def _is_checkout(self):
        for doc_id in self:
            chechRes = self.getCheckedOut(doc_id.id, None)
            self.is_checkout = False
            if chechRes:
                self.is_checkout = True
                
    
    #   Overridden methods for this entity
 
    def _get_filestore(self):
        dms_Root_Path = tools_config.get('document_path', os.path.join(tools_config['root_path'], 'filestore'))
        return os.path.join(dms_Root_Path, self.env.cr.dbname)

    def copy(self, default={}):
        newID = False
        previous_name=False
        oid=self.id
        
        # get All document relation
        documentRelation = self.env['plm.document.relation']
        if not self._context.get('new_revision', False):
            previous_name = self.browse(oid).name
            if not 'name' in default:
                new_name = 'Copy of %s' % previous_name
                lenny = self.search([('name', '=', new_name)], order='revisionid')
                if len(lenny) > 0:
                    new_name = '%s (%s)' % (new_name, len(lenny) + 1)
                default['name'] = new_name
            # manage copy of the file
            fname, filesize = self._manageFile(oid)
            # assign default value
            default['store_fname'] = fname
            default['file_size'] = filesize
            default['state'] = 'draft'
            default['writable'] = True
            note={
                'type': 'copy object',
                'reason': "Previous name was '{old} new one is '{new}'.".format(old=previous_name,new=new_name),
                 }
            self._insertlog(oid, note=note)

        tmpID = super(plm_document, self).copy(default)
        if tmpID!=None:
            newID = tmpID
            # create all the document relation
            for OldRel in documentRelation.search([('parent_id', '=', oid)]):
                documentRelation.create({
                    'parent_id': newID.id,
                    'child_id': OldRel.child_id.id,
                    'configuration': OldRel.configuration,
                    'link_kind': OldRel.link_kind,
                })
        if newID and previous_name:
            wf_message_post(self, [newID.id], body='Copied starting from : {value}.'.format(value=previous_name))
        return newID

    @api.model
    def create(self, vals=None):
        ret=False
        
        if vals and vals.get('name', False):
            existingID=self.getDocumentID(vals)
            if existingID:
                ret=self.browse(existingID)
            else:
                try:
                    status=vals.get('state','draft')
                    vals.update({'state': status})

                    minor=vals.get('minorrevision', None)
                    minor="A" if(isVoid(minor)) else minor
                    vals['minorrevision']=minor
                    major=vals.get('revisionid', None)
                    major=self._default_rev if(isVoid(major)) else major
                    vals['revisionid']=major
                    
                    objectItem=super(plm_document, self).create(vals)
                    if objectItem:
                        ret=objectItem                      # Returns the objectItem instead the id to be coherent
                        values={
                                'name': vals['name'],
                                'revision': "{major}-{minor}".format(major=major,minor=minor),
                                'file': vals['datas_fname'],
                                'type': self._name,
                                'op_type': 'creation',
                                'op_note': 'Create new entity on database',
                                'op_date': datetime.now(),
                                'userid': self._uid,
                                }
                        self.env['plm.logging'].create(values)
                except Exception as ex:
                    logging.error("Exception {msg}. It has tried to create with values : {vals}.".format(msg=ex, vals=vals))
        return ret

    def write(self, vals):
        ret=True
        if vals:
            ids=self._ids
            check=self._context.get('internal_writing', False)
            if not check:
                for docItem in self.browse(ids):
                    if not isDraft(self, docItem.id):
                        raise UserError(_("Edit Entity Error.\n\nThe entity '{name}-{rev}' is in a status that does not allow you to make save action.".format(name=docItem.name,rev=docItem.revisionid)))
                        ret=False
                        break
                    if not docItem.writable:
                        raise UserError(_("Edit Entity Error.\n\nThe entity '{name}-{rev}' cannot be written.".format(name=docItem.name,rev=docItem.revisionid)))
                        break
            if ret:
                self._insertlog(ids, changes=vals)
                ret=super(plm_document, self).write(vals)
        return ret

    def unlink(self):
        ret=False
        values = {'state': 'released', }
        ids=self._ids
        isAdmin = isAdministrator(self)

        if not self.env['plm.document.relation'].IsFather(ids):
            note={
                'type': 'unlink object',
                'reason': "Removed entity from database.",
             }
            for checkObj in self.browse(ids):
                checkApply=False
                if isReleased(self, checkObj.id):
                    if isAdmin:
                        checkApply=True
                elif isDraft(self, checkObj.id):
                    checkApply=True

                if not checkApply:
                    continue            # Apply unlink only if have respected rules.

                existingIDs = []
                for last_id in self._getprevminorevision(checkObj):
                    existingIDs.append(last_id.id)
                for last_id in self._getbyrevision(checkObj.name, checkObj.revisionid - 1):
                    existingIDs.append(last_id.id)

                if len(existingIDs) > 0:
                    obsoletedIds=[]
                    undermodifyIds=[]
                    for idd in existingIDs:
                        if isObsoleted(self, idd):
                            obsoletedIds.append(idd)
                        elif isUnderModify(self, idd):
                            undermodifyIds.append(idd)
                    if obsoletedIds:
                        move_workflow(self, obsoletedIds, 'reactivate', 'released')
                        wf_message_post(self, obsoletedIds, body='Removed : Latest Revision.')
                    if undermodifyIds:
                        move_workflow(self, undermodifyIds, 'reactivate', 'released')
                        wf_message_post(self, undermodifyIds, body='Removed : Latest Revision.')
                self._insertlog(checkObj.id, note=note)
                item = super(plm_document, checkObj).unlink()
                if item:
                    ret=ret | item
        return ret

    name = fields.Char('Name', required=True)
    description = fields.Text('Description')
    res_name = fields.Char('Resource Name')
    res_model = fields.Char('Resource Model', readonly=True, help="The database object this attachment will be attached to.")
    res_field = fields.Char('Resource Field', readonly=True)
    res_id = fields.Many2oneReference('Resource ID', model_field='res_model',
                                      readonly=True, help="The record id this is attached to.")
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
                                 default=lambda self: self.env.company)
    type = fields.Selection([('url', 'URL'), ('binary', 'File')],
                            string='Type', required=True, default='binary', change_default=True,
                            help="You can either upload a file from your computer or copy/paste an internet link to your file.")
    url = fields.Char('Url', index=True, size=1024)
    public = fields.Boolean('Is public document')
 
    # for external access
    access_token = fields.Char('Access Token')
 
    # the field 'datas' is computed and may use the other fields below
    db_datas = fields.Binary('Database Data', attachment=True)
    store_fname = fields.Char('Stored Filename')
    file_size = fields.Integer('File Size', readonly=True)
    file_size_mb = fields.Float('File Size [Mb]', readonly=True, compute=_get_filesize)
    checksum = fields.Char("Checksum/SHA1", size=40, index=True, readonly=True)
    mimetype = fields.Char('Mime Type', readonly=True)
    index_content = fields.Text('Indexed Content', readonly=True, prefetch=False)

    usedforspare    =   fields.Boolean  (string='Used for Spare',help="Drawings marked here will be used printing Spare Part Manual report.", default=False)
    usedformftg     =   fields.Boolean  (string='Used for Manufacturing',help="Drawings marked here will be used as skecthes for manufacturing on worksheets.", default=False)
    revisionid      =   fields.Integer  (string='Revision Index', required=True, default=0)
    minorrevision   =   fields.Char     (string='Minor Revision', required=True, default='A')
    writable        =   fields.Boolean  (string='Writable', default=True)
    datas           =   fields.Binary   (string='File Content', inverse='_data_set', compute='_data_get', attachment=True)
    printout        =   fields.Binary   (string='Printout Content', help="Print PDF content.", attachment=False)
    preview         =   fields.Binary   (string='Preview Content', help="Static preview.", attachment=False)
    state           =   fields.Selection(USED_STATES,string='Status', help="The status of the document.", readonly="True", default='draft')
    checkout_user   =   fields.Char(string="Checked-Out to", compute=_get_checkout_name)
    is_checkout     =   fields.Boolean(string='Is Checked-Out', compute=_is_checkout, store=False)
    is_integration  =   fields.Boolean(string="Is from integration", default=False)
    datas_fname     =   fields.Char('Filename', help="Stored filename.")

    _sql_constraints = [
        ('name_unique', 'unique (name,revisionid,minorrevision)', 'File name has to be unique!')
        # qui abbiamo la sicurezza dell'univocita del nome file
    ]

    @api.model
    def CheckedIn(self, files=[], default=None):
        """
            Get checked status for requested files
        """
        retValues = []
        

        def getcheckedfiles(files):
            res = []
            for fileName in files:
                ids = self.search([('datas_fname', '=', fileName)], order='revisionid')
                if len(ids) > 0:
                    res.append([fileName, not (self._is_checkedout_for_me(ids[len(ids) - 1].id))])
            return res

        if len(files) > 0:  # no files to process
            retValues = getcheckedfiles(files)
        return retValues

    @api.model
    def GetUpdated(self, vals=[], default=None):
        """
            Get Last/Requested revision of given items (by name, revision, update time)
        """
        docData, attribNames = vals
                
        ids = self.GetLatestIds(docData)
        return packDictionary(self.read(getCleanList(ids), attribNames))

    @api.model
    def GetStdDocuName(self, vals=[], default=None):
        """
            Gets new P/N reading from entity chosen (taking it from new index on sequence).
        """
        ret=""
        entID, objectName = vals
        if entID and objectName:
            userType=self.env[objectName] if (objectName in self.env) else None
            if not(userType==None):
                for objID in userType.browse(getListIDs(entID)):
                    ret=self.GetNewDNfromSeq(objID.sequence_id)
                    break
        return ret

    @api.model
    def GetNewDNfromSeq(self, seqID=None, default=None):
        """
            Gets new Document Number from sequence (checks for D/N existence).
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
                    logging.error("GetNewDNfromSeq : Unable to get a new document Number from sequence '{name}'."\
                                  .format(name=seqID.name))
                    break
        return ret

    @api.model
    def GetLatestIds(self, vals=[], default=None):
        """
            Get Last/Requested revision of given items (by name, revision, update time)
        """
        ids = []
        
        for request in vals:
            docName, _, updateDate = request
            if updateDate:
                criteria=[('name', '=', docName), ('write_date', '>', updateDate)]
            else:
                criteria=[('name', '=', docName)]
    
            docIds = self.search(criteria, order='revisionid,minorrevision')
            if len(docIds) > 0:
                ids.append(docIds[len(docIds) - 1].id)
        return getCleanList(ids)

    @api.model
    def CheckWholeSetFiles(self, request=[], default=None):
        """
            Evaluate documents to return
        """
        required,wholeset=[[],[]]
        
        if request:
            ids, listedFiles, selection = request
            if ids:
                required=self.checkAllFiles([ getListIDs(ids), listedFiles, selection ], default=None)
                wholeset=self.checkAllFiles([ getListIDs(ids), ([],[]), selection ],   default=None)
        return packDictionary([required,wholeset])
        
    @api.model
    def checkAllFiles(self, request, default=None):
        """
            Evaluate documents to return
        """
        outputData=[]
        execFlag = 2  # Used to force writable flag as mine
        forceFlag = False
        listed_models = []
        listed_documents = []
        ids, listedFiles, selection = request

        if selection == False:      # It's in CheckInRecursive / CheckOutRecursive
            selection = 1
            execFlag = 1            # Used to force writable flag to not mine
        if selection < 0:
            forceFlag = True
            selection = selection * (-1)

        for oid in ids:
            kind = 'LyTree'  # Get relations due to layout connected
            docArray = self._relateddocs(oid, [kind], listed_documents)
            kind = 'SdTree'  # Get relations due to service files connected
            othArray = self._explodedocs(oid, [kind], listed_documents)
    
            kind = 'HiTree'  # Get Hierarchical tree relations due to children
            modArray = self._explodedocs(oid, [kind], listed_models)
            for item in modArray:
                kind = 'LyTree'  # Get relations due to layout connected
                docArray.extend(self._relateddocs(item, [kind], listed_documents))
                kind = 'SdTree'  # Get relations due to service files connected
                othArray.extend(self._explodedocs(item, [kind], listed_documents))
                
            modArray.extend(docArray)
 
            docArray=getCleanList(modArray)
            
            if selection == 2:
                docArray = self._getlastrev(docArray)
    
            if not oid in docArray:
                docArray.append(oid)  # Add requested document to package
            outputData.extend(self._data_check_files(docArray, listedFiles, forceFlag))
            if othArray:
                outputData.extend(self._data_check_files(othArray, listedFiles, True, execFlag))
        return getCleanList(outputData)

    @api.model
    def GetSomeFiles(self, request=[], default=None):
        """
            Extract documents to be returned.
        """
        
        forceFlag = False
        ids, listedFiles, selection = request
        if selection == False:
            selection = 1

        if selection < 0:
            forceFlag = True
            selection = selection * (-1)

        if selection == 2:
            docArray = self._getlastrev(ids)
        else:
            docArray = ids
        return self._data_get_files(docArray, listedFiles, forceFlag)

    @api.model
    def GetAllFiles(self, request=[], default=None):
        """
            Extract documents to be returned 
        """
        
        forceFlag = False
        listed_models = []
        listed_documents = []
        modArray = []
        oid, listedFiles, selection = request
        if selection == False:
            selection = 1

        if selection < 0:
            forceFlag = True
            selection = selection * (-1)

        kind = 'HiTree'  # Get Hierarchical tree relations due to children
        docArray = self._explodedocs(oid, [kind], listed_models)

        if not oid in docArray:
            docArray.append(oid)  # Add requested document to package

        for item in docArray:
            kinds = ['LyTree', 'RfTree']  # Get relations due to layout connected
            modArray.extend(self._relateddocs(item, kinds, listed_documents))
            modArray.extend(self._explodedocs(item, kinds, listed_documents))
        #             kind='RfTree'               # Get relations due to referred connected
        #             modArray.extend(self._relateddocs(item, kind, listed_documents))
        #             modArray.extend(self._explodedocs(item, kind, listed_documents))

        modArray.extend(docArray)
        docArray = getCleanList(modArray)  # Get unique documents object IDs

        if selection == 2:
            docArray = self._getlastrev(docArray)

        if not oid in docArray:
            docArray.append(oid)  # Add requested document to package
        return self._data_get_files(docArray, listedFiles, forceFlag)

    def getRelatedDocs(self, ids, fthkindList=[], chnkindList=[]):
        """
            Extracts documents related to current one(s) (layouts, referred models, etc.)
        """
        result = []
        listed_documents = []
        
        for oid in ids:
            result.extend(self._relateddocs(oid, fthkindList, listed_documents, False))
            result.extend(self._explodedocs(oid, chnkindList, listed_documents, False))
        return (getCleanList(result))

    @api.model
    def GetRelatedDocs(self, ids=[], default=None):
        """
            Return document infos related to current one(s) (layouts, referred models, etc.)
        """
        result = []
        kindList = ['RfTree', 'LyTree']  # Get relations due to referred models
        
        read_docs = self.getRelatedDocs(ids, kindList, kindList)
        for document in self.browse(read_docs):
            result.append([document.id, document.name, document.preview])
        return result

    @api.model
    def GetServerTime(self, request=[], default=None):
        """
            calculate the server db time 
        """
        return datetime.now()

    def getUserSign(self, oid, default=None):
        """
            get the user name
        """
        uiUser = self.env['res.users'].browse(oid)
        return uiUser.name

    def _getbyrevision(self, name, revision):
        
        return self.search([('name', '=', name), ('revisionid', '=', revision)])

    def _getbyaltminorevision(self, docObject):
        
        return self.search([('name', '=', docObject.name), ('revisionid', '=', docObject.revisionid), ('minorrevision', '!=', docObject.minorrevision)])

    def _getprevminorevision(self, docObject):
        
        return self.search([('name', '=', docObject.name), ('revisionid', '=', docObject.revisionid), ('minorrevision', '=', getprevminor(docObject.minorrevision))])

    def getCheckedOut(self, oid, default=None):
        
        for objDoc in self.env['plm.checkout'].search([('documentid', '=', oid)]):
            return (objDoc.documentid.name, objDoc.documentid.revisionid, objDoc.userid.name,
                    objDoc.hostname)
        return False


class plm_checkout(models.Model):
    _name = 'plm.checkout'
    _description = 'Checked-Out Documents'
    
    userid      = fields.Many2one ('res.users',    string='Related User',     index=True, ondelete='cascade')
    hostname    = fields.Char     (                string='Hostname',         size=64)
    hostpws     = fields.Char     (                string='PWS Directory',    size=1024)
    documentid  = fields.Many2one ('plm.document', string='Related Document', index=True, ondelete='cascade')
    preview     = fields.Binary   (related="documentid.preview",string='Preview Content',store=False)

    _sql_constraints = [
        ('documentid', 'unique (documentid)', 'The documentid must be unique !')
    ]

    def _insertlog(self, ids, changes={}, note={}):
        ret=False
        op_type, op_note=["unknown",""]
        for objID in self.env['plm.document'].browse(getListIDs(ids)):
            if note:
                op_type="{type}".format(type=note['type'])
                op_note="{reason}".format(reason=note['reason'])
            if op_note:
                values={
                        'name': objID.name,
                        'revision': "{major}-{minor}".format(major=objID.revisionid,minor=objID.minorrevision),
                        'file': objID.datas_fname,
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

    def logging_operation(self, ids, operation):
        note={
                'type': 'CheckDoc',
                'reason': "Applying '{operation}' operation to document.".format(operation=operation),
             }
        self._insertlog(ids, note=note)

    def _adjustRelations(self, oids, userid=False):
        
        docRelType = self.env['plm.document.relation']
        if userid:
            ids = docRelType.search([('child_id', 'in', getListIDs(oids)), ('userid', '=', False)])
        else:
            ids = docRelType.search([('child_id', 'in', getListIDs(oids))])
        values = {'userid': userid, }
        for oid in ids:
            oid.write(values)

    #   Overridden methods for this entity

    def create(self, vals):
        ret=False
        docIDs=[]
        
        check=self._context.get('internal_writing', False)
        if check:
            if not self.search([('documentid', '=', vals['documentid'])]):
                documentType = self.env['plm.document']
                docObj = documentType.browse(vals['documentid'])
                if docObj.state=='draft':
                    values = {'writable': True, }
                    if not docObj.with_context({'internal_writing':True}).write(values):
                        logging.error("create : Unable to check-out the required document (" + str(docObj.name) + "-" + str(
                            docObj.revisionid) + ").")
                        return ret
                    self._adjustRelations(getListIDs(docObj.id), self._uid)
                    docIDs.append(docObj.id)
                    objectItem=super(plm_checkout, self).create(vals)
                    if objectItem:
                        ret=objectItem
                        self.logging_operation(docIDs, 'Check-Out')
                        wf_message_post(documentType, docIDs, body='Checked-Out')
        return ret

    def unlink(self):
        ret=False
        documentType = self.env['plm.document']
        ids=self._ids
        isAdmin=isAdministrator(self)
        chkIDs = []
        docIDs = []
        
        check=self._context.get('internal_writing', False)
        if not check:
            if not isAdmin and not isIntegratorUser(self):
                logging.error(
                    "[unlink] : Unable to Check-In the required document.\n You aren't authorized in this context.")
                raise UserError(_("Unable to Check-In the required document.\n\nYou aren't authorized in this context."))
        values = {'writable': False, }
        for checkObj in self.browse(getListIDs(ids)):
            if isAdmin or checkObj.userid.id==self._uid:
                chkIDs.append(checkObj.id)
                docIDs.append(checkObj.documentid.id)
                if not checkObj.documentid.with_context({'internal_writing':True}).write(values):
                    logging.error(
                        "[unlink] : Unable to check-in the document (" + str(checkObj.documentid.name) + "-" + str(
                            checkObj.documentid.revisionid) + ").\n You can't change writable flag.")
                    return False
        self._adjustRelations(docIDs, False)
        item_ids=self.browse(getListIDs(chkIDs))
        if item_ids:
            ret=super(plm_checkout, item_ids).unlink()
        if ret:
            wf_message_post(documentType,  docIDs, body='Checked-In')
            self.logging_operation(docIDs, 'Check-In')
        return ret


class plm_document_relation(models.Model):
    _name = 'plm.document.relation'
    _description = 'Document Relations'
    
    parent_id       =   fields.Many2one ('plm.document', string='Related parent document', index=True,   ondelete='cascade')
    child_id        =   fields.Many2one ('plm.document', string='Related child document',  index=True,   ondelete='cascade')
    configuration   =   fields.Char     (                string='Configuration Name',                    size=1024)
    link_kind       =   fields.Char     (                string='Kind of Link',                          size=64, required=True)
    create_date     =   fields.Datetime (                string='Date Created',                          readonly=True)
    userid          =   fields.Many2one ('res.users',    string='CheckOut User',           index=True,   readonly="True")
    
    _defaults = {
        'link_kind': lambda *a: 'HiTree',
        'userid': lambda *a: False,
    }
    _sql_constraints = [
        ('relation_uniq', 'unique (parent_id,child_id,link_kind)', _('The Document Relation must be unique !'))
    ]

    @api.model
    def CleanStructure(self, parent_ids=[], default=None):
        executed=[]
        oIds=self
        for parent_id in parent_ids:
            if isWritable(self.env['plm.document'], parent_id):
                criteria = [('parent_id', '=', parent_id)]
                if not(criteria in executed):
                    executed.append(criteria)
                    oIds|=self.search(criteria)
        oIds.unlink()
        return False

    @api.model
    def SaveStructure(self, relations=[], level=0, currlevel=0):
        """
            Save Document relations
        """
        ret=False
        savedItems = []

        def cleanStructure(relations):
            res = {}
            oIds=self
            for relation in relations:
                res['parent_id'], res['child_id'], res['configuration'], res['link_kind'] = relation
                if isWritable(self.env['plm.document'], res['parent_id']):
                    if (res['link_kind'] == 'LyTree') or (res['link_kind'] == 'RfTree'):
                        criteria = [('child_id', '=', res['child_id'])]
                    else:
                        criteria = [('parent_id', '=', res['parent_id'])]
                    oIds |= self.search(criteria)
            oIds.unlink()

        def saveChild(relation):
            """
                save the relation 
            """
            ret=False
            try:
                res = {}
                res['parent_id'], res['child_id'], res['configuration'], res['link_kind'] = relation
                if (res['parent_id'] != None) and (res['child_id'] != None):
                    if (len(str(res['parent_id'])) > 0) and (len(str(res['child_id'])) > 0):
                        if not ((res['parent_id'], res['child_id']) in savedItems):
                            if isWritable(self.env['plm.document'], res['parent_id']):
                                savedItems.append((res['parent_id'], res['child_id']))
                                self.create(res)
                else:
                    logging.error(
                        "saveChild : Unable to create a relation between documents. One of documents involved doesn't exist. Arguments(" + str(
                            relation) + ") ")
                    ret=True
            except Exception as ex:
                logging.error(
                    "saveChild : Unable to create a relation. Arguments (%s) Exception (%s)" % (str(relation), str(ex)))
                ret=True
            return ret
        
        if relations:  # no relation to save
            cleanStructure(relations)
            for relation in relations:
                ret=saveChild(relation)
        return ret

    @api.model
    def IsFather(self, ids):
        """
            Check if a Document is child in a docBoM relation.
        """
        ret=False
        
        for idd in getListIDs(ids):
            feed=False
            for fth_id in self.search([('parent_id', '=', idd),('link_kind', '=', 'HiTree')]):
                feed=True
                for line_id in self.search([('child_id', '=', idd),('parent_id', '=', fth_id.child_id.id),('link_kind', '=', 'LyTree')]):
                    feed=False
                ret=ret|feed
                if ret:
                    break
        return ret

    @api.model
    def GetChildren(self, ids, link=["HiTree"]):
        """
            Gets children documents as existing in 'link' relation.
        """
        ret={}
        docLinks=[]
        for idd in getListIDs(ids):
            for docLink in self.search([('parent_id', '=', idd), ('link_kind', 'in', getListIDs(link))]):
                docLinks.append(docLink.id)
            ret[idd]=getListIDs(docLinks)
        return ret

    @api.model
    def GetFathers(self, ids, link=["HiTree"]):
        """
            Gets fathers documents as existing in 'link' relation.
        """
        ret={}
        docLinks=[]
        for idd in getListIDs(ids):
            for docLink in self.search([('child_id', '=', idd), ('link_kind', 'in', getListIDs(link))]):
                docLinks.append(docLink.id)
            ret[idd]=getListIDs(docLinks)
        return ret


class plm_backupdoc(models.Model):
    _name = 'plm.backupdoc'
    _description = 'Document Backup'

    userid          =   fields.Many2one ('res.users', 'Related User', index=True, ondelete='cascade')
    existingfile    =   fields.Char     ('Physical Document Location',size=1024)
    documentid      =   fields.Many2one ('plm.document', 'Related Document', index=True, ondelete='cascade')
    revisionid      =   fields.Integer  (related="documentid.revisionid",string="Revision",store=False)
    minorrevision   =   fields.Char     (related="documentid.minorrevision",string='Minor Revision',store=False)
    state           =   fields.Selection(related="documentid.state",string="Status",store=False)
    file_size_mb    =   fields.Float    (related="documentid.file_size_mb",string="File Size [Mb]",store=False)
    printout        =   fields.Binary   ('Printout Content', attachment=False)
    preview         =   fields.Binary   ('Preview Content', attachment=False)

    def _insertlog(self, ids, changes={}, note={}):
        ret=False       
        op_type, op_note=["unknown",""]
        for objID in self.env['plm.document'].browse(getListIDs(ids)):
            if note:
                op_type="{type}".format(type=note['type'])
                op_note="{reason}".format(reason=note['reason'])
            elif changes:
                op_type='change value'
                op_note=self.env['plm.logging'].getchanges(objID, changes)
            if op_note:
                values={
                        'name': objID.name,
                        'revision': "{major}-{minor}".format(major=objID.revisionid,minor=objID.minorrevision),
                        'file': objID.datas_fname,
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

    def logging_operation(self, ids, operation):
        note={
                'type': 'BackupDoc',
                'reason': "Applying '{operation}' operation to document.".format(operation=operation),
             }
        self._insertlog(ids, note=note)

    def create(self, vals):
        ret=False
        
        check=self._context.get('internal_writing', False)
        if check:
            objectItem=super(plm_backupdoc, self).create(vals)
            if objectItem:
                ret=objectItem
                if vals.get('documentid', False):
                    self.logging_operation(vals['documentid'], 'Stored Copy')
        return ret

    def unlink(self):
        committed = False
        documentType = self.env['plm.document']
        ids=self._ids
        
        check=self._context.get('internal_writing', False)
        if not check:
            if not isAdministrator(self):
                logging.warning(
                    "unlink : Unable to remove the required documents. You aren't authorized in this context.")
                raise UserError(_("Unable to remove the required document.\n You aren't authorized in this context."))
        checkObjs = self.browse(ids)
        for checkObj in checkObjs:
            if not int(checkObj.documentid):
                return super(plm_backupdoc, self).unlink(ids)
            currentname = checkObj.documentid.store_fname
            if checkObj.existingfile != currentname:
                fullname = os.path.join(documentType._get_filestore(), checkObj.existingfile)
                if os.path.exists(fullname):
                    if os.path.exists(fullname):
                        os.chmod(fullname, stat.S_IWRITE)
                        os.unlink(fullname)
                        committed = True
                        self.logging_operation(checkObj.documentid, 'Removed Physical Copy')
                else:
                    logging.warning(
                        "unlink : Unable to remove the document (" + str(checkObj.documentid.name) + "-" + str(
                            checkObj.documentid.revisionid) + ") from backup set. You can't change writable flag.")
                    raise UserError(_("Unable to remove the document '{}-{}' from backup set.\nIt isn't a backup file, it's original current one.".format(checkObj.documentid.name,checkObj.documentid.revisionid)))
        if committed:
            return super(plm_backupdoc, self).unlink(ids)
        else:
            return False


class plm_temporary(osv.osv.osv_memory):
    _inherit = "plm.temporary"

    ##  Specialized Actions callable interactively
    def action_restore_document(self):
        committed = False
        documentType = self.env['plm.document']
        backupdocType = self.env['plm.backupdoc']
        
        
        check=self._context.get('internal_writing', False)
        if not check:
            if not isAdministrator(self):
                logging.warning(
                    "unlink : Unable to remove the required documents.\n You aren't authorized in this context.")
                raise UserError(_("Unable to remove the required document.\n You aren't authorized in this context."))
        backObj=backupdocType.browse(self._context['active_id'])
        if backObj and backObj.documentid:
            objDoc=backObj.documentid
            if objDoc.state == 'draft' and documentType.ischecked_in(objDoc.id):
                if backObj.existingfile != objDoc.store_fname:
                    committed=objDoc.with_context({'internal_writing':True}).write(
                                                   {'store_fname': backObj.existingfile, 
                                                    'printout': backObj.printout,
                                                    'preview': backObj.preview, } )
                    if not committed:
                        logging.warning("action_restore_document : Unable to restore the document (" + str(
                            backObj.documentid.name) + "-" + str(backObj.documentid.revisionid) + ") from backup set.")
                        raise UserError(_("Unable to restore the document '{}-{}' from backup set.\nCheck if it's checked-in, before to retry.".format(backObj.documentid.name,backObj.documentid.revisionid)))
        return committed

