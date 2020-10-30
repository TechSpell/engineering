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

import re
import base64
import pickle
from array import array
from xmlrpclib import Binary
from datetime import datetime

import odoo.netsvc as netsvc
from odoo import  SUPERUSER_ID, _

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
    if isinstance(bytesString, Binary):
        dump = bytesString.data
    else:
        dump = bytesString
    return base64.b64encode(dump)

def unpackDictionary(bytesString=""):
    ret={}
    if isinstance(bytesString, Binary):
        dump = bytesString.data
    else:
        dump = bytesString
    tmp=base64.b64decode(dump)
    if isinstance(tmp, bytes):
        ret=pickle.loads(tmp, encoding="bytes")
    elif isinstance(tmp, str):
        ret=pickle.loads(tmp)
    return ret

def packDictionary(thisDict={}):
    # Serialization and encryption of dictionaries readable from Python 2.3 and above.
    dump = pickle.dumps(thisDict,2)
    return base64.b64encode(dump)

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
    instanceType=entity.env['workflow.instance']
    activityType=entity.env['workflow.activity']
    workitemType=entity.env['workflow.workitem']
    transitionType=entity.env['workflow.transition']
    for instance in instanceType.search( [("res_id", "=", entity.id),("res_type", "=", entity._name)] ):
        for workitem in workitemType.search( [("inst_id", "=", instance.id)] ):
            idFrom=workitem.act_id.id
            for idTo in activityType.search( [("wkf_id", "=", instance.wkf_id.id),("name", "=", status)] ):
                for transition in transitionType.search( [("act_to","=", idTo.id)] ):
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

def getString(txtValue="", lower=False, upper=False, capitalize=False):
    ret=""
    tmpval=txtValue if not(txtValue==None) else ""
    if isinstance(txtValue, (str,bytes)):
        if (isinstance(txtValue, str)):
            tmpval=txtValue
        elif (isinstance(txtValue, bytes)):
            tmpval=txtValue.decode("utf-8", 'ignore')
        else:
            tmpval="{value}".format(value=txtValue)
        ret=tmpval.strip()
        if lower or upper or capitalize:
            if lower:
                ret=ret.lower()
            elif upper:
                ret=ret.upper()
            elif capitalize:
                ret=ret.capitalize()
    else:
        ret="{value}".format(value=tmpval).strip()
    txtValue=None
    return ret

def isNotVoid(data2Check):
    ret = True if not(data2Check == None) else False
    if not ret:
        if not(data2Check == None):
            if isinstance(data2Check, str):
                ret = True if not(data2Check in ["",False]) else False
            if isinstance(data2Check, bool):
                ret = True if not(getString(data2Check) in ["True","False"]) else False
            if isinstance(data2Check, int,float):
                subsetChars=r'[^0-9\-]'
                tmpval=re.sub(subsetChars, '', getString(data2Check))
                ret = True if not(tmpval== "") else False
    return ret

def isVoid(data2Check):
    return not( isNotVoid(data2Check))

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
