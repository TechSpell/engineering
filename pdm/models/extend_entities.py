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

from openerp.osv import orm, fields
from openerp.tools.translate import _

from common import getListIDs

class plm_document(orm.Model):
    _name = 'plm.document'
    _inherit = ['mail.thread','plm.document']

    _columns = {
        'linkedcomponents': fields.many2many('product.product', 'plm_component_document_rel', 'document_id',
                                             'component_id', 'Linked Parts'),
    }
    _defaults = {
                 'state': lambda *a: 'draft',
                 'res_id': lambda *a: False,
    }    
plm_document()

class plm_component(orm.Model):
    _name = 'product.product'
    _inherit = 'product.product'
    
    def _father_part_compute(self, cr, uid, ids, name, arg, context={}):
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
        result={}
        prod_ids=[]
        if context is None:
            context = {}
        bom_line_objType = self.pool['mrp.bom.line']
        prod_objs = self.pool['product.product'].browse(cr, uid, ids, context=context)
        for prod_obj in prod_objs:
            tmp_ids = bom_line_objType.search(cr, uid, [('product_id','=',prod_obj.id)])
            for bom_line_obj in bom_line_objType.browse(cr, uid, tmp_ids, context=context):                
                prod_ids.extend([bom_line_obj.bom_id.product_id.id])
            result[prod_obj.id]=list(set(prod_ids))
        return result
 
    _columns = {
        'linkeddocuments': fields.many2many('plm.document', 'plm_component_document_rel', 'component_id', 'document_id',
                                            'Linked Docs'),
        'tmp_material': fields.many2one('plm.material', 'Raw Material', required=False, change_default=True,
                                        help="Select raw material for current product"),
        #                'tmp_treatment': fields.many2one('plm.treatment','Thermal Treatment', required=False, change_default=True, help="Select thermal treatment for current product"),
        'tmp_surface': fields.many2one('plm.finishing', 'Surface Finishing', required=False, change_default=True,
                                       help="Select surface finishing for current product"),
        'father_part_ids': fields.function(_father_part_compute, relation="mrp.bom", string="BOM lines of the referred bom", type="one2many", store=False),
    }

    def on_change_tmpmater(self, cr, uid, ids, tmp_material=False, context=None):
        values={'engineering_material':''}
        context=context or self.pool['res.users'].context_get(cr, uid)
        if tmp_material:
            thisMaterial=self.pool['plm.material']
            thisObject=thisMaterial.browse(cr, uid, tmp_material, context=context)
            if thisObject.name:
                values['engineering_material']="{name}".format(name=thisObject.name)
        return {'value': {'engineering_material':values['engineering_material']}}

    def on_change_tmptreatment(self, cr, uid, ids, tmp_treatment=False, context=None):
        values={'engineering_treatment': ''}
        context=context or self.pool['res.users'].context_get(cr, uid)
        if tmp_treatment:
            thisTreatment=self.pool['plm.treatment']
            thisObject=thisTreatment.browse(cr, uid, tmp_treatment, context=context)
            if thisObject.name:
                values['engineering_treatment']="{name}".format(name=thisObject.name)
        return {'value': {'engineering_treatment':values['engineering_treatment']}}

    def on_change_tmpsurface(self, cr, uid, ids, tmp_surface=False, context=None):
        values={'engineering_surface': ''}
        context=context or self.pool['res.users'].context_get(cr, uid)
        if tmp_surface:
            thisSurface=self.pool['plm.finishing']
            thisObject=thisSurface.browse(cr, uid, tmp_surface, context=context)
            if thisObject.name:
                values['engineering_surface']="{name}".format(name=thisObject.name)
        return {'value': {'engineering_surface':values['engineering_surface']}}

    def _father_compute(self, cr, uid, ids, context=None):
        """ 
            Gets father BoM.
        """
        prod_ids={}
        for prod_obj in self.browse(cr, uid, ids, context=context):
            prodIDs=[]
            bom_line_objType=self.pool['mrp.bom.line']
            tmp_ids = bom_line_objType.search(cr, uid, [('product_id','=',prod_obj.id)])
            for bom_line_obj in bom_line_objType.browse(cr, uid, tmp_ids, context=context): 
                if not bom_line_obj.bom_id.product_id:
                    prodIDs.append(self.getFromTemplateID(cr, uid, bom_line_obj.bom_id.product_tmpl_id.id, context=context).id)
                else:            
                    prodIDs.append(bom_line_obj.bom_id.product_id.id)
            prod_ids[prod_obj.id]=list(set(prodIDs))
        return prod_ids

    def recurse_father_part_compute(self, cr, uid, ids=[], context=None):
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
        for prod_obj in self.browse(cr, uid, ids, context=context):
            prod_ids=[]
            if not(prod_obj.id in self.alreadyListed):
                self.alreadyListed.append(prod_obj.id)
                tmp_ids=self._father_compute(cr, uid, [prod_obj.id], context=context)
                if tmp_ids:
                    prod_ids.extend(tmp_ids[prod_obj.id])
                    for prodObject in self.browse(cr, uid, tmp_ids[prod_obj.id], context=context):
                        bufIDs=self.recurse_father_part_compute(cr, uid, [prodObject.id], context=context)
                        prod_ids.extend(bufIDs[prodObject.id])
            result[prod_obj.id]=list(set(prod_ids))
        return result

