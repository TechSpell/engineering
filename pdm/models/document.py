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

import random
import string
import base64
import logging
import os, stat
import time
from datetime import datetime

from openerp.osv import fields, orm
from openerp.tools.translate import _
from openerp.tools import config as tools_config

from .common import getListIDs, getCleanList, packDictionary, unpackDictionary, getCleanBytesDictionary, \
                        get_signal_workflow, signal_workflow, move_workflow, wf_message_post, \
                        isAdministrator, isObsoleted, isUnderModify, isAnyReleased, isDraft

# To be adequated to plm.component class states
USED_STATES = [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('released', 'Released'), ('undermodify', 'UnderModify'),
               ('obsoleted', 'Obsoleted')]


# STATEFORRELEASE=['confirmed']
# STATESRELEASABLE=['confirmed','released','undermodify','UnderModify']

def random_name():
    random.seed()
    d = [random.choice(string.ascii_letters) for x in xrange(20)]
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


class plm_document(orm.Model):
    _name = 'plm.document'
    _table = 'plm_document'
    _inherit = 'ir.attachment'

    def _insertlog(self, cr, uid, ids, changes={}, note={}, context=None):
        ret=False
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
                        'revision': "{major}-{minor}".format(major=objID.revisionid,minor=objID.minorrevision),
                        'file': objID.datas_fname,
                        'type': self._name,
                        'op_type': op_type,
                        'op_note': op_note,
                        'op_date': datetime.now(),
                        'userid': uid,
                        }
                objectItem=self.pool['plm.logging'].create(cr, uid, values, context=context)
                if objectItem:
                    ret=True
        return ret

    def _is_checkedout_for_me(self, cr, uid, oid, context=None):
        """
            Get if given document (or its latest revision) is checked-out for the requesting user
        """
        act = False
        context = context or self.pool['res.users'].context_get(cr, uid)
        checkType = self.pool['plm.checkout']
        for lastDoc in self._getlastrev(cr, uid, [oid], context=context):
            for docID in checkType.search(cr, uid, [('documentid', '=', lastDoc)], context=context):
                objectCheck = checkType.browse(cr, uid, docID, context=context)
                if objectCheck.userid.id == uid:
                    act = True
                    break
        return act

    def _getlastrev(self, cr, uid, ids, context=None):
        result = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        for objDoc in self.browse(cr, uid, getCleanList(ids), context=context):
            docIds = self.search(cr, uid, [('name', '=', objDoc.name),
                                           ('type', '=', 'binary')], order='revisionid, minorrevision',
                                           context=context)
            docIds.sort()  # Ids are not surely ordered, but revision are always in creation order.
            result.append(docIds[len(docIds) - 1])
        return getCleanList(result)

    def _data_get_files(self, cr, uid, ids, listedFiles=([], []), forceFlag=False, context=None):
        """
            Get Files to return to Client as list: [ docID, nameFile, contentFile, writable, lastupdate ]
        """
        result = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        datefiles, listfiles = listedFiles
        for objDoc in self.browse(cr, uid, ids, context=context):
            if objDoc.type == 'binary':
                timeDoc = self.getLastTime(cr, uid, objDoc.id)
                timeSaved = time.mktime(timeDoc.timetuple())
                timeStamp=timeDoc.strftime('%Y-%m-%d %H:%M:%S')
                try:
                    isCheckedOutToMe = self._is_checkedout_for_me(cr, uid, objDoc.id, context=context)
                    if not (objDoc.datas_fname in listfiles):
                        if (not objDoc.store_fname) and (objDoc.db_datas):
                            value = objDoc.db_datas
                        else:
                            value = file(os.path.join(self._get_filestore(cr), objDoc.store_fname), 'rb').read()
                        result.append(
                            (objDoc.id, objDoc.datas_fname, base64.encodestring(value), isCheckedOutToMe, timeStamp))
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
                                value = file(os.path.join(self._get_filestore(cr), objDoc.store_fname), 'rb').read()
                            result.append(
                                (objDoc.id, objDoc.datas_fname, base64.encodestring(value), isCheckedOutToMe, timeStamp))
                        else:
                            result.append((objDoc.id, objDoc.datas_fname, False, isCheckedOutToMe, timeStamp))
                except Exception, ex:
                    logging.error(
                        "_data_get_files : Unable to access to document (" + str(objDoc.name) + "). Error :" + str(ex))
                    result.append((objDoc.id, objDoc.datas_fname, False, True, self.GetServerTime(cr, uid, ids).strftime('%Y-%m-%d %H:%M:%S')))
        return result

    def _data_get(self, cr, uid, ids, name, arg, context=None):
        result = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        value = False
        for objDoc in self.browse(cr, uid, ids, context=context):
            if objDoc.type == 'binary':
                if not objDoc.store_fname:
                    value = objDoc.db_datas
                    if not value or len(value) < 1:
                        raise orm.except_orm(_('Stored Document Error'), _(
                            "Document %s - %s cannot be accessed" % (str(objDoc.name), str(objDoc.revisionid))))
                else:
                    filestore = os.path.join(self._get_filestore(cr), objDoc.store_fname)
                    if os.path.exists(filestore):
                        value = file(filestore, 'rb').read()
                if value and len(value) > 0:
                    result[objDoc.id] = base64.encodestring(value)
                else:
                    result[objDoc.id] = ''
        return result

    def _data_set(self, cr, uid, oid, name, value, args=None, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        oiDocument = self.browse(cr, uid, oid, context=context)
        if oiDocument.type == 'binary':
            if not value:
                filename = oiDocument.store_fname
                try:
                    os.unlink(os.path.join(self._get_filestore(cr), filename))
                except:
                    pass
                cr.execute('update plm_document set store_fname=NULL WHERE id=%s', (oid,))
                return True
            try:
                printout = False
                preview = False
                if oiDocument.printout:
                    printout = oiDocument.printout
                if oiDocument.preview:
                    preview = oiDocument.preview
                db_datas = b''  # Clean storage field.
                fname, filesize = self._manageFile(cr, uid, oid, binvalue=value, context=context)
                cr.execute('update plm_document set store_fname=%s,file_size=%s,db_datas=%s where id=%s',
                           (fname, filesize, db_datas, oid))
                context.update({'internal_writing':True})              
                self.pool['plm.backupdoc'].create(cr, uid, {
                    'userid': uid,
                    'existingfile': fname,
                    'documentid': oid,
                    'printout': printout,
                    'preview': preview
                }, context=context)

                return True
            except Exception, ex:
                raise orm.except_orm(_('Error in _data_set'), str(ex))
        else:
            return True

    def _explodedocs(self, cr, uid, oid, kinds, listed_documents=[], recursion=True, context=None):
        result = []
        if not(oid in listed_documents):
            context = context or self.pool['res.users'].context_get(cr, uid)
            documentRelation = self.pool['plm.document.relation']
            docRelIds = documentRelation.search(cr, uid, [('parent_id', '=', oid), ('link_kind', 'in', kinds)], context=context)
            if docRelIds:
                for child in documentRelation.browse(cr, uid, docRelIds, context=context):
                    if recursion:
                        listed_documents.append(oid)
                        result.extend(self._explodedocs(cr, uid, child.child_id.id, kinds, listed_documents, recursion, context=context))
                    result.append(child.child_id.id)
        return result

    def _relateddocs(self, cr, uid, oid, kinds, listed_documents=[], recursion=True, context=None):
        """
            Returns fathers (recursively) of this document.
        """
        result = []
        if not (oid in listed_documents):
            context = context or self.pool['res.users'].context_get(cr, uid)
            documentRelation = self.pool['plm.document.relation']
            docRelIds=documentRelation.GetFathers(cr, uid, oid, kinds, context=context)
            for fthID in docRelIds.keys():
                for father in documentRelation.browse(cr, uid, docRelIds[fthID], context=context):
                    if recursion:
                        listed_documents.append(oid)
                        result.extend(self._relateddocs(cr, uid, father.parent_id.id, kinds, listed_documents, recursion, context=context))
                    if father.parent_id:
                        result.append(father.parent_id.id)
        return getCleanList(result)

    def _data_check_files(self, cr, uid, ids, listedFiles=([], []), forceFlag=False, otherFlag=False, context=None):
        result = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        multiplyFactor = 1
        datefiles, listfiles = listedFiles
        for objDoc in self.browse(cr, uid, getCleanList(ids), context=context):
            if objDoc.type == 'binary':
                timeDoc = self.getLastTime(cr, uid, objDoc.id)
                timeSaved = time.mktime(timeDoc.timetuple())

                if not otherFlag:
                    isCheckedOutToMe = self._is_checkedout_for_me(cr, uid, objDoc.id, context=context)
                elif otherFlag == 1:
                    isCheckedOutToMe = False
                elif otherFlag == 2:
                    multiplyFactor = -1
                    isCheckedOutToMe = True
                    collectable = True
                    isNewer = True
                else:
                    isCheckedOutToMe = self._is_checkedout_for_me(cr, uid, objDoc.id, context=context)

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
                try:
                    objDatas = objDoc.datas
                except Exception as msg:
                    logging.error('[_data_check_files] Document with "id":{idd}  and "name":{name} may contains no data!!'.format(idd=objDoc.id, name=objDoc.name))
                    logging.error('Exception: {msg}'.format(msg=msg))
                if (objDoc.file_size < 1) and (objDatas):
                    file_size = len(objDoc.datas)
                else:
                    if os.path.exists(os.path.join(self._get_filestore(cr), objDoc.store_fname)):
                        file_size = objDoc.file_size
                if file_size < 1:
                    collectable = False
                result.append((objDoc.id, objDoc.datas_fname, file_size, collectable * multiplyFactor, isCheckedOutToMe, timeDoc.strftime('%Y-%m-%d %H:%M:%S')))
        return getCleanList(result)

    def _manageFile(self, cr, uid, oid, binvalue=None, context=None):
        """
            use given 'binvalue' to save it on physical repository and to read size (in bytes).
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        path = self._get_filestore(cr)
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except:
                raise orm.except_orm(_('Document Error'),
                                     _("Permission denied or directory %s cannot be created." % (str(path))))

        flag = None
        # This can be improved
        for dirs in os.listdir(path):
            if os.path.isdir(os.path.join(path, dirs)) and len(os.listdir(os.path.join(path, dirs))) < 4000:
                flag = dirs
                break
        if binvalue == None:
            fileStream = self._data_get(cr, uid, [oid], name=None, arg=None, context=context)
            binvalue = fileStream[fileStream.keys()[0]]

        flag = flag or create_directory(path)
        filename = random_name()
        fname = os.path.join(path, flag, filename)
        fobj = file(fname, 'wb')
        value = base64.decodestring(binvalue)
        fobj.write(value)
        fobj.close()
        return (os.path.join(flag, filename), len(value))

    def _iswritable(self, cr, uid, oid):
        checkState = ('draft')
        if not oid.type == 'binary':
            logging.warning("_iswritable : Document (" + str(oid.name) + "-" + str(
                oid.revisionid) + ") not writable as hyperlink.")
            return False
        if not oid.writable:
            logging.warning("_iswritable : Document (" + str(oid.name) + "-" + str(
                oid.revisionid) + ") not writable.")
            return False
        if not oid.state in checkState:
            logging.warning("_iswritable : Document (" + str(oid.name) + "-" + str(
                oid.revisionid) + ") in status ; " + str(oid.state) + ".")
            return False
        return True

    def GetNextDocumentName(self, cr, uid, request, context=None):
        """
            Gets new document name from a an initial part name
        """
        ret= ""
        partName, length=request
        if partName and length:
            context = context or self.pool['res.users'].context_get(cr, uid)
            criteria=[( 'name', 'like', "{name}-".format(name=partName) + "_"*length )]
            ids=self.search(cr, uid,  criteria, context=context)
            count=len(ids)
            while ret=="":
                chkname="{name}-%0{length}d".format(name=partName,length=length)%(count)
                count+=1
                criteria=[('name', '=', chkname)]
                docuIds = self.search(cr, uid, criteria, context=context)
                if (docuIds==None) or (len(docuIds)==0):
                    ret=chkname
                if count>1000:
                    logging.error("GetNextDocumentName : Unable to get a new P/N from sequence '{name}'."\
                                  .format(name=partName))
                    break
        return ret

    def CheckIn(self, cr, uid, ids, context=None):
        """
            Executes Check-In on requested document
        """
        idChks=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        objCheckOut=self.pool['plm.checkout']
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            idChks.extend(objCheckOut.search(cr,uid,[('documentid', '=', tmpObject.id)], context=context))
        context.update({'internal_writing': True})
        return objCheckOut.unlink(cr, uid, idChks, context=context)

    def CheckOut(self, cr, uid, request, context=None):
        """
            Executes Check-In on requested document
        """
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing': True})
        ids, hostName, pwsPath=request
        objCheckOut=self.pool['plm.checkout']
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            if objCheckOut.create(cr, uid, {
                            'documentid':tmpObject.id, 'userid':uid, 'hostname':hostName, 'hostpws':pwsPath
                            }, context=context):
                ret=True
        return ret

    def CheckInRecursive(self, cr, uid, ids, context=None):
        """
             Executes recursive Check-In starting from requested document.
              Returns list of involved files.
       """
        ret=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        for idDoc,namefile,_,_,_,_ in self.checkAllFiles(cr, uid, [getListIDs(ids),[[],[]],False], context=context):
            if self.CheckIn(cr, uid, idDoc, context=context):
                ret.append(namefile)
        return getCleanList(ret)

    def CheckOutRecursive(self, cr, uid, request, context=None):
        """
             Executes recursive Check-Out starting from requested document.
              Returns list of involved files.
       """
        ret=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        ids, hostName, pwsPath=request
        for idDoc,namefile,_,_,_,_ in self.checkAllFiles(cr, uid, [getListIDs(ids),[[],[]],False], context=context):
            if self.CheckOut(cr, uid, [idDoc, hostName, pwsPath], context=context):
                ret.append(namefile)
        return getCleanList(ret)

    def IsSaveable(self, cr, uid, ids, context=None):
        """
            Answers about capability to save requested document
        """
        ret=True
        context = context or self.pool['res.users'].context_get(cr, uid)
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            ret=ret and self._iswritable(cr, uid, tmpObject.id)
        return ret

    def IsRevisable(self, cr, uid, ids, context=None):
        """
            Answers about capability to create a new revision of current document
        """
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            if tmpObject.state in ['released','undermodify','obsoleted']:
                ret=True
                break
        return ret

    def NewRevision(self, cr, uid, request, context=None):
        """
            Creates a new revision of the document
        """
        newID = False
        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing': True, 'new_revision': True})
        newIndex = 0
        ids, hostName, pwsPath=request
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            latestIDs = self.GetLatestIds(cr, uid, [(tmpObject.name, tmpObject.revisionid, False)], context=context)
            for oldObject in self.browse(cr, uid, latestIDs, context=context):
                if isAnyReleased(self, cr, uid, oldObject.id, context=context):
                    note={
                            'type': 'revision process',
                            'reason': "Creating new revision for '{old}'.".format(old=oldObject.name),
                         }
                    self._insertlog(cr, uid, oldObject.id, note=note, context=context)
                    docsignal=get_signal_workflow(self, cr, uid, oldObject, 'undermodify', context=context)
                    move_workflow(self, cr, uid, [oldObject.id], docsignal, 'undermodify')
                    newIndex=int(oldObject.revisionid) + 1
                    default = {
                                'name': oldObject.name,
                                'revisionid': newIndex,
                                'minorrevision':"A",
                                'writable': True,
                                'state': 'draft',
                                'linkedcomponents': [(5)],  # Clean attached products for new revision object
                                }
                    tmpID = super(plm_document, self).copy(cr, uid, oldObject.id, default, context=context)
                    if tmpID!=None:
                        wf_message_post(self, cr, uid, [oldObject.id], body='Created : New Revision.', context=context)
                        newID = tmpID
                        note={
                                'type': 'revision process',
                                'reason': "Created new revision '{index}' for document '{name}'.".format(index=newIndex,name=oldObject.name),
                             }
                        self._insertlog(cr, uid, newID, note=note, context=context)
                        self.CheckOut(cr, uid, [[newID], hostName, pwsPath], context=context)            # Take in Check-Out the new Document revision.
                        
                        self._copy_DocumentBom(cr, uid, oldObject.id, newID, context=context)
                        self._cleanComponentLinks(cr, uid, [(newID,False)], context=context)
                        self.write(cr, uid, newID, default, context=context)
                        note={
                                'type': 'revision process',
                                'reason': "Copied Document Relations to new revision '{index}' for document '{name}'.".format(index=newIndex,name=oldObject.name),
                             }
                        self._insertlog(cr, uid, newID, note=note, context=context)
            break
        return (newID, newIndex)

    def NewMinorRevision(self,cr,uid,request,context=None):
        """
            create a new revision of the document
        """
        newID=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing': True})
        ids, hostName, pwsPath=request
        for tmpObject in self.browse(cr, uid, ids, context=context):
            latestIDs=self.GetLatestIds(cr, uid,[(tmpObject.name,tmpObject.revisionid,False)], context=context)
            for oldObject in self.browse(cr, uid, latestIDs, context=context):
                note={
                        'type': 'minor revision process',
                        'reason': "Creating new revision for '{old}'.".format(old=oldObject.name),
                     }
                self._insertlog(cr, uid, oldObject.id, note=note, context=context)
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
                tmpID=super(plm_document,self).copy(cr, uid, oldObject.id, default, context=context)
                if tmpID!=None:
                    wf_message_post(self, cr, uid, [oldObject.id], body='Created : New Minor Revision.', context=context)
                    newID = tmpID
                    note={
                            'type': 'minor revision process',
                            'reason': "Created new minor revision '{index}' for '{old}'.".format(index=newminor,old=oldObject.name),
                         }
                    self._insertlog(cr, uid, tmpID, note=note, context=context)
                    self.CheckOut(cr, uid, [[newID], hostName, pwsPath], context=context)             # Take in Check-Out the new Document revision.
                    self.write(cr, uid, newID, {'writable':True, 'state':'draft' }, context=context)
            break
        return (newID, default['revisionid'], default['minorrevision']) 

    def Clone(self, cr, uid, request, default={}, context=None):
        """
             Creates a new copy of the document
       """
        exitValues = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        ids, hostName, pwsPath=request
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            note={
                    'type': 'clone object',
                    'reason': "Creating new cloned entity starting from '{old}'.".format(old=tmpObject.name),
                 }
            self._insertlog(cr, uid, tmpObject.id, note=note, context=context)
            newID = self.copy(cr, uid, tmpObject.id, default, context=context)
            if newID:
                newEnt = self.browse(cr, uid, newID, context=context)
                exitValues['_id'] = newID
                exitValues['name'] = newEnt.name
                exitValues['revisionid'] = newEnt.revisionid
                self.CheckOut(cr, uid, [[newID], hostName, pwsPath], context=context)             # Take in Check-Out the new Document revision.
                break
        return packDictionary(exitValues)

    def CloneVirtual(self, cr, uid, ids, default={}, context=None):
        """
            Creates a false new copy of the document
        """
        exitValues = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        for tmpObject in self.browse(cr, uid, getListIDs(ids), context=context):
            new_name = "Copy of {name}".format(name=tmpObject.name)
            exitValues['_id'] = False
            exitValues['name'] = new_name
            exitValues['revisionid'] = 0
            exitValues['writable'] = True
            exitValues['state'] = 'draft'
            exitValues['store_fname'] = ""
            exitValues['file_size'] = 0
            break
        return packDictionary(exitValues)

    def getDocumentID(self,cr ,uid, document, context=None):
        """
            Gets ExistingID from document values.
        """
        existingID=False
        execution=False
        context = context or self.pool['res.users'].context_get(cr, uid)

        fullNamePath='full_file_name'
        if (fullNamePath in document) and document[fullNamePath]:
            execution=True
        else:
            fullNamePath='datas_fname'
            if (fullNamePath in document) and document[fullNamePath]:
                execution=True

        if execution:
            order=None
            criteria=[]
            if not ('name' in document):
#               These statements can cover document already saved without document data
                filename=getFileName(document[fullNamePath])
                if filename:
                    document['name']=filename
                    criteria.append( ('datas_fname', '=', filename) )
                    order='revisionid, minorrevision'
#               These statements can cover document already saved without document data
            else:
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
                existingIDs = self.search(cr, uid, criteria, order=order, context=context)
                if existingIDs:
                    existingIDs.sort()
                    existingID = existingIDs[len(existingIDs) - 1]
            return existingID
        
    def CheckDocumentsToSave(self, cr, uid, documents, default=None, context=None):
        """
            Save or Update Documents
        """
        retValues = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
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

            existingID=self.getDocumentID(cr, uid, document, context=context)

            if existingID:
                hasSaved = False
                hasCheckedOut=self._is_checkedout_for_me(cr, uid, existingID, context=context)
                if hasCheckedOut:
                    objDocument = self.browse(cr, uid, existingID, context=context)
                    if ('_lastupdate' in document) and document['_lastupdate']:
                        lastupdate=datetime.strptime(str(document['_lastupdate']),'%Y-%m-%d %H:%M:%S')
                        logging.debug("CheckDocumentsToSave : time db : {timedb} time file : {timefile}".format(timedb=self.getLastTime(cr,uid,existingID).strftime('%Y-%m-%d %H:%M:%S'), timefile=document['_lastupdate']))
                        if self._iswritable(cr, uid, objDocument) and self.getLastTime(cr, uid, existingID) < lastupdate:
                            hasSaved = True

            retValues[getFileName(document[fullNamePath])]={
                        'hasCheckedOut':hasCheckedOut,
                        'documentID':existingID,
                        'hasSaved':hasSaved}                                                                                              
            listedDocuments.append(document['name'])
        return packDictionary(retValues)


    def SaveOrUpdate(self, cr, uid, request, default=None, context=None):
        """
            Save or Update Documents
        """
        retValues = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        listedDocuments=[]
        fullNamePath='datas_fname'
        documents, [hostName,pwsPath]=unpackDictionary(request)
        modelFields=self.pool['plm.config.settings'].GetFieldsModel(cr, uid,self._name, context=context)
        for document in documents:
            context.update({'internal_writing': False})
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
            if not existingID:
                logging.debug("[SaveOrUpdate] Document {name} is creating.".format(name=document['name']))
                context.update({'internal_writing': True})
                existingID = self.create(cr, uid, document, context=context)
                if autocheckout:
                    hasCheckedOut=self.CheckOut(cr, uid, [existingID, hostName, pwsPath], context=context)
                hasSaved = True
            else:
                if autocheckout:
                    hasCheckedOut=self._is_checkedout_for_me(cr, uid, existingID, context=context)
                else:
                    hasCheckedOut=True
                if hasCheckedOut:
                    objDocument = self.browse(cr, uid, existingID, context=context)
                    if objDocument:
                        document['revisionid']=objDocument.revisionid
                        if self._iswritable(cr, uid, objDocument) and (self.getLastTime(cr, uid, existingID) < lastupdate):
                            logging.debug("[SaveOrUpdate] Document {name}/{revi} is updating.".format(name=document['name'],revi=document['revisionid']))
                            hasSaved = True
                            if not self.write(cr, uid, [existingID], document, context=context):
                                logging.error("[SaveOrUpdate] Document {name}/{revi} cannot be updated.".format(name=document['name'],revi=document['revisionid']))
                                hasSaved = False
                    else:
                        logging.error("[SaveOrUpdate] Document {name}/{revi} doesn't exist anymore.".format(name=document['name'],revi=document['revisionid']))
                else:
                    userName=self.getUserSign(cr, uid, uid, context=context)
                    logging.error("[SaveOrUpdate] Document {name}/{revi} was not checked-out for {user}.".format(name=document['name'],revi=document['revisionid'],user=userName))
   
            retValues[getFileName(document[fullNamePath])]={
                        'hasCheckedOut':hasCheckedOut,
                        'documentID':existingID,
                        'hasSaved':hasSaved}                                                                                              
            listedDocuments.append(document['name'])
        return packDictionary(retValues)

    def RegMessage(self, cr, uid, request, default=None, context=None):
        """
            Registers a message for requested document
        """
        oid, message = request
        self.wf_message_post(cr, uid, [oid], body=message)
        return False

    def CleanUp(self, cr, uid, ids, default=None, context=None):
        """
            Remove faked documents
        """
        cr.execute("delete from plm_document where store_fname=NULL and type='binary'")
        return True

    def QueryLast(self, cr, uid, request=([], []), default=None, context=None):
        """
            Query to return values based on columns selected.
        """
        expData = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        queryFilter, columns = request
        if len(columns) < 1:
            return expData
        if 'revisionid' in queryFilter:
            del queryFilter['revisionid']
        allIDs=self.search(cr, uid, queryFilter, order='revisionid', context=context)
        if len(allIDs) > 0:
            tmpData = self.export_data(cr, uid, allIDs, columns)
            if 'datas' in tmpData:
                expData = tmpData['datas']
        return expData

    def _cleanComponentLinks(self, cr, uid, relations=[], context=None):
        """
            Clean document component relations..
        """
        objType = self.pool['plm.component.document.rel']
        objType.CleanStructure(cr, uid, relations, context=context)


    def _copy_DocumentBom(self, cr, uid, idStart, idDest=None, context=None):
        """
            Create a new 'bomType' BoM (arrested at first level BoM children).
        """
        default = {}
        if not idDest:
            idDest=idStart
        context = context or self.pool['res.users'].context_get(cr, uid)
        checkObjDest = self.browse(cr, uid, idDest, context=context)
        if checkObjDest:
            objBomType = self.pool['plm.document.relation']
            objBoms = objBomType.search(cr, uid, [('parent_id', '=', idDest), ], context=context)
            idBoms = objBomType.search(cr, uid, [('parent_id', '=', idStart), ], context=context)
            if not objBoms:
                for oldObj in objBomType.browse(cr, uid, getListIDs(idBoms), context=context):
                    default={
                             'parent_id': idDest,
                             'child_id': oldObj.child_id.id,
                             'kind': oldObj.link_kind,
                             'configuration': '',
                             'userid': False,
                             }
                    objBomType.create(cr,uid, default, context=context)
        return False
                    
    def ischecked_in(self, cr, uid, ids, context=None):
        """
            Check if a document is checked-in 
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        checkoutType = self.pool['plm.checkout']

        for document in self.browse(cr, uid, getListIDs(ids), context=context):
            if checkoutType.search(cr, uid, [('documentid', '=', document.id)], context=context):
                logging.warning(
                    _("The document %s - %s has not checked-in" % (str(document.name), str(document.revisionid))))
                return False
        return True

    def logging_workflow(self, cr, uid, ids, action, status, context=None):
        note={
                'type': 'workflow movement',
                'reason': "Applying workflow action '{action}', moving to status '{status}.".format(action=action, status=status),
             }
        self._insertlog(cr, uid, ids, note=note, context=context)

    def _action_onrelateddocuments(self, cr, uid, ids, default={}, action="", status="", context=None):
        """
            Move workflow on documents related to given ones.
        """
        fthkindList = ['RfTree', 'LyTree']          # Get relation names due to fathers
        chnkindList = ['HiTree','RfTree', 'LyTree'] # Get relation names due to children
        context = context or self.pool['res.users'].context_get(cr, uid)
        context['internal_writing']=True
        allIDs=getCleanList(ids)
        relIDs = self.getRelatedDocs(cr, uid, ids, fthkindList, chnkindList, context=context)
        allIDs.extend(relIDs)                   # Force to obtain involved documents
        docIDs=list(set(allIDs)-set(ids))       # Force to obtain only related documents
        for currObj in self.browse(cr, uid, docIDs, context=context):
            docsignal=get_signal_workflow(self, cr, uid, currObj, status, context=context)
            move_workflow(self, cr, uid, [currObj.id], docsignal, status)
        ret=self.write(cr, uid, ids, default, context=context)
        self.logging_workflow(cr, uid, ids, action, status, context=context)
        if ret:
            wf_message_post(self, cr, uid, allIDs, body='Status moved to: {status}.'.format(status=status), context=context)
        return ret
 
    def ActionUpload(self, cr, uid, ids, context=None):
        """
            action to be executed after automatic upload
        """
        signal='uploaddoc'
        signal_workflow(self, cr, uid, ids, signal)
        return False

    def action_upload(self,cr,uid,ids,context=None):
        """
            action to be executed after automatic upload
        """
        status='uploaded'
        action = 'upload'
        default = {
                    'writable': False,
                    'state': status,
                    }
        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing': True})
        self.logging_workflow(cr, uid, ids, default, action, status, context=context)
        return self._action_onrelateddocuments(cr, uid, ids, default, action, status, context=context)

    def action_draft(self, cr, uid, ids, context=None):
        """
            release the object
        """
        status='draft'
        action = 'draft'
        default = {
                    'writable': True,
                    'state': status,
                    }
        context = context or self.pool['res.users'].context_get(cr, uid)
        return self._action_onrelateddocuments(cr, uid, ids, default, action, status, context=context)

    def action_correct(self, cr, uid, ids, context=None):
        """
            release the object
        """
        status='draft'
        action = 'correct'
        default = {
                    'writable': True,
                    'state': status,
                    }
        context = context or self.pool['res.users'].context_get(cr, uid)
        return self._action_onrelateddocuments(cr, uid, ids, default, action, status, context=context)

    def action_confirm(self, cr, uid, ids, context=None):
        """
            action to be executed for Draft state
        """
        ret=False
        status='confirmed'
        action='confirm'
        default = {
                   'writable': False,
                   'state': status
                   }
        context = context or self.pool['res.users'].context_get(cr, uid)
        if self.ischecked_in(cr, uid, ids, context=context):
            ret=self._action_onrelateddocuments(cr, uid, ids, default, action, status, context=context)
        else:
            signal_workflow(self, cr, uid, ids, 'correct')
        return ret

    def action_release(self, cr, uid, ids, context=None):
        """
            release the object
        """
        status='released'
        action = 'release'
        default = {
                    'writable': False,
                    'state': status,
                    }
        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing': True})
        for oldObject in self.browse(cr, uid, ids, context=context):
            last_ids = self._getbyrevision(cr, uid, oldObject.name, oldObject.revisionid - 1, context=context)
            if last_ids:
                move_workflow(self, cr, uid, last_ids, 'obsolete', 'obsoleted')
        return self._action_onrelateddocuments(cr, uid, ids, default, action, status, context=context)

    def action_obsolete(self, cr, uid, ids, context=None):
        """
            obsolete the object
        """
        status='obsoleted'
        action = 'obsolete'

        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing': True})
 
        for oldObject in self.browse(cr, uid, ids, context=context):
            move_workflow(self, cr, uid, oldObject.id, action, status, context=context)
        wf_message_post(self, cr, uid, ids, body='Status moved to: {status}.'.format(status=status), context=context)
        return True

    def action_modify(self, cr, uid, ids, context=None):
        """
            modify the object
        """
        status='undermodify'
        action = 'modify'

        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing': True})
 
        for oldObject in self.browse(cr, uid, ids, context=context):
            move_workflow(self, cr, uid, oldObject.id, action, status, context=context)
        wf_message_post(self, cr, uid, ids, body='Status moved to: {status}.'.format(status=status), context=context)
        return True

    #   Overridden methods for this entity
    def _get_filestore(self, cr):
        dms_Root_Path = tools_config.get('document_path', os.path.join(tools_config['root_path'], 'filestore'))
        return os.path.join(dms_Root_Path, cr.dbname)

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        return self._search(cr, uid, args, offset=offset, limit=limit, order=order, context=context, count=False)

    def copy(self, cr, uid, oid, default={}, context=None):
        """
            Overwrite the default copy method
        """
        newID = False
        previous_name=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        # get All document relation
        documentRelation = self.pool['plm.document.relation']
        docRelIds = documentRelation.search(cr, uid, [('parent_id', '=', oid)], context=context)
        if not context.get('new_revision', False):
            previous_name = self.browse(cr, uid, oid, context=context).name
            if not 'name' in default:
                new_name = 'Copy of %s' % previous_name
                l = self.search(cr, uid, [('name', '=', new_name)], order='revisionid', context=context)
                if len(l) > 0:
                    new_name = '%s (%s)' % (new_name, len(l) + 1)
                default['name'] = new_name
            # manage copy of the file
            fname, filesize = self._manageFile(cr, uid, oid, context=context)
            # assign default value
            default['store_fname'] = fname
            default['file_size'] = filesize
            default['state'] = 'draft'
            default['writable'] = True
            note={
                'type': 'copy object',
                'reason': "Previous name was '{old} new one is '{new}'.".format(old=previous_name,new=new_name),
                 }
            self._insertlog(cr, uid, oid, note=note, context=context)

        tmpID = super(plm_document, self).copy(cr, uid, oid, default, context=context)
        if tmpID!=None:
            newID = tmpID
            # create all the document relation
            for OldRel in documentRelation.browse(cr, uid, getListIDs(docRelIds), context=context):
                documentRelation.create(cr, uid, {
                    'parent_id': newID,
                    'child_id': OldRel.child_id.id,
                    'configuration': OldRel.configuration,
                    'link_kind': OldRel.link_kind,
                }, context=context)
        if newID and previous_name:
            wf_message_post(self, cr, uid, [newID], body='Copied starting from : {value}.'.format(value=previous_name), context=context)
        return newID

    def create(self, cr, uid, vals, context=None):
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        if vals and vals.get('name', False):
            existingID=self.getDocumentID(cr, uid, vals, context=context)
            if existingID:
                ret=existingID
            else:
                try:
                    minor=vals.get('minorrevision',False)
                    if not minor:
                        minor=vals['minorrevision']="A"
                    major=vals.get('revisionid', None)
                    if not major:
                        major=vals['revisionid']=0
                    
                    ret=super(plm_document, self).create(cr, uid, vals, context=context)
                    values={
                            'name': vals['name'],
                            'revision': "{major}-{minor}".format(major=major,minor=minor),
                            'file': vals['datas_fname'],
                            'type': self._name,
                            'op_type': 'creation',
                            'op_note': 'Create new entity on database',
                            'op_date': datetime.now(),
                            'userid': uid,
                            }
                    self.pool['plm.logging'].create(cr, uid, values, context=context)
                except Exception, ex:
                    logging.error("Exception {msg}. It has tried to create with values : {vals}.".format(msg=ex, vals=vals))
        return ret

    def write(self, cr, uid, ids, vals, context=None):
        ret=True
        if vals:
            context = context or self.pool['res.users'].context_get(cr, uid)
            check=context.get('internal_writing', False)
            if not check:
                for docItem in self.browse(cr, uid, ids, context=context):
                    if not isDraft(self,cr, uid, docItem.id, context=context):
                    
                        raise orm.except_orm(_('Edit Entity Error'),
                                             _("The entity '{name}-{rev}' is in a status that does not allow you to make save action".format(name=docItem.name,rev=docItem.revisionid)))
                        ret=False
                        break
                    if not docItem.writable:
                        raise orm.except_orm(_('Edit Entity Error'),
                                             _("The entity '{name}-{rev}' cannot be written.".format(name=docItem.name,rev=docItem.revisionid)))
                        break
            if ret:
                self._insertlog(cr, uid, ids, changes=vals, context=context)
                ret=super(plm_document, self).write(cr, uid, ids, vals, context=context)
        return ret

    def unlink(self, cr, uid, ids, context=None):
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        isAdmin = isAdministrator(self, cr, uid, context=context)

        if not self.pool['plm.document.relation'].IsChild(cr, uid, ids, context=context):
            note={
                'type': 'unlink object',
                'reason': "Removed entity from database.",
             }
            for checkObj in self.browse(cr, uid, ids, context=context):
                checkApply=False
                if isAnyReleased(self, cr, uid, checkObj.id, context=context):
                    if isAdmin:
                        checkApply=True
                elif isDraft(self, cr, uid, checkObj.id, context=context):
                    checkApply=True

                if not checkApply:
                    continue            # Apply unlink only if have respected rules.
    
                existingIDs = self.search(cr, uid, [
                                        ('name', '=', checkObj.name), 
                                        ('revisionid', '=', checkObj.revisionid - 1)
                                        ])
                if len(existingIDs) > 0:
                    status='released'
                    context.update({'internal_writing': True})
                    for document in self.browse(cr, uid, getListIDs(existingIDs), context=context):
                        docsignal=get_signal_workflow(self, cr, uid, document, status, context=context)
                        move_workflow(self, cr, uid, [document.id], docsignal, status)
                self._insertlog(cr, uid, checkObj.id, note=note, context=context)
                ret=ret | super(plm_document, self).unlink(cr, uid, ids, context=context)
        return ret

    def _get_checkout_state(self, cr, uid, ids, field_name, args, context={}):
        outVal = {}  # {id:value}
        context = context or self.pool['res.users'].context_get(cr, uid)
        for docId in ids:
            chechRes = self.getCheckedOut(cr, uid, docId, None, context=context)
            if chechRes:
                outVal[docId] = str(chechRes[2])
            else:
                outVal[docId] = ''
        return outVal

    def _is_checkout(self, cr, uid, ids, field_name, args, context={}):
        outRes = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        for docId in ids:
            outRes[docId] = False
            chechRes = self.getCheckedOut(cr, uid, docId, None, context=context)
            if chechRes:
                outRes[docId] = True
        return outRes

    _columns = {
        'usedforspare': fields.boolean('Used for Spare',
                                       help="Drawings marked here will be used printing Spare Part Manual report."),
        'revisionid': fields.integer('Revision Index', required=True),
        'minorrevision': fields.char('Minor Revision Label'),
        'writable': fields.boolean('Writable'),
        'datas': fields.function(_data_get, method=True, fnct_inv=_data_set, string='File Content', type="binary"),
        'printout': fields.binary('Printout Content', help="Print PDF content."),
        'preview': fields.binary('Preview Content', help="Static preview."),
        'state': fields.selection(USED_STATES, 'Status', help="The status of the product.", readonly="True"),
        'checkout_user': fields.function(_get_checkout_state, type='char', string="Checked-Out To"),
        'is_checkout': fields.function(_is_checkout, type='boolean', string="Is Checked-Out", store=False)
    }

    _defaults = {
        'usedforspare': lambda *a: False,
        'revisionid': lambda *a: 0,
        'minorrevision': lambda *a: 'A',
        'writable': lambda *a: True,
        'state': lambda *a: 'draft',
    }

    _sql_constraints = [
        ('name_unique', 'unique (name,revisionid,minorrevision)', 'File name has to be unique!')
        # qui abbiamo la sicurezza dell'univocita del nome file
    ]

    def CheckedIn(self, cr, uid, files, default=None, context=None):
        """
            Get checked status for requested files
        """
        retValues = []
        context = context or self.pool['res.users'].context_get(cr, uid)

        def getcheckedfiles(files):
            res = []
            for fileName in files:
                ids = self.search(cr, uid, [('datas_fname', '=', fileName)], order='revisionid')
                if len(ids) > 0:
                    ids.sort()
                    res.append([fileName, not (self._is_checkedout_for_me(cr, uid, ids[len(ids) - 1], context=context))])
            return res

        if len(files) > 0:  # no files to process
            retValues = getcheckedfiles(files)
        return retValues

    def GetUpdated(self, cr, uid, vals, context=None):
        """
            Get Last/Requested revision of given items (by name, revision, update time)
        """
        docData, attribNames = unpackDictionary(vals)
        context = context or self.pool['res.users'].context_get(cr, uid)
        ids = self.GetLatestIds(cr, uid, docData, context=context)
        return packDictionary(self.read(cr, uid, getCleanList(ids), attribNames))

    def GetLatestIds(self, cr, uid, vals, context=None):
        """
            Get Last/Requested revision of given items (by name, revision, update time)
        """
        ids = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        for request in vals:
            docName, _, updateDate = request
            if updateDate:
                criteria=[('name', '=', docName), ('write_date', '>', updateDate)]
            else:
                criteria=[('name', '=', docName)]
    
            docIds = self.search(cr, uid, criteria, order='revisionid,minorrevision', context=context)
            if len(docIds) > 0:
                docIds.sort()
                ids.append(docIds[len(docIds) - 1])
        return getCleanList(ids)

    def CheckWholeSetFiles(self, cr, uid, request, default=None, context=None):
        """
            Evaluate documents to return
        """
        required,wholeset=[[],[]]
        context = context or self.pool['res.users'].context_get(cr, uid)
        if request:
            oid, listedFiles, selection = request
            if oid:
                required=self.checkAllFiles(cr, uid, [ oid, listedFiles, selection ], default=None, context=None)
                wholeset=self.checkAllFiles(cr, uid, [ oid, ([],[]), selection ],   default=None, context=None)
        return packDictionary([required,wholeset])
        
    def checkAllFiles(self, cr, uid, request, default=None, context=None):
        """
            Evaluate documents to return
        """
        outputData=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
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
            docArray = self._relateddocs(cr, uid, oid, [kind], listed_documents, context=context)
            kind = 'SdTree'  # Get relations due to service files connected
            othArray = self._explodedocs(cr, uid, oid, [kind], listed_documents, context=context)

            kind = 'HiTree'  # Get Hierarchical tree relations due to children
            modArray = self._explodedocs(cr, uid, oid, [kind], listed_models, context=context)
            for item in modArray:
                kind = 'LyTree'  # Get relations due to layout connected
                docArray.extend(self._relateddocs(cr, uid, item, [kind], listed_documents, context=context))
                kind = 'SdTree'  # Get relations due to service files connected
                othArray.extend(self._explodedocs(cr, uid, item, [kind], listed_documents, context=context))
                
            modArray.extend(docArray)
 
            docArray=getCleanList(modArray)
            

            if selection == 2:
                docArray = self._getlastrev(cr, uid, docArray, context=context)

            if not oid in docArray:
                docArray.append(oid)  # Add requested document to package
            outputData = self._data_check_files(cr, uid, docArray, listedFiles, forceFlag, context=context)
            if othArray:
                altothData = self._data_check_files(cr, uid, othArray, listedFiles, True, execFlag, context=context)
                if altothData:
                    outputData.extend(altothData)
        return outputData

    def GetSomeFiles(self, cr, uid, request, default=None, context=None):
        """
            Extract documents to be returned.
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        forceFlag = False
        ids, listedFiles, selection = request
        if selection == False:
            selection = 1

        if selection < 0:
            forceFlag = True
            selection = selection * (-1)

        if selection == 2:
            docArray = self._getlastrev(cr, uid, ids, context=context)
        else:
            docArray = ids
        return packDictionary(self._data_get_files(cr, uid, docArray, listedFiles, forceFlag, context=context))

    def GetAllFiles(self, cr, uid, request, default=None, context=None):
        """
            Extract documents to be returned 
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
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
        docArray = self._explodedocs(cr, uid, oid, [kind], listed_models, context=context)

        if not oid in docArray:
            docArray.append(oid)  # Add requested document to package

        for item in docArray:
            kinds = ['LyTree', 'RfTree']  # Get relations due to layout connected
            modArray.extend(self._relateddocs(cr, uid, item, kinds, listed_documents, context=context))
            modArray.extend(self._explodedocs(cr, uid, item, kinds, listed_documents, context=context))
        #             kind='RfTree'               # Get relations due to referred connected
        #             modArray.extend(self._relateddocs(cr, uid, item, kind, listed_documents, context=context))
        #             modArray.extend(self._explodedocs(cr, uid, item, kind, listed_documents, context=context))

        modArray.extend(docArray)
        docArray = getCleanList(modArray)  # Get unique documents object IDs

        if selection == 2:
            docArray = self._getlastrev(cr, uid, docArray, context=context)

        if not oid in docArray:
            docArray.append(oid)  # Add requested document to package
        return packDictionary(self._data_get_files(cr, uid, docArray, listedFiles, forceFlag, context=context))

    def getRelatedDocs(self, cr, uid, ids, fthkindList=[], chnkindList=[], context=None):
        """
            Extracts documents related to current one(s) (layouts, referred models, etc.)
        """
        result = []
        listed_documents = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        for oid in ids:
            result.extend(self._relateddocs(cr, uid, oid, fthkindList, listed_documents, False, context=context))
            result.extend(self._explodedocs(cr, uid, oid, chnkindList, listed_documents, False, context=context))
        return (getCleanList(result))

    def GetRelatedDocs(self, cr, uid, ids, default=None, context=None):
        """
            Return document infos related to current one(s) (layouts, referred models, etc.)
        """
        result = []
        kindList = ['RfTree', 'LyTree']  # Get relations due to referred models
        context = context or self.pool['res.users'].context_get(cr, uid)
        read_docs = self.getRelatedDocs(cr, uid, ids, kindList, kindList, context=context)
        for document in self.browse(cr, uid, read_docs, context=context):
            result.append([document.id, document.name, document.preview])
        return result

    def GetServerTime(self, cr, uid, oid, default=None, context=None):
        """
            calculate the server db time 
        """
        return datetime.now()

    def getLastTime(self, cr, uid, oid, default=None, context=None):
        """
            get document last modification time 
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        obj = self.browse(cr, uid, oid, context=context)
        if (obj.write_date != False):
            return datetime.strptime(obj.write_date, '%Y-%m-%d %H:%M:%S')
        else:
            return datetime.strptime(obj.create_date, '%Y-%m-%d %H:%M:%S')

    def getUserSign(self, cr, uid, oid, default=None, context=None):
        """
            get the user name
        """
        userType = self.pool['res.users']
        context = context or self.pool['res.users'].context_get(cr, uid)
        uiUser = userType.browse(cr, uid, oid, context=context)
        return uiUser.name

    def _getbyrevision(self, cr, uid, name, revision, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        return self.search(cr, uid, [('name', '=', name), ('revisionid', '=', revision)], context=context)

    def getCheckedOut(self, cr, uid, oid, default=None, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        checkoutType = self.pool['plm.checkout']
        checkoutIDs = checkoutType.search(cr, uid, [('documentid', '=', oid)], context=context)
        for checkoutID in checkoutIDs:
            objDoc = checkoutType.browse(cr, uid, checkoutID, context=context)
            return (objDoc.documentid.name, objDoc.documentid.revisionid, self.getUserSign(cr, objDoc.userid.id, 1),
                    objDoc.hostname)
        return False


class plm_checkout(orm.Model):
    _name = 'plm.checkout'
    _columns = {
        'create_date': fields.datetime('Date Created', readonly=True),
        'userid': fields.many2one('res.users', 'Related User', ondelete='cascade'),
        'hostname': fields.char('Hostname', size=64),
        'hostpws': fields.char('PWS Directory', size=1024),
        'documentid': fields.many2one('plm.document', 'Related Document', ondelete='cascade'),
    }

    _sql_constraints = [
        ('documentid', 'unique (documentid)', 'The documentid must be unique !')
    ]

    def _insertlog(self, cr, uid, ids, changes={}, note={}, context=None):
        ret=False
        objectItem=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        op_type, op_note=["unknown",""]
        for objID in self.pool['plm.document'].browse(cr, uid, getListIDs(ids), context=context):
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
                        'userid': uid,
                        }
                objectItem=self.pool['plm.logging'].create(cr, uid, values, context=context)
                if objectItem:
                    ret=True
        return ret

    def logging_operation(self, cr, uid, ids, operation, context=None):
        note={
                'type': 'CheckDoc',
                'reason': "Applying '{operation}' operation to document.".format(operation=operation),
             }
        self._insertlog(cr, uid, ids, note=note, context=context)

    def _adjustRelations(self, cr, uid, oids, userid=False, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        docRelType = self.pool['plm.document.relation']
        if userid:
            ids = docRelType.search(cr, uid, [('child_id', 'in', getListIDs(oids)), ('userid', '=', False)], context=context)
        else:
            ids = docRelType.search(cr, uid, [('child_id', 'in', getListIDs(oids))], context=context)
        if ids:
            values = {'userid': userid, }
            docRelType.write(cr, uid, ids, values, context=context)

    def create(self, cr, uid, vals, context=None):
        ret=False
        docIDs=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        check=context.get('internal_writing', False)
        if check:
            documentType = self.pool['plm.document']
            docObj = documentType.browse(cr, uid, vals['documentid'], context=context)
            if docObj.state=='draft':
                values = {'writable': True, }
                if not documentType.write(cr, uid, [docObj.id], values, context=context):
                    logging.error("create : Unable to check-out the required document (" + str(docObj.name) + "-" + str(
                        docObj.revisionid) + ").")
                    return ret
                self._adjustRelations(cr, uid, getListIDs(docObj.id), uid, context=context)
                docIDs.append(docObj.id)
                objectItem=super(plm_checkout, self).create(cr, uid, vals, context=context)
                if objectItem:
                    ret=objectItem
                    self.logging_operation(cr, uid, docIDs, 'Check-Out', context=context)
                    wf_message_post(documentType, cr, uid, docIDs, body='Checked-Out')
        return ret

    def unlink(self, cr, uid, ids, context=None):
        documentType = self.pool['plm.document']
        context = context or self.pool['res.users'].context_get(cr, uid)
        check=context.get('internal_writing', False)
        if not check:
            if not isAdministrator(self, cr, uid, context=context):
                logging.error(
                    "unlink : Unable to Check-In the required document.\n You aren't authorized in this context.")
                raise orm.except_orm(_('Check-In Error'), _(
                    "Unable to Check-In the required document.\n You aren't authorized in this context."))
            else:
                context.update({'internal_writing':True})
        checkObjs = self.browse(cr, uid, getListIDs(ids), context=context)
        docIDs = []
        values = {'writable': False, }
        for checkObj in checkObjs:
            docIDs.append(checkObj.documentid.id)
            if not documentType.write(cr, uid, [checkObj.documentid.id], values, context=context):
                logging.error(
                    "unlink : Unable to check-in the document (" + str(checkObj.documentid.name) + "-" + str(
                        checkObj.documentid.revisionid) + ").\n You can't change writable flag.")
                return False
        self._adjustRelations(cr, uid, docIDs, False, context=context)
        ret=super(plm_checkout, self).unlink(cr, uid, getListIDs(ids), context=context)
        wf_message_post(documentType, cr, uid, docIDs, body='Checked-In')
        self.logging_operation(cr, uid, docIDs, 'Check-In', context=context)
        return ret

class plm_document_relation(orm.Model):
    _name = 'plm.document.relation'
    _columns = {
        'parent_id': fields.many2one('plm.document', 'Related parent document', ondelete='cascade'),
        'child_id': fields.many2one('plm.document', 'Related child document', ondelete='cascade'),
        'configuration': fields.char('Configuration Name', size=1024),
        'link_kind': fields.char('Kind of Link', size=64, required=True),
        'create_date': fields.datetime('Date Created', readonly=True),
        'userid': fields.many2one('res.users', 'CheckOut User', readonly="True"),
    }
    _defaults = {
        'link_kind': lambda *a: 'HiTree',
        'userid': lambda *a: False,
    }
    _sql_constraints = [
        ('relation_uniq', 'unique (parent_id,child_id,link_kind)', _('The Document Relation must be unique !'))
    ]

    def CleanStructure(self, cr, uid, parent_ids=[], context=None):
        cleanIds=[]
        for parent_id in parent_ids:
            criteria = [('parent_id', '=', parent_id)]
            cleanIds.extend(self.search(cr, uid, criteria, context=context))
        self.unlink(cr, uid, getCleanList(cleanIds), context=context)
        return False

    def SaveStructure(self, cr, uid, relations=[], level=0, currlevel=0, context=None):
        """
            Save Document relations
        """
        ret=False
        savedItems = []
        context = context or self.pool['res.users'].context_get(cr, uid)

        def cleanStructure(relations):
            res = {}
            cleanIds = []
            for relation in relations:
                res['parent_id'], res['child_id'], res['configuration'], res['link_kind'] = relation
                if (res['link_kind'] == 'LyTree') or (res['link_kind'] == 'RfTree'):
                    criteria = [('child_id', '=', res['child_id'])]
                else:
                    criteria = [('parent_id', '=', res['parent_id'])]
                cleanIds.extend(self.search(cr, uid, criteria, context=context))
            self.unlink(cr, uid, getCleanList(cleanIds), context=context)

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
                            savedItems.append((res['parent_id'], res['child_id']))
                            self.create(cr, uid, res, context=context)
                else:
                    logging.error("saveChild : Unable to create a relation between documents. One of documents involved doesn't exist.")
                    logging.error("Arguments ({}).".format(relation))
                    ret=True
            except Exception as ex:
                logging.error("saveChild : Unable to create a relation between documents.")
                logging.error("Arguments ({}).".format(relation))
                logging.error("Exception ({}).".format(ex))
                ret=True
            return ret
        
        if relations:  # no relation to save
            cleanStructure(relations)
            for relation in relations:
                ret=saveChild(relation)
        return ret

    def IsChild(self, cr, uid, ids, context=None):
        """
            Check if a Document is child in a docBoM relation.
        """
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        for idd in getListIDs(ids):
            if self.search(cr, uid, [('child_id', '=', idd)], context=context):
                ret=ret|True
        return ret

    def GetChildren(self, cr, uid, ids, link=["HiTree"], context=None):
        """
            Gets children documents as existing in 'link' relation.
        """
        ret={}
        context = context or self.pool['res.users'].context_get(cr, uid)
        for idd in getListIDs(ids):
            links=self.search(cr, uid, [('parent_id', '=', idd), ('link_kind', 'in', getListIDs(link))], context=context)
            if links:
                ret[idd]=links
        return ret

    def GetFathers(self, cr, uid, ids, link=["HiTree"], context=None):
        """
            Gets fathers documents as existing in 'link' relation.
        """
        ret={}
        context = context or self.pool['res.users'].context_get(cr, uid)
        for idd in getListIDs(ids):
            links=self.search(cr, uid, [('child_id', '=', idd), ('link_kind', 'in', getListIDs(link))], context=context)
            if links:
                ret[idd]=links
        return ret


class plm_backupdoc(orm.Model):
    _name = 'plm.backupdoc'
    _columns = {
        'userid': fields.many2one('res.users', 'Related User', ondelete='cascade'),
        'create_date': fields.datetime('Date Created', readonly=True),
        'createdate': fields.datetime('Date Created', readonly=True),
        'existingfile': fields.char('Physical Document Location', size=1024),
        'documentid': fields.many2one('plm.document', 'Related Document', ondelete='cascade'),
        'revisionid': fields.related('documentid', 'revisionid', type="integer", relation="plm.document",
                                     string="Revision", store=False),
        'minorrevision': fields.related('documentid', 'minorrevision', type="char", relation="plm.document",
                                     string="Minor Revision", store=False),
        'state': fields.related('documentid', 'state', type="char", relation="plm.document", string="Status",
                                store=False),
        'printout': fields.binary('Printout Content'),
        'preview': fields.binary('Preview Content'),
    }
    _defaults = {
        'createdate': lambda self, cr, uid, ctx: time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    def _insertlog(self, cr, uid, ids, changes={}, note={}, context=None):
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        op_type, op_note=["unknown",""]
        for objID in self.pool['plm.document'].browse(cr, uid, getListIDs(ids), context=context):
            if note:
                op_type="{type}".format(type=note['type'])
                op_note="{reason}".format(reason=note['reason'])
            elif changes:
                op_type='change value'
                op_note=self.pool['plm.logging'].getchanges(cr, uid, objID, changes, context=context)
            if op_note:
                values={
                        'name': objID.name,
                        'revision': "{major}-{minor}".format(major=objID.revisionid,minor=objID.minorrevision),
                        'file': objID.datas_fname,
                        'type': self._name,
                        'op_type': op_type,
                        'op_note': op_note,
                        'op_date': datetime.now(),
                        'userid': uid,
                        }
                objectItem=self.pool['plm.logging'].create(cr, uid, values, context=context)
                if objectItem:
                    ret=True
        return ret

    def logging_operation(self, cr, uid, ids, operation, context=None):
        note={
                'type': 'BackupDoc',
                'reason': "Applying '{operation}' operation to document.".format(operation=operation),
             }
        self._insertlog(cr, uid, ids, note=note, context=context)

    def create(self, cr, uid, vals, context=None):
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        check=context.get('internal_writing', False)
        if check:
            objectItem=super(plm_backupdoc, self).create(cr, uid, vals, context=context)
            if objectItem:
                ret=objectItem
                if vals.get('documentid', False):
                    self.logging_operation(cr, uid, vals['documentid'], 'Stored Copy', context=context)
        return ret

    def unlink(self, cr, uid, ids, context=None):
        committed = False
        documentType = self.pool['plm.document']
        context = context or self.pool['res.users'].context_get(cr, uid)
        check=context.get('internal_writing', False)
        if not check:
            if not isAdministrator(self, cr, uid, context=context):
                logging.warning(
                    "unlink : Unable to remove the required documents. You aren't authorized in this context.")
                raise orm.except_orm(_('Backup Error'), _(
                    "Unable to remove the required document.\n You aren't authorized in this context."))
        checkObjs = self.browse(cr, uid, ids, context=context)
        for checkObj in checkObjs:
            if not int(checkObj.documentid):
                return super(plm_backupdoc, self).unlink(cr, uid, ids, context=context)
            currentname = checkObj.documentid.store_fname
            if checkObj.existingfile != currentname:
                fullname = os.path.join(documentType._get_filestore(cr), checkObj.existingfile)
                if os.path.exists(fullname):
                    if os.path.exists(fullname):
                        os.chmod(fullname, stat.S_IWRITE)
                        os.unlink(fullname)
                        committed = True
                        self.logging_operation(cr, uid, checkObj.documentid, 'Removed Physical Copy', context=context)
                else:
                    logging.warning(
                        "unlink : Unable to remove the document (" + str(checkObj.documentid.name) + "-" + str(
                            checkObj.documentid.revisionid) + ") from backup set. You can't change writable flag.")
                    raise orm.except_orm(_('Check-In Error'), _(
                        "Unable to remove the document (" + str(checkObj.documentid.name) + "-" + str(
                            checkObj.documentid.revisionid) + ") from backup set.\n It isn't a backup file, it's original current one."))
        if committed:
            return super(plm_backupdoc, self).unlink(cr, uid, ids, context=context)
        else:
            return False

    def action_restore_document(self, cr, uid, ids, context=None):
        committed = False
        documentType = self.pool['plm.document']
        context = context or self.pool['res.users'].context_get(cr, uid)
        check=context.get('internal_writing', False)
        if not check:
            if not isAdministrator(self, cr, uid, context=context):
                logging.warning(
                    "unlink : Unable to remove the required documents.\n You aren't authorized in this context.")
                raise orm.except_orm(_('Backup Error'), _(
                    "Unable to remove the required document.\n You aren't authorized in this context."))
        checkObj=self.browse(cr, uid, context['active_id'], context=context)
        objDoc=documentType.browse(cr, uid, checkObj.documentid.id, context=context)
        if objDoc.state == 'draft' and documentType.ischecked_in(cr, uid, ids, context=context):
            if checkObj.existingfile != objDoc.store_fname:
                context.update({'internal_writing':True})
                committed=documentType.write(cr, uid, [objDoc.id],
                                               {'store_fname': checkObj.existingfile, 'printout': checkObj.printout,
                                                'preview': checkObj.preview, }, context=context)
                if not committed:
                    logging.warning("action_restore_document : Unable to restore the document (" + str(
                        checkObj.documentid.name) + "-" + str(checkObj.documentid.revisionid) + ") from backup set.")
                    raise orm.except_orm(_('Check-In Error'), _(
                        "Unable to restore the document (" + str(checkObj.documentid.name) + "-" + str(
                            checkObj.documentid.revisionid) + ") from backup set.\n Check if it's checked-in, before to proceed."))
        self.unlink(cr, uid, ids, context=context)
        return committed

