# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2016-2017 TechSpell srl (<http://techspell.eu>). All Rights Reserved
#    
#    Created on : 2017-03-21
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
import base64
import pickle
from array import array
from xmlrpclib import Binary

import openerp.netsvc as netsvc
from openerp.tools.translate import _

BOMTYPES=[('normal',_('Normal BoM')),('phantom',_('Sets / Phantom')),('ebom',_('Engineering BoM')),('spbom',_('Spare BoM'))]
SUPERUSER_ID=1

def normalize(value):
    tmpvalue="{value}".format(value=value)
    return tmpvalue.replace('"', '\"').replace("'", '\"').replace("%", "%%").strip()

def getCleanValue(value):
    ret=value.decode() if isinstance(value, bytes) else value
    return ret

def getCleanData(myData):
    ret=None
    if isinstance(myData, dict):
        ret=getCleanBytesDictionary(myData)
    if isinstance(myData, list,tuple):
        ret=getCleanBytesList(myData)
    return ret

def getCleanBytesList(myList=[]):
    ret=[]
    for keyName in myList:
        ret.append(getCleanValue(keyName))
    return ret

def getCleanBytesDictionary(myDict={}):
    ret={}
    if list(set(myDict.keys())):
        for keyName in myDict.keys():
            ret.update({ getCleanValue(keyName): getCleanValue(myDict[keyName]) })
    return ret

def unpackDictionary(bytesString=""):
    ret={}
    if isinstance(bytesString, Binary):
        streamOne=pickle.loads(base64.b64decode(bytesString.data))
    else:
        streamOne=pickle.loads(base64.b64decode(bytesString))
       
    if isinstance(streamOne, list):
        arrayByte=array('B', b'')
        arrayByte.fromlist(streamOne)
        ret=pickle.loads(arrayByte.tostring())
    return ret

def packDictionary(thisDict={}):
    # Serialization and encryption of dictionaries readable from Python 2.3 and above.
    arrayByte=array('B', pickle.dumps(thisDict,2))
    return base64.b64encode(pickle.dumps(arrayByte.tolist(),2))

def getListedDatas(item):
    results=[]
    if item:
        if isinstance(item, (list,tuple)):
            for singleItem in item:
                if singleItem:
                    if isinstance(singleItem, (list,tuple)):
                        results.extend(list(set(singleItem)))
                    else:
                        results=getListIDs(singleItem)
        else:
            results=getListIDs(item)
    return results

def getListIDs(item):
    results=[]
    if item:
        if isinstance(item, (list,tuple)):
            results=list(set(item))
        else:
            results=[item]
    return results

def getIDs(item):
    results=[]
    if item:
        if isinstance(item, (list,tuple)):
            for singleItem in item:
                results.append(singleItem.id)
        else:
            results=getListIDs(item.id)
    return results

def getCleanList(item):
    return list(set(getListIDs(item)))

def getInteger(value=''):
    """
        Returns an integer number using digit contained in a string
    """
    numvalue=0
    tmpnum='0'
    for iChar in str(value):
        if iChar.isdigit():
            tmpnum+=iChar
        numvalue=int(tmpnum)
    return numvalue

#   WorkFlow common internal method to apply changes
def signal_workflow(entity, cr, uid, ids, signal):
    """
        Emits workflow signal as requested.
    """
    ret=False
    if signal:
        ret=True
        wf_service = netsvc.LocalService("workflow")
        for idd in getListIDs(ids):
            wf_service.trg_validate(uid, entity._name, idd, signal, cr)
    return ret

def get_signal_workflow(self, cr, uid, entity, status="", context=None):
    signal=""
    instanceType=self.pool.get('workflow.instance')
    activityType=self.pool.get('workflow.activity')
    workitemType=self.pool.get('workflow.workitem')
    transitionType=self.pool.get('workflow.transition')
    instIds=instanceType.search(cr, uid, [("res_id", "=", entity.id),("res_type", "=", entity._name)], context=context)
    for instance in instanceType.browse(cr, uid, instIds, context=context):
        wkitemFromIds=workitemType.search(cr, uid, [("inst_id", "=", instance.id)], context=context)

        for workitem in workitemType.browse(cr, uid, wkitemFromIds, context=context):
            idFrom=workitem.act_id.id
            actIdTos=activityType.search(cr, uid, [("wkf_id", "=", instance.wkf_id.id),("name", "=", status)], context=context)
            if isinstance(actIdTos, list):                        
                for idTo in actIdTos:
                    transIds=transitionType.search(cr, uid, [("act_to","=", idTo)], context=context)
                    for transition in transitionType.browse(cr, uid, transIds, context=context):
                        if transition.act_from.id==idFrom:
                            signal=transition.signal
                            break
    return signal

def move_workflow(entity, cr, uid, ids, signal="", status="", context=None):
    """
        Emits workflow signal as requested.
    """
    if signal and status:
        context = context or entity.pool['res.users'].context_get(cr, uid)
        context['internal_writing']=True
        if signal_workflow(entity, cr, uid, ids, signal):
            entity.write(cr, uid, ids, {'state': status}, context=context)
            entity.logging_workflow(cr, uid, ids, signal, status, context=context)
  
def isAdministrator(entity, cr, uid, context=None):
    """
        Checks if this user is in PLM Administrator group
    """
    ret = False
    context = context or entity.pool['res.users'].context_get(cr, uid)
    groupType=entity.pool['res.groups']
    for gId in groupType.search(cr, uid, [('name', '=', 'PLM / Administrators')], context=context):
        for user in groupType.browse(cr, uid, gId, context=context).users:
            if uid == user.id or uid==SUPERUSER_ID:
                ret = True
                break
    return ret

def isInStatus(entity, cr, uid, idd, status=[], context=None):
    """
        Check if a document is in one of a list of statuses. 
    """
    ret=False
    context = context or entity.pool['res.users'].context_get(cr, uid)
    for document in entity.browse(cr, uid, getListIDs(idd), context=context):
        try:
            if (document.state in getListIDs(status)):
                ret=ret|True
                break
        except:
            pass
    return ret

def isObsoleted(entity, cr, uid, idd, context=None):
    """
        Check if a document is released
    """
    return isInStatus(entity, cr, uid, idd, status=["obsoleted"], context=None)

def isUnderModify(entity, cr, uid, idd, context=None):
    """
        Check if a document is released
    """
    return isInStatus(entity, cr, uid, idd, status=["undermodify"], context=None)

def isReleased(entity, cr, uid, idd, context=None):
    """
        Check if a document is in 'released' state. 
    """
    return isInStatus(entity, cr, uid, idd, status=["released"], context=None)

def isAnyReleased(entity, cr, uid, idd, context=None):
    """
        Check if a document is in 'released' state. 
    """
    return isInStatus(entity, cr, uid, idd, status=["released","undermodify","obsoleted"], context=None)

def isDraft(entity, cr, uid, idd, context=None):
    """
        Check if a document is in 'draft' state. 
    """
    return isInStatus(entity, cr, uid, idd, status=["draft"], context=None)