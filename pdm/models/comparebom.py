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

import os
from odoo import models, fields, api, _, osv

from .common import ORIBOMTYPES, BOMTYPES, moduleName

openerpModule=moduleName()

BOM_SHOW_FIELDS=['Position','Code','Description','Quantity']

# TODO: Remember to adequate views for added/missing entities changing BOM_SHOW_FIELDS.

##############################################################################################################
#    Class plm.compare.bom
###############################################################################################################


class plm_compare_bom(osv.osv.osv_memory):
    _name = "plm.compare.bom"
    _description = "BoM Comparison"
    
    name          = fields.Char       (                                         string=_('Part Number'),          size=64)
    bom_id1       = fields.Many2one   ('mrp.bom',                   index=True, string=_('BoM 1'), required=True, ondelete='cascade')
    type_id1      = fields.Selection  (ORIBOMTYPES+BOMTYPES,                    string=_('BoM Type'))
    part_id1      = fields.Many2one   ('product.product', 'Part',   index=True,                                   ondelete='cascade')
    revision1     = fields.Integer    (related="part_id1.engineering_revision", string=_("Revision"),             store=False)
    description1  = fields.Text       (related="part_id1.description",          string=_("Description"),          store=False)
    bom_id2       = fields.Many2one   ('mrp.bom',                   index=True, string=_('BoM 2'), required=True, ondelete='cascade')
    type_id2      = fields.Selection  (ORIBOMTYPES+BOMTYPES,                    string=_('BoM Type'))
    part_id2      = fields.Many2one   ('product.product', 'Part',   index=True,                                   ondelete='cascade')
    revision2     = fields.Integer    (related="part_id2.engineering_revision", string=_("Revision"),             store=False)
    description2  = fields.Text       (related="part_id2.description",          string=_("Description"),          store=False)
    anotinb       = fields.One2many   ('plm.adding.bom',  'bom_id', index=True, string=_('BoM Adding'))
    bnotina       = fields.One2many   ('plm.missing.bom', 'bom_id', index=True, string=_('BoM Missing'))

    _defaults = {
                 'name': 'x',
    }

    @api.model
    def default_get(self, fields):
        """ To get default values for the object.
        @param fields: List of fields for which we want default values
        @return: A dictionary which of fields with values.
        """
        record_ids = self._context.get('active_ids')
        res={}
        if len(record_ids)>0:
            res['bom_id1'] = record_ids[0]
        if len(record_ids)>1:
            res['bom_id2'] = record_ids[1]

        return res
    
    def action_compare_Bom(self):
        """
            Create a new Spare BoM if doesn't exist (action callable from views)
        """
        ids=self._ids
        if len(ids)<1:
            return False
        
        adding_obj = self.env['plm.adding.bom']
        missing_obj = self.env['plm.missing.bom']
        data_obj = self.env['ir.model.data']

        checkObj=self.browse(ids[0])
        differs, changes = self._compare_Bom(checkObj.bom_id1, checkObj.bom_id2)
        ANotInB, BNotInA = differs
        changesInA, changesInB = changes
        
        defaults={'name':checkObj.bom_id1.product_id.name,'type_id1':checkObj.bom_id1.type,'part_id1':checkObj.bom_id1.product_id.id,'type_id2':checkObj.bom_id2.type,'part_id2':checkObj.bom_id2.product_id.id}
        self.browse(ids).write(defaults)
        
        idList1,objList1,objProd1,dictData1,AminusB = ANotInB
        idList2,objList2,objProd2,dictData2,BminusA = BNotInA
        
        idList3,objList3,objProd3,dictData3,AchangesB = changesInA
        idList4,objList4,objProd4,dictData4,BchangesA = changesInB

        anotinb=[]
        for item in AminusB:
            objBom=objList1[idList1.index(item)]
            objProd=objProd1[idList1.index(item)]
            objectItem=adding_obj.create( {
                'bom_id': checkObj.id,
                'bom_idrow': objBom.id,
                'part_id': objProd.id,
                'reason': "Added",
            })
            if objectItem:
                anotinb.append(objectItem.id)
   

        for item in AchangesB:
            objBom=objList3[idList3.index(item)]
            objProd=objProd3[idList3.index(item)]
            
            objectItem=adding_obj.create( {
                'bom_id': checkObj.id,
                'bom_idrow': objBom.id,
                'part_id': objProd.id,
                'reason': "Changed",
            })
            if objectItem:
                anotinb.append(objectItem.id)

        bnotina=[]
        for item in BminusA:
            objBom=objList2[idList2.index(item)]
            objProd=objProd2[idList2.index(item)]
            objectItem=missing_obj.create( {
                'bom_id': checkObj.id,
                'bom_idrow': objBom.id,
                'part_id': objProd.id,
                'reason': "Removed",
            })
            if objectItem:
                bnotina.append(objectItem.id)

        for item in BchangesA:
            objBom=objList4[idList4.index(item)]
            objProd=objProd4[idList4.index(item)]
            objectItem=missing_obj.create( {
                'bom_id': checkObj.id,
                'bom_idrow': objBom.id,
                'part_id': objProd.id,
                'reason': "Changed",
            })
            if objectItem:
                bnotina.append(objectItem.id)

        if (len(anotinb)<1 and len(bnotina)<1):
            return False
        
        id3 = data_obj._get_id( openerpModule, 'plm_visualize_diff_form')
        if id3:
            id3 = data_obj.browse( id3).res_id

        ctx={'active_id':ids[0],'active_ids':ids, 'active_model':"plm.compare.bom"}
        return {
            'domain': [],
            'name': _('Differences on BoMs'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'plm.compare.bom',
            'res_id': ids[0],
            'views': [(id3,'form')],
            'type': 'ir.actions.act_window',
         }
 

    def _compare_Bom(self, oid1=False, oid2=False, context={}):
        """
            Create a new Normal Bom (recursive on all EBom children)
        """
        changesA=([],[],[],{},{})
        changesB=([],[],[],{},{})
 
        fields=['name','engineering_revision']                   # Evaluate differences
        boolfields=['name','itemnum','product_qty'] # Evaluate changes

        differs=self._differs_Bom( oid1, oid2, fields)
        changes=self._differs_Bom( oid1, oid2, boolfields)
        if len(differs)<1 and len(changes)<1:
            return ((changesA,changesB),(changesA,changesB))
        
        idList1,objList1,objProd1,dictData1,AminusB = differs[0]
        idList2,objList2,objProd2,dictData2,BminusA = differs[1]

        idList3,objList3,objProd3,dictData3,AchangesB = changes[0]
        idList4,objList4,objProd4,dictData4,BchangesA = changes[1]
        
        changesinA={}
        for item in list(set(AchangesB.keys()) - set(AminusB.keys())):
            changesinA[item]=AchangesB[item]

        changesinB={}
        for item in list(set(BchangesA.keys()) - set(BminusA.keys())):
            changesinB[item]=BchangesA[item]
        if len(changesinA):
            changesA=(idList3,objList3,objProd3,dictData3,changesinA)
        if len(changesinB):
            changesB=(idList4,objList4,objProd4,dictData4,changesinB)
            
        return (differs,(changesA,changesB))

    def _unpackData(self, oid, fields=[]):
        """
            Export data about products and BoM, formatting as required to match.
        """
        idList=[]
        listData=[]
        objList=[]
        objProd=[]
        dictData={}
        if len(oid.bom_line_ids):
            prod_names=list(oid.bom_line_ids[0].product_id._fields.keys())
            bom_names=list(oid.bom_line_ids[0]._fields.keys())
            for bom_line in oid.bom_line_ids:
                idList.append(bom_line.id)
                objList.append(bom_line)
                objProd.append(bom_line.product_id)
                
                row_data={}
                for field in fields:
                    if field in prod_names:
                        row_data[field]=bom_line.product_id[field]
                    if field in bom_names:
                        row_data[field]=bom_line[field]
                        
                if row_data:
                    listData.append(row_data)
                    dictData[bom_line.id]=row_data
        return (idList,listData,objList,objProd,dictData)
    
    def _differs_Bom(self, oid1=False, oid2=False, fields=[]):
        """
            Create a new Normal Bom (recursive on all EBom children)
        """
        defaults={}
        if not oid1 or not oid2 or not fields:
            return False
        bomType=self.env['mrp.bom']

        idList1,listData1,objList1,objProd1,dictData1=self._unpackData( oid1, fields)
        idList2,listData2,objList2,objProd2,dictData2=self._unpackData( oid2, fields)

        index=0
        counted=len(listData1)
        AminusB={}
        while index < counted:
            itemData=listData1[index]
            if not itemData in listData2:
                AminusB[idList1[index]]=itemData
            index+=1
        index=0
        counted=len(listData2)
        BminusA={}
        while index < counted:
            itemData=listData2[index]
            if not itemData in listData1:
                BminusA[idList2[index]]=itemData
            index+=1
        return ((idList1,objList1,objProd1,dictData1,AminusB),(idList2,objList2,objProd2,dictData2,BminusA))


class plm_missing_bom(osv.osv.osv_memory):
    _name = "plm.missing.bom"
    _description = "BoM Missing Objects"
    
    bom_id      =   fields.Many2one ('plm.compare.bom', _('BoM'),      index=True,  ondelete='cascade')
    bom_idrow   =   fields.Many2one ('mrp.bom.line',    _('BoM Line'), index=True,  ondelete='cascade')
    part_id     =   fields.Many2one ('product.product', _('Part'),     index=True,  ondelete='cascade')
    revision    =   fields.Integer  (related="part_id.engineering_revision",string=_("Revision"),           store=False)
    description =   fields.Text     (related="part_id.description",         string=_("Description"),        store=False)
    itemnum     =   fields.Integer  (related="bom_idrow.itemnum",           string=_("CAD Item Position"),  store=False)
    itemqty     =   fields.Float    (related="bom_idrow.product_qty",       string=_("Quantity"),           store=False)
    reason      =   fields.Char     (string=_("Difference"),                size=32)
    
    _defaults = {
    }


class plm_adding_bom(osv.osv.osv_memory):
    _name = "plm.adding.bom"
    _description = "BoM Adding Objects"
    
    bom_id          =   fields.Many2one ('plm.compare.bom', _('BoM'),      index=True, ondelete='cascade')
    bom_idrow       =   fields.Many2one ('mrp.bom.line',    _('BoM Line'), index=True, ondelete='cascade')
    part_id         =   fields.Many2one ('product.product', _('Part'),     index=True, ondelete='cascade')
    revision        =   fields.Integer  (related="part_id.engineering_revision",    string=_("Revision"),          store=False)
    description     =   fields.Text     (related="part_id.description",             string=_("Description"),       store=False)
    itemnum         =   fields.Integer  (related="bom_idrow.itemnum",               string=_("CAD Item Position"), store=False)
    itemqty         =   fields.Float    (related="bom_idrow.product_qty",           string=_("Quantity"),          store=False)
    reason          =   fields.Char     (string=_("Difference"),                    size=32)

    _defaults = {
    }

