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

from odoo import models, fields, api, _, osv
from odoo.exceptions import UserError

RETDMESSAGE=''

class plm_temporary(osv.osv.osv_memory):
    _inherit = "plm.temporary"

    name          = fields.Char       (  string=_('Part Number'), size=64)

    ##  Specialized Actions callable interactively
    def action_create_spareBom(self):
        """
            Create a new Spare BoM if doesn't exist (action callable from views)
        """
        if not 'active_id' in self._context:
            return False
        if not 'active_ids' in self._context:
            return False
        
        
        productType=self.env['product.product']
        bomType=self.env['mrp.bom']
        for idd in self._context['active_ids']:
            checkObj=productType.browse(idd)
            if not checkObj:
                continue
            criteria=[('product_tmpl_id','=',idd),('type','=','spbom'),('active','=',True)]
            objBoms=bomType.search( criteria )
            if objBoms:
                raise UserError(_("Creating a new Spare BoM Error.\n\nBoM for Part {} already exists.".format(checkObj.name)))

        productType.with_context(
                {"update_latest_revision": self.revflag}
                ).create_spareBom_WF(self._context['active_ids'])

        return {
            'name': _('Bill of Materials'),
            'view_type': 'form',
            "view_mode": 'tree,form',
            'res_model': 'mrp.bom',
            'type': 'ir.actions.act_window',
            'domain': "[('product_id','in', [" + ','.join(map(str, self._context['active_ids'])) + "])]",
        }


class plm_component(models.Model):
    _inherit = 'product.product'

    #  Work Flow Actions
    def create_spareBom_WF(self, ids=[]):
        """
            Create a new Spare BoM if doesn't exist (action callable from code)
        """
        
        for idd in ids:
            processedIds=[]
            self._create_spareBom(idd, processedIds=processedIds)
        return False

    #   Internal methods
    def _create_spareBom(self, idd=False, processedIds=[]):
        """
            Create a new Spare BoM (recursive on all EBom children)
        """
        newidBom=False
        
        if idd in processedIds:
            return False
        processedIds.append(idd)
        checkObj=self.browse(idd)
        if not checkObj:
            return False
        if '-Spare' in checkObj.name:
            return False
        sourceBomType = self._context.get('sourceBomType', 'ebom')
        bomType=self.env['mrp.bom']
        objBoms=bomType.search([('product_id', '=', idd), ('type', '=', 'spbom'), ('active', '=', True)])
        idBoms=bomType.search([('product_id', '=', idd), ('type', '=', 'normal'), ('active', '=', True)])
        if not idBoms:
            idBoms=bomType.search([('product_tmpl_id','=',checkObj.product_tmpl_id.id),('type','=',sourceBomType)])

        defaults={'product_tmpl_id': checkObj.product_tmpl_id.id,'product_id': checkObj.id, 'type': 'spbom', 'active': True,}
        if not objBoms:
            if checkObj.std_description.bom_tmpl:
                newidBom = checkObj.std_description.bom_tmpl.with_context({'internal_writing':True}).copy()
            if (not newidBom) and idBoms:
                newidBom=idBoms[0].with_context({'internal_writing':True}).copy(defaults)
            if newidBom:
                newidBom.with_context({'internal_writing':True}).write(defaults)
                ok_rows=self._summarizeBom(newidBom.bom_line_ids)
                for bom_line in list(set(newidBom.bom_line_ids) ^ set(ok_rows)):
                    bom_line.unlink()
                for bom_line in ok_rows:
                    bom_line.with_context({'internal_writing':True}).write( 
                                {'type': 'spbom', 'source_id': False, 
                                 'product_qty': bom_line.product_qty, } )
                    self._create_spareBom(bom_line.product_id.id, processedIds=processedIds)
        else:
            for bom_line in objBoms[0].bom_line_ids:
                self._create_spareBom(bom_line.product_id.id, processedIds=processedIds)
        return False


class plm_description(models.Model):
    _inherit = "plm.description"

    bom_tmpl    =   fields.Many2one('mrp.bom',_('Choose a BoM'), index=True, required=False, change_default=True, help=_("Select a  BoM as template to drive building Spare BoM."))

    _defaults = {
        'bom_tmpl': lambda *a: False,
    }

# Introduced relationship with mrp.bom to implement Spare Part Bom functionality
