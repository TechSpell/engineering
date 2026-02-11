# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2020-2025 Codebeex srl (<http://www.codebeex.com>). All Rights Reserved
#    
#    Created on : 2025-12-22
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
from .common import moduleName
from copy import deepcopy

openerpModule=moduleName()


class plm_check_bom(osv.osv.osv_memory):
    _name = "plm.check.bom"
    _description = "Products to be checked"
    
    temp_id         =   fields.Many2one ('plm.temporary', index=True,               string=_('Replace Check'),  ondelete='cascade')
    bom_id          =   fields.Many2one ('mep.bom', index=True,                     string=_('Bom'),            ondelete='cascade')
    part_id         =   fields.Many2one ('product.template', index=True,            string=_('Father'),         ondelete='cascade')
    name            =   fields.Char     (related="part_id.name",                    string=_("BoM Product"),    store=False)
    revision        =   fields.Integer  (related="part_id.engineering_revision",    string=_("Revision"),       store=False)
    status          =   fields.Selection(related="part_id.state",                   string=_("Status"),         store=False)
    description     =   fields.Html     (related="part_id.description",             string=_("Description"),    store=False)
    reason          =   fields.Char     (string=_("Notes"),                                                                )
    level           =   fields.Integer  (string=_("Level"),                                                                )
    child_id        =   fields.Many2one ('product.product', index=True,             string=_('Child'),          ondelete='cascade')
    ch_name         =   fields.Char     (related="child_id.name",                   string=_("ChildProduct"),   store=False)
    ch_revision     =   fields.Integer  (related="child_id.engineering_revision",   string=_("Revision"),       store=False)
    ch_status       =   fields.Selection(related="child_id.state",                  string=_("Status"),         store=False)
    ch_description  =   fields.Html     (related="child_id.description",            string=_("Description"),    store=False)
    ch_reason       =   fields.Char     (string=_("Notes"),                                                                )
    choice          =   fields.Boolean  (string=_("Choice"),                                                               )
    discharge       =   fields.Boolean  (string=_("Discharge"),                     default=False                          )
    notallowalble   =   fields.Boolean  (string=_("Not Allowalble"),                default=False                          )


class plm_temporary(osv.osv.osv_memory):
    _inherit = "plm.temporary"
    _description = "Temporary Class"

    ch_bom_ids      =   fields.One2many ('plm.check.bom',  'temp_id',     index=True, string=_('Boms in which to replace products')   )

    def action_replace_normalBom(self):
        """
            Replaces a product (and only one) in any chosen Normal Bom.
            Avoids replacements in obsoleted Bom or with obsoleted/undermodify products.
        """
        ret=False
        tempType = self.env["plm.temporary"]
        product_ids = product_id = self.env['product.product']
        father_ids = self.env['mrp.bom']
        part_ids = checkProductType = self.env["plm.check.product"]
        ch_bom_ids = checkBomType = self.env["plm.check.bom"]
        
        if 'active_ids' in self._context:
            product_ids = self.env['product.product'].browse(self._context['active_ids'])
        if 'my_product_id' in self._context:
            product_ids = self.env['product.product'].browse(self._context['my_product_id'])
        if product_ids:
            product_id = product_ids[0]
            old_ids = product_id._getpreviousrevisions()
            if old_ids:
                father_ids = old_ids._getinboms()                            

        if product_id and father_ids:
            name_operation = _('Checking Bom Replacement')
            tmp_id = tempType.create({'name': name_operation})
            if tmp_id:
                context = dict(self.env.context or {})
                context.update({
                    'active_id': tmp_id.id,
                    'rp_part_id': product_id.id
                    })
                part_discharge = False
                values = {
                    'part_id': product_id.id,
                    'temp_id': tmp_id.id,
                    }
                if product_id.state in ('obsoleted','undermodify'):
                    part_discharge = True
                    values.update({
                        'discharge': part_discharge,
                        'reason': _('Chosen product is Obsoleted or Under Modify.'),
                        })
                values.update({
                    'choice': not part_discharge,
                    })
                part_ids += checkProductType.create(values)
                
                for father_id in father_ids:
                    product_tmpl_id = father_id.product_tmpl_id
                    discharge = part_discharge
                    values = {
                        'bom_id': father_id.id,
                        'part_id': product_tmpl_id.id,
                        'temp_id': tmp_id.id,
                        }

                    if product_tmpl_id.state in ('obsoleted','undermodify'): 
                        discharge = True
                        values.update({
                            'notallowalble': discharge,
                            'reason': _('Father product is not in allowable status.'),
                            })
                    values.update({
                        'choice': not discharge,
                        })
                    cldvalues = deepcopy(values)
                    for line in father_id.bom_line_ids:
                        discharge = False
                        if line.product_id.name == product_id.name:
                            cldvalues.update({
                            'child_id': line.product_id.id,
                            })
                            if line.product_id.state in ('obsoleted','undermodify'): 
                                discharge = True
                                values.update({
                                    'notallowalble': discharge,
                                    'ch_reason': _('Child product is not in allowable status.'),
                                    })
                            ch_bom_ids += checkBomType.create(cldvalues)

                view_name = "{}.plm_replace_bom_form_view".format(openerpModule)
                    
                return {
                    'domain': [],
                    'name': name_operation,
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'plm.temporary',
                    'res_id': tmp_id.id,
                    'view_id': self.env.ref(view_name).id,
                    'type': 'ir.actions.act_window',
                }
        return ret

    def action_replacement_apply(self):
        """
            Action to be executed to execute replacement operations.
            Launched from plm.temporary form
        """
        if self.part_ids and self.ch_bom_ids:
            product_id = self.part_ids[0].part_id
            bomLineType = self.env["mrp.bom.line"]
            bomType = self.env["mrp.bom"]
            
            for ch_bom_id in self.ch_bom_ids:
                if ch_bom_id.choice and ch_bom_id.bom_id:
                    bom_id = bomType.browse(ch_bom_id.bom_id.ids[0])
                    if bom_id:
                        flag = False
                        note = "Replaced:"
                        criteria = [('bom_id','=', bom_id.id)]
                        for child_id in bomLineType.search(criteria):
                            if child_id.product_id == ch_bom_id.child_id:
                                child_id.product_id = product_id
                                note += _(" position {} {}-{} with {}-{}".format(child_id.sequence, ch_bom_id.ch_name, ch_bom_id.ch_revision, product_id.name, product_id.engineering_revision))
                                flag = True
                        if flag:
                            bom_id.message_post(body=_(note))