plm_component()

class plm_relation(orm.Model):
    _name = 'mrp.bom'
    _inherit = 'mrp.bom'

#######################################################################################################################################33

#   Overridden methods for this entity

    def _bom_find(self, cr, uid, product_tmpl_id=None, product_id=None, properties=None, bomType='normal',context=None):
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
                product_tmpl_id = self.pool['product.product'].browse(cr, uid, product_id, context=context).product_tmpl_id.id
            domain = domain + [
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
#         domain = domain + [ '|', ('date_start', '=', False), ('date_start', '<=', time.strftime(DEFAULT_SERVER_DATE_FORMAT)),
#                             '|', ('date_stop', '=', False), ('date_stop', '>=', time.strftime(DEFAULT_SERVER_DATE_FORMAT))]
        # order to prioritize bom with product_id over the one without
        ids = self.search(cr, uid, domain, order='sequence, product_id', context=context)
        # Search a BoM which has all properties specified, or if you can not find one, you could
        # pass a BoM without any properties
        bom_empty_prop = False
        for bom in self.pool['mrp.bom'].browse(cr, uid, ids, context=context):
            return bom.id
        return bom_empty_prop
    
#######################################################################################################################################33

    def _father_compute(self, cr, uid, ids, name, arg, context=None):
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
        result = {}
        if context is None:
            context = {}
        bom_objType = self.pool['mrp.bom']
        bom_line_objType = self.pool['mrp.bom.line']
        bom_objs = bom_objType.browse(cr, uid, ids, context=context)
        for bom_obj in bom_objs:
            bom_type=bom_obj.type
            result[bom_obj.id] = []
            if bom_type=='':
                criteria = [('product_id','=',bom_obj.product_id.id)]
            else:
                criteria = [('product_id','=',bom_obj.product_id.id),('type','=',bom_type)]
        
            tmp_ids=bom_line_objType.search(cr, uid, criteria, context=context)
            for bom_child in bom_line_objType.browse(cr, uid, getListIDs(tmp_ids), context=context):
                if bom_child.bom_id.id:
                    if not (bom_child.bom_id.id in result[bom_obj.id]):
                        result[bom_obj.id]+=[bom_child.bom_id.id]
        return result
 
    _columns = {
                'state': fields.related('product_id','state',type="char",relation="product.template",string="Status",help="The status of the product in its LifeCycle.",store=False),
                'engineering_revision': fields.related('product_id','engineering_revision',type="char",relation="product.template",string="Revision",help="The revision of the product.",store=False),
                'description': fields.related('product_id','description',type="char",relation="product.template",string="Description",store=False),
                'father_complete_ids': fields.function(_father_compute, relation='mrp.bom', method=True, string="BoM Hierarchy", type='many2many', store =False),
               }

plm_relation()

class plm_relation_line(orm.Model):
    _name = 'mrp.bom.line'
    _inherit = 'mrp.bom.line'
    _order = "itemnum"

    def _get_child_bom_lines(self, cr, uid, ids, field_name, arg, context=None):
        """
            If the BOM line refers to a BOM, return the ids of the child BOM lines
        """
        bom_obj = self.pool['mrp.bom']
        res = {}
        for bom_line in self.browse(cr, uid, ids, context=context):
            bom_id = bom_obj._bom_find(cr, uid,
                product_tmpl_id=bom_line.product_id.product_tmpl_id.id,
                product_id=bom_line.product_id.id, bomType=bom_line.type, context=context)
            if bom_id:
                child_bom = bom_obj.browse(cr, uid, bom_id, context=context)
                res[bom_line.id] = [x.id for x in child_bom.bom_line_ids]
            else:
                res[bom_line.id] = False
        return res


    _columns = {
        'state': fields.related('product_id', 'state', type="char", relation="product.template", string="Status",
                                store=False),
        'engineering_revision': fields.related('product_id', 'engineering_revision', type="char",
                                               relation="product.template", string="Revision", store=False),
        'description': fields.related('product_id', 'description', type="char", relation="product.template",
                                      string="Description", store=False),
        'weight': fields.related('product_id','weight_net',type="float",relation="product.template",string="Weight Net",store=False),
        'child_line_ids': fields.function(_get_child_bom_lines, relation="mrp.bom.line", string="BOM lines of the referred bom", type="one2many"),
               }

plm_relation_line()


class plm_checkout(orm.Model):
    _name = 'plm.checkout'
    _inherit = 'plm.checkout'

    _columns = {
        'name': fields.related('documentid', 'name', type="char", relation="plm.document",
                                         string="Document", store=False),
        }
  
plm_checkout()


class plm_backupdoc(orm.Model):
    _name = 'plm.backupdoc'
    _inherit = 'plm.backupdoc'

    _columns = {
        'name': fields.related('documentid', 'name', type="char", relation="plm.document",
                                         string="Document", store=False),
            }
plm_backupdoc()


class plm_document_relation(orm.Model):
    _name = 'plm.document.relation'
    _inherit = 'plm.document.relation'

    def _get_parents(self, cr, uid, lines=None, context=None):
        """
            If the BOM line refers to a BOM, return the ids of the child BOM lines
        """
        ids=[]
        for line_id in lines:
            criteria=[('parent_id', '=', line_id.parent_id.id)]
            ids=self.search(cr, uid, criteria, context=context)
        return self.browse(cr, uid, list(set(ids)), context=context)


    def _get_children(self, cr, uid, line_ids=None, context=None):
        """
            If the BOM line refers to a BOM, return the ids of the child BOM lines
        """
        ids=[]
        for line_id in line_ids:
            ids.append(line_id.child_id.id)
        criteria=[('parent_id', 'in', list(set(ids)))]
        resIDs=self.search(cr, uid, criteria, context=context)
        return list(set(resIDs))
    
    def _get_children_lines(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for line_id in self.browse(cr, uid, ids, context=context):
            parents=self._get_parents(cr, uid, line_id, context=context)
            res[line_id.id]=self._get_children(cr, uid, parents, context=context)
        return res


    def _get_fathers(self, cr, uid, lines=None, context=None):
        ids=[]
        for line_id in lines:
            criteria=[('child_id', '=', line_id.parent_id.id),('link_kind', 'in', ['HiTree'])]
            ids=self.search(cr, uid, criteria, context=context)
        return list(set(ids))
        
    def _get_fathers_lines(self, cr, uid, ids, name, arg, context=None):
        res={}
        for line_id in self.browse(cr, uid, ids, context=context):
            res[line_id.id]=self._get_fathers(cr, uid, line_id, context=context)
        return res


    _columns = {
        'name':             fields.related('parent_id', 'name', type="char", relation="plm.document",
                                         string="Document", store=False),
        'parent_preview':   fields.related('parent_id', 'preview', type="binary", relation="plm.document",
                                         string="Preview", store=False),
        'parent_state':     fields.related('parent_id', 'state', type="char", relation="plm.document", string="Status",
                                       store=False, index=True),
        'parent_revision':  fields.related('parent_id', 'revisionid', type="integer", relation="plm.document",
                                          string="Revision", store=False),
        'parent_checkedout':fields.related('parent_id', 'checkout_user', type="char", relation="plm.document",
                                            string="Checked-Out To", store=False),
        'child_preview':    fields.related('child_id', 'preview', type="binary", relation="plm.document", string="Preview",
                                        store=False),
        'child_state':      fields.related('child_id', 'state', type="char", relation="plm.document", string="Status",
                                      store=False, index=True),
        'child_revision':   fields.related('child_id', 'revisionid', type="integer", relation="plm.document",
                                         string="Revision", store=False),
        'child_checkedout': fields.related('child_id', 'checkout_user', type="char", relation="plm.document",
                                           string="Checked-Out To", store=False),
        'child_line_ids':   fields.function(_get_children_lines, relation='plm.document.relation', method=True, string="Documents related as children", type='one2many', store =False),
        'father_line_ids':  fields.function(_get_fathers_lines, relation='plm.document.relation',  method=True, string="Documents related as fathers",  type='one2many', store =False),
    }

plm_document_relation()

