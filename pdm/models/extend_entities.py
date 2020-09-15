# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2016 TechSpell srl (<http://techspell.eu>). All Rights Reserved
#    
#    Created on : 2016-03-01
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

import time

from openerp import models, fields, api, _, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT


class plm_document(models.Model):
    _inherit = 'plm.document'

    linkedcomponents    =   fields.Many2many('product.product', 'plm_component_document_rel','document_id','component_id', string=_('Linked Parts'))

    _defaults = {
                 'state': lambda *a: 'draft',
                 'res_id': lambda *a: False,
    }    


class plm_component(models.Model):
    _inherit = 'product.product'

    @api.multi
    def _father_part_compute(self):
        """ 
            Gets father BoM.
        """
        prod_ids=[]
        ids=self._ids
        for prod_obj in self.env['product.product'].browse(ids):
            for bom_line_obj in self.env['mrp.bom.line'].search([('product_id','=',prod_obj.id)]):                
                prod_ids.extend([bom_line_obj.bom_id.product_id.id])
            prod_obj.father_part_ids=list(set(prod_ids))

    linkeddocuments = fields.Many2many  ('plm.document', 'plm_component_document_rel','component_id','document_id', _('Linked Docs'))  
    tmp_material    = fields.Many2one   ('plm.material',_('Raw Material'), required=False, change_default=True, help=_("Select raw material for current product"))
    #tmp_treatment   = fields.Many2one('plm.treatment',_('Thermal Treatment'), required=False, change_default=True, help=_("Select thermal treatment for current product"))
    tmp_surface     = fields.Many2one   ('plm.finishing',_('Surface Finishing'), required=False, change_default=True, help=_("Select surface finishing for current product"))
    father_part_ids = fields.Many2many  ('product.product', compute = _father_part_compute, string=_("BoM Hierarchy"), store =False)

    @api.onchange('tmp_material')
    def on_change_tmpmater(self):
        values={'engineering_material':''}
        if self.tmp_material:
            thisMaterial=self.env['plm.material']
            thisObject=thisMaterial.browse(self.tmp_material.id)
            if thisObject.name:
                values['engineering_material']="{name}".format(name=thisObject.name)
                self.engineering_material=values['engineering_material']
        return {'value': {'engineering_material':values['engineering_material']}}

#     @api.onchange('tmp_treatment')
#     def on_change_tmptreatment(self):
#         values={'engineering_treatment': ''}
#         if self.tmp_treatment:
#             thisTreatment=self.env['plm.treatment']
#             thisObject=thisTreatment.browse(self.tmp_treatment.id)
#             if thisObject.name:
#                 values['engineering_treatment']="{name}".format(name=thisObject.name)
#                 self.engineering_treatment=values['engineering_treatment']
#         return {'value': {'engineering_treatment':values['engineering_treatment']}}

    @api.onchange('tmp_surface')
    def on_change_tmpsurface(self):
        values={'engineering_surface': ''}
        if self.tmp_surface:
            thisSurface=self.env['plm.finishing']
            thisObject=thisSurface.browse(self.tmp_surface.id)
            if thisObject.name:
                values['engineering_surface']="{name}".format(name=thisObject.name)
                self.engineering_surface=values['engineering_surface']
        return {'value': {'engineering_surface':values['engineering_surface']}}

    @api.multi
    def _father_compute(self):
        """ 
            Gets father BoM.
        """
        prod_ids={}
        for prod_obj in self.env['product.product'].browse(self._ids):
            prodIDs=[]
            for bom_line_obj in self.env['mrp.bom.line'].search([('product_id','=',prod_obj.id)]): 
                if not bom_line_obj.bom_id.product_id:
                    product=self.getFromTemplateID(bom_line_obj.bom_id.product_tmpl_id.id)
                    if product:
                        prodIDs.append(product.id)
                else:            
                    prodIDs.append(bom_line_obj.bom_id.product_id.id)
            prod_ids[prod_obj.id]=list(set(prodIDs))
        return prod_ids

    def recurse_father_part_compute(self, productIDs=[]):
        """ Gets all fathers of a product (extended to top level, flat list).
        @param self: The object pointer
        @param cr: The current row, from the database cursor,
        @param uid: The current user ID for security checks
        @param ids: List of selected IDs
        @param context: A standard dictionary for contextual values
        @return:  Dictionary of values
        """
        result={}
        if not self.alreadyListed:
            self.alreadyListed=[]
        for prod_obj in self.browse(productIDs):
            prod_ids=[]
            if not(prod_obj.id in self.alreadyListed):
                self.alreadyListed.append(prod_obj.id)
                tmp_ids=prod_obj._father_compute()
                if tmp_ids:
                    prod_ids.extend(tmp_ids[prod_obj.id])
                    for prodObject in self.browse(tmp_ids[prod_obj.id]):
                        bufIDs=self.recurse_father_part_compute([prodObject.id])
                        prod_ids.extend(bufIDs[prodObject.id])
            result[prod_obj.id]=list(set(prod_ids))
        return result

class plm_relation(models.Model):
    _inherit = 'mrp.bom'

#######################################################################################################################################33

#   Overridden methods for this entity

    def _bom_find(self, cr, uid, product_tmpl_id=None, product_id=None, properties=None, bomType='normal', context=None):
        """ Finds BoM for particular product and product uom.
        @param product_tmpl_id: Selected product.
        @param product_uom: Unit of measure of a product.
        @param properties: List of related properties.
        @return: False or BoM id.
        """
        if not context:
            context = {}
        if properties is None:
            properties = []
        domain = ['&',('type', '=', bomType)]
#
        if product_id:
            if not product_tmpl_id:
                product_tmpl_id = self.env['product.product'].browse(cr, uid, product_id, context=context).product_tmpl_id.id
            domain = domain +[
                '|',
                    ('product_id', '=', product_id),
                    '&',
                        ('product_id', '=', False),
                        ('product_tmpl_id', '=', product_tmpl_id)
            ]
        elif product_tmpl_id:
            domain = domain +[('product_id', '=', False), ('product_tmpl_id', '=', product_tmpl_id)]
        else:
            # neither product nor template, makes no sense to search
            return False
        if context.get('company_id'):
            domain = domain + [('company_id', '=', context['company_id'])]
        domain = domain + [ '|', ('date_start', '=', False), ('date_start', '<=', time.strftime(DEFAULT_SERVER_DATE_FORMAT)),
                            '|', ('date_stop', '=', False), ('date_stop', '>=', time.strftime(DEFAULT_SERVER_DATE_FORMAT))]
        # order to prioritize bom with product_id over the one without
        ids = self.search(cr, uid, domain, order='sequence, product_id', context=context)
        # Search a BoM which has all properties specified, or if you can not find one, you could
        # pass a BoM without any properties with the smallest sequence
        bom_empty_prop = False
        for bom in self.pool['mrp.bom'].browse(cr, uid, ids, context=context):
            if not set(map(int, bom.property_ids or [])) - set(properties or []):
                if not properties or bom.property_ids:
                    return bom.id
                elif not bom_empty_prop:
                    bom_empty_prop = bom.id
        return bom_empty_prop
     
#######################################################################################################################################33

    @api.one
    def _father_compute(self):
        """ Gets father bom.
        @param self: The object pointer
        @param cr: The current row, from the database cursor,
        @param uid: The current user ID for security checks
        @param ids: List of selected IDs
        @param name: Name of the field
        @param arg: User defined argument
        @param context: A standard dictionary for contextual values
        @return:  Dictionary of values
        """
        bom_type=''
        result = []
        ids=self._ids
        bom_objType = self.env['mrp.bom']
        bom_line_objType = self.env['mrp.bom.line']
        bom_objs = bom_objType.browse(ids)
        for bom_obj in bom_objs:
            bom_type=bom_obj.type
            if bom_type=='':
                criteria = [('product_id','=',bom_obj.product_id.id)]
            else:
                criteria = [('product_id','=',bom_obj.product_id.id),('type','=',bom_type)]
        
            for bom_child in bom_line_objType.search(criteria):
                if bom_child.bom_id.id:
                    if not(bom_child.bom_id.id in result):
                        result.append(bom_child.bom_id.id)
        self.father_complete_ids=result
 
    state                   = fields.Selection  (related="product_id.state",                string=_("Status"),     help=_("The status of the product in its LifeCycle."),  store=False)
    engineering_revision    = fields.Integer    (related="product_id.engineering_revision", string=_("Revision"),   help=_("The revision of the product."),                 store=False)
    description             = fields.Text       (related="product_id.description",          string=_("Description"),                                                        store=False)
    father_complete_ids     = fields.Many2many  ('mrp.bom.line', compute=_father_compute,   string=_("BoM Hierarchy"),                                                      store=False)


