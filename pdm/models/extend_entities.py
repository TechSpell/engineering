# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2016-2018 TechSpell srl (<http://techspell.eu>). All Rights Reserved
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
#     tmp_treatment   = fields.Many2one   ('plm.treatment',_('Thermal Treatment'), required=False, change_default=True, help=_("Select thermal treatment for current product"))
    tmp_surface     = fields.Many2one   ('plm.finishing',_('Surface Finishing'), required=False, change_default=True, help=_("Select surface finishing for current product"))
    father_part_ids = fields.Many2many  ('product.product', compute = _father_part_compute, string=_("BoM Hierarchy"), store =False)

    @api.onchange('tmp_material')
    def on_change_tmpmater(self, tmp_material=False):
        values={'engineering_material':''}
        if tmp_material:
            thisMaterial=self.env['plm.material']
            thisObject=thisMaterial.browse(tmp_material)
            if thisObject.name:
                values['engineering_material']="{name}".format(name=thisObject.name)
        return {'value': {'engineering_material':values['engineering_material']}}

#     @api.onchange('tmp_treatment')
#     def on_change_tmptreatment(self, tmp_treatment=False):
#         values={'engineering_treatment': ''}
#         if tmp_treatment:
#             thisTreatment=self.env['plm.treatment']
#             thisObject=thisTreatment.browse(tmp_treatment)
#             if thisObject.name:
#                 values['engineering_treatment']="{name}".format(name=thisObject.name)
#         return {'value': {'engineering_treatment':values['engineering_treatment']}}

    @api.onchange('tmp_surface')
    def on_change_tmpsurface(self, tmp_surface=False):
        values={'engineering_surface': ''}
        if tmp_surface:
            thisSurface=self.env['plm.finishing']
            thisObject=thisSurface.browse(tmp_surface)
            if thisObject.name:
                values['engineering_surface']="{name}".format(name=thisObject.name)
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
                    prodIDs.append(self.getFromTemplateID(bom_line_obj.bom_id.product_tmpl_id.id).id)
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

#     @api.model
#     def _bom_find(self, product_tmpl=None, product=None, picking_type=None, company_id=False, bomType='normal'):
#         """ Finds BoM for particular product, picking and company """
#         domain = ['&',('type', '=', bomType)]
#         if product:
#             if not product_tmpl:
#                 product_tmpl = product.product_tmpl_id
#             domain +=['|', ('product_id', '=', product.id), '&', ('product_id', '=', False), ('product_tmpl_id', '=', product_tmpl.id)]
#         elif product_tmpl:
#             domain += [('product_tmpl_id', '=', product_tmpl.id)]
#         else:
#             # neither product nor template, makes no sense to search
#             return False
#         if picking_type:
#             domain += ['|', ('picking_type_id', '=', picking_type.id), ('picking_type_id', '=', False)]
#         if company_id or self.env.context.get('company_id'):
#             domain = domain + [('company_id', '=', company_id or self.env.context.get('company_id'))]
#         # order to prioritize bom with product_id over the one without
#         return self.search(domain, order='sequence, product_id', limit=1)

#     @api.one
#     @api.depends('child_bom_id')
#     def _compute_child_line_ids(self):
#         """ If the BOM line refers to a BOM, return the ids of the child BOM lines """
#         self.child_line_ids = self.child_bom_id.bom_line_ids.ids

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

#     def _get_child_bom_lines(self):
#         """
#             If the BOM line refers to a BOM, return the ids of the child BOM lines
#         """
#         bom_obj = self.env['mrp.bom']
#         ids=self._ids
#         res = {}
#         for bom_line in self.browse(ids):
#             bom_id = bom_obj._bom_find(product_tmpl=bom_line.product_id.product_tmpl_id,
#                 product=bom_line.product_id, bomType=bom_line.type)
#             if bom_id:
#                 child_bom = bom_obj.browse(bom_id)
#                 res[bom_line.id] = [x.id for x in child_bom.bom_line_ids]
#             else:
#                 res[bom_line.id] = False
#         return res

    state                   =   fields.Selection    (related="product_id.state",                string=_("Status"),     help=_("The status of the product in its LifeCycle."),  store=False)
    engineering_revision    =   fields.Integer      (related="product_id.engineering_revision", string=_("Revision"),   help=_("The revision of the product."),                 store=False)
    description             =   fields.Text         (related="product_id.description",          string=_("Description"),                                                        store=False)
    weight                  =   fields.Float        (related="product_id.weight",               string=_("Weight Net"),                                                         store=False)
#     child_line_ids          =   fields.One2many     ("mrp.bom.line",compute=_get_child_bom_lines,string=_("BOM lines of the referred bom"))


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
    father_line_ids     =   fields.Many2many('plm.document.relation', compute=_get_fathers_lines,    string=_("Documents related as fathers"),  store=False)

