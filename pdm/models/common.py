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
from datetime import datetime

import openerp.netsvc as netsvc
from openerp import  SUPERUSER_ID, _

BOMTYPES=[('normal',_('Normal BoM')),('phantom',_('Sets / Phantom')),('ebom',_('Engineering BoM')),('spbom',_('Spare BoM'))]

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

def getUpdTime(obj):
    if(obj.write_date!=False):
        return datetime.strptime(obj.write_date,'%Y-%m-%d %H:%M:%S')
    else:
        return datetime.strptime(obj.create_date,'%Y-%m-%d %H:%M:%S')

def streamPDF(bytesString=""):
    ret=""
    if isinstance(bytesString, Binary):
        ret=base64.b64encode(bytesString.data)
    else:
        ret=base64.b64encode(bytesString)
    return ret

def unpackDictionary(bytesString=""):
    ret={}
    if isinstance(bytesString, Binary):
        ret=pickle.loads(base64.b64decode(bytesString.data))
    else:
        ret=pickle.loads(base64.b64decode(bytesString))
    return ret

def packDictionary(thisDict={}):
    # Serialization and encryption of dictionaries readable from Python 2.3 and above.
    return base64.b64encode(pickle.dumps(thisDict,2))

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
            results=getListIDs(item.ids)
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
def signal_workflow(entity, ids, signal):
    """
        Emits workflow signal as requested.
    """
    ret=False
    if signal:
        ret=True
        wf_service = netsvc.LocalService("workflow")
        for idd in getListIDs(ids):
            wf_service.trg_validate(entity._uid, entity._name, idd, signal, entity._cr)
    return ret

def get_signal_workflow(entity, status=""):
    signal=""
    cr=entity._cr
    uid=entity._uid
    context = entity.pool['res.users'].context_get(cr, uid)
    instanceType=entity.pool.get('workflow.instance')
    activityType=entity.pool.get('workflow.activity')
    workitemType=entity.pool.get('workflow.workitem')
    transitionType=entity.pool.get('workflow.transition')
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

def move_workflow(entity, ids, signal, status):
    """
        Emits workflow signal as requested.
    """
    if signal and status:
        if signal_workflow(entity, ids, signal):
            entity.browse(ids).with_context({'internal_writing':True}).write( {'state': status} )
            entity.logging_workflow(ids, signal, status)

def wf_message_post(entity, ids=[], body=""):
    """
        Writing messages to follower, on multiple objects
    """
    if not (body==""):
        for objItem in entity.browse(ids):
            objItem.message_post(body=_(body))

def isAdministrator(entity):
    """
        Checks if this user is in PLM Administrator group
    """
    ret = False
    groupType=entity.env['res.groups']
    for gId in groupType.search([('name', '=', 'PLM / Administrators')]):
        for user in gId.users:
            if entity._uid == user.id or entity._uid==SUPERUSER_ID:
                ret = True
                break
    return ret

def isIntegratorUser(entity):
    """
        Checks if this user is in PLM Administrator group
    """
    ret = False
    groupType=entity.env['res.groups']
    for gId in groupType.search([('name', '=', 'PLM / Integration Users')]):
        for user in gId.users:
            if entity._uid == user.id:
                ret = True
                break
    return ret

def isInStatus(entity, idd, status=[]):
    """
        Check if a document is released
    """
    ret=False
    for document in entity.browse(getListIDs(idd)):
        try:
            if (document.state in getListIDs(status)):
                ret=ret|True
                break
        except:
            pass
    return ret

def isWritable(entity, idd):
    """
        Check if a document is released
    """
    ret=True
    for item_id in entity.browse(getListIDs(idd)):
        try:
            if not item_id._iswritable():
                ret=False
                break
        except:
            pass
    return ret

def isObsoleted(entity, idd):
    """
        Check if a document is released
    """
    return isInStatus(entity, idd, status=["obsoleted"])

def isUnderModify(entity, idd):
    """
        Check if a document is released
    """
    return isInStatus(entity, idd, status=["undermodify"])

def isOldReleased(entity, idd):
    """
        Check if a document is in 'released' state. 
    """
    return isInStatus(entity, idd, status=["undermodify","obsoleted"])

def isReleased(entity, idd):
    """
        Check if a document is in 'released' state. 
    """
    return isInStatus(entity, idd, status=["released"])

def isAnyReleased(entity, idd):
    """
        Check if a document is in 'released' state. 
    """
    return isInStatus(entity, idd, status=["released","obsoleted"])

def isDraft(entity, idd):
    """
        Check if a document is in 'draft' state. 
    """
    return isInStatus(entity, idd, status=["draft"])

def getMachineStorage(repository="/", unit="G"):
    if sys.version_info >= (3, 3):
        total, used, free = shutil.disk_usage(repository)
    else:
        result=os.statvfs(repository)
        block_size=result.f_frsize
        total=result.f_blocks*block_size
        free=result.f_bavail*block_size
    rate=2**30
    ratio=0
    uom="Gb"
    if unit.upper()=="M":
        rate=2**20
        uom="Mb"
    elif unit.upper()=="K":
        rate=2**10
        uom="Kb"
    total_size=int(total/rate)
    free_size=int(free/rate)
    if total_size>0:
        ratio=int(100*(float(free_size)/float(total_size)))
    ltot='total_size = %s %s' %(total_size, uom)
    lfre='free_size = %s %s' %(free_size, uom)
    lrat='ratio = %s%%' %(ratio)
    return ((total_size,free_size,ratio),(ltot,lfre,lrat))