class plm_relation_line(models.Model):
    _name = 'mrp.bom.line'
    _inherit = 'mrp.bom.line'
    _order = "itemnum"

    def _get_child_bom_lines(self):
        """
            If the BOM line refers to a BOM, return the ids of the child BOM lines
        """
        bom_obj = self.env['mrp.bom']
        ids=self._ids
        res = {}
        for bom_line in self.browse(ids):
            bom_id = bom_obj._bom_find(product_tmpl_id=bom_line.product_id.product_tmpl_id.id,
                product_id=bom_line.product_id.id, bomType=bom_line.type)
            if bom_id:
                child_bom = bom_obj.browse(bom_id)
                res[bom_line.id] = [x.id for x in child_bom.bom_line_ids]
            else:
                res[bom_line.id] = False
        return res

    state                   =   fields.Selection    (related="product_id.state",                string=_("Status"),     help=_("The status of the product in its LifeCycle."),  store=False)
    engineering_revision    =   fields.Integer      (related="product_id.engineering_revision", string=_("Revision"),   help=_("The revision of the product."),                 store=False)
    description             =   fields.Text         (related="product_id.description",          string=_("Description"),                                                        store=False)
    weight                  =   fields.Float        (related="product_id.weight",               string=_("Weight Net"),                                                         store=False)
    child_line_ids          =   fields.One2many     ("mrp.bom.line",compute=_get_child_bom_lines,string=_("BOM lines of the referred bom"),                                     store=False)


class plm_checkout(models.Model):
    _inherit = 'plm.checkout'

    name                =   fields.Char     (related="documentid.name",         string=_("Document"),       store=False)

class plm_backupdoc(models.Model):
    _inherit = 'plm.backupdoc'

    name                =   fields.Char     (related="documentid.name",         string=_("Document"),       store=False)


class plm_document_relation(models.Model):
    _inherit = 'plm.document.relation'

    def _get_parents(self, lines=None):
        """
            If the BOM line refers to a BOM, return the ids of the child BOM lines
        """
        ids=[]
        for line_id in lines:
            criteria=[('parent_id', '=', line_id.parent_id.id)]
            for father_id in self.search( criteria ):
                ids.append(father_id.id)
        return self.browse(list(set(ids)))


    def _get_children(self, line_ids=None):
        """
            If the BOM line refers to a BOM, return the ids of the child BOM lines
        """
        ids=[]
        for line_id in line_ids:
            ids.append(line_id.child_id.id)
        criteria=[('parent_id', 'in', list(set(ids)))]
        return self.search( criteria )

    @api.one
    def _get_children_lines(self, lines=None):
        res = []
        for line_id in self.browse(self._ids):
            parents=self._get_parents(line_id)
            children=self._get_children(parents)
            res.extend(children._ids)
        self.child_line_ids = list(set(res))


    def _get_fathers(self, lines=None):
        ids=[]
        for line_id in lines:
            criteria=[('child_id', '=', line_id.parent_id.id),('link_kind', 'in', ['HiTree'])]
            for child_id in self.search( criteria ):
                ids.append(child_id.id)
        return self.browse(list(set(ids)))
        
    @api.one
    def _get_fathers_lines(self):
        res = []
        for line_id in self.browse(self._ids):
            parents=self._get_fathers(line_id)
            res.extend(parents._ids)
        self.father_line_ids = list(set(res))
 
    name                =   fields.Char     (related="parent_id.name",          string=_("Document"),       store=False)
    parent_preview      =   fields.Binary   (related="parent_id.preview",       string=_("Preview"),        store=False)
    parent_state        =   fields.Selection(related="parent_id.state",         string=_("Status"),         store=False)
    parent_revision     =   fields.Integer  (related="parent_id.revisionid",    string=_("Revision"),       store=False)
    parent_checkedout   =   fields.Char     (related="parent_id.checkout_user", string=_("Checked-Out To"), store=False)
    child_preview       =   fields.Binary   (related="child_id.preview",        string=_("Preview"),        store=False)
    child_state         =   fields.Selection(related="child_id.state",          string=_("Status"),         store=False)
    child_revision      =   fields.Integer  (related="child_id.revisionid",     string=_("Revision"),       store=False)
    child_checkedout    =   fields.Char     (related="child_id.checkout_user",  string=_("Checked-Out To"), store=False)
    child_line_ids      =   fields.One2many ("plm.document.relation", compute=_get_children_lines,   string=_("Documents related as children"), store=False)
    father_line_ids     =   fields.One2many ('plm.document.relation', compute=_get_fathers_lines,    string=_("Documents related as fathers"),  store=False)

