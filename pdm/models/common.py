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
from xmlrpc.client import Binary
from datetime import datetime

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
    ret=""
    if isinstance(bytesString, Binary):
        ret=base64.b64encode(bytesString.data)
    else:
        ret=base64.b64encode(bytesString)
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
        ret=pickle.loads(arrayByte.tostring(), encoding="bytes")
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

def getUser(entity=None, uid=False):
    """
        Gets the user login, name and signature
    """
    ret=None
    if not(entity==None) and uid:
        for uiUser in entity.env['res.users'].browse([uid]):
            ret=uiUser
            break
    return ret

def getUserName(entity=None, uid=False):
    """
        Gets the user login, name and signature
    """
    ret=""
    uiUser=getUser(entity, uid)
    if uiUser:
        ret=uiUser.name
    return ret

def isinstalled_module(entity, module_name):
    ret=False
    entyModule=entity.env['ir.module.module'].sudo()
    criteria=[('name', '=', module_name.replace("module_", ''))]
    modules = entyModule.search( criteria )
    for module in  modules:
        if module.state.lower()=='installed':
            ret=True
            break
    return ret
    
    
#   WorkFlow common internal method to apply changes

def move_workflow(entity, idEntities, transition_name="", final_status=""):
    """
        Executes workflow as requested by reaching the final status.
    """
    ret=[]
    if idEntities:
        entity_ids=entity.browse(idEntities)
        if isinstalled_module(entity, 'module_wkf'):
            ret=entity.env['wkf.tools'].MoveWorkflow(entity_ids, transition_name, final_status)
        else:
            for entity_id in entity_ids:
                entity_id.with_context({'internal_writing':True}).write( {'state': final_status})
                entity_id.logging_workflow(entity_id.id, transition_name, final_status)
    return ret


#   WorkFlow common methods

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