# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2011-2015 OmniaSolutions srl (<http://www.omniasolutions.eu>). All Rights Reserved
#    Copyright (C) 2016-2020 Techspell srl (<http://www.techspell.eu>). All Rights Reserved
#    Copyright (C) 2020-2021 Didotech srl (<http://www.didotech.com>). All Rights Reserved
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

from openerp.osv import fields, orm
from openerp.tools.translate import _

RETDMESSAGE=''

class plm_temporary(orm.TransientModel):
    _inherit = "plm.temporary"

    ##  Specialized Actions callable interactively
    def action_create_spareBom(self, cr, uid, ids, context=None):
        """
            Create a new Spare BoM if doesn't exist (action callable from views)
        """
        if not 'active_id' in context:
            return False
        if not 'active_ids' in context:
            return False
        
        context = context or self.pool['res.users'].context_get(cr, uid)
        productType=self.pool['product.product']
        bomType=self.pool['mrp.bom']
        context.update({ "update_latest_revision": self.browse(cr,uid,ids[0]).revflag })
        for idd in context['active_ids']:
            checkObj=productType.browse(cr, uid, idd, context)
            if not checkObj:
                continue
            criteria=[('product_id','=',idd),('type','=','spbom'),('active','=',True)]
            objBoms=bomType.search(cr, uid, criteria, context=context)
            if objBoms:
                raise orm.except_orm(_('Creating a new Spare BoM Error.'), _("BoM for Part %r already exists." %(checkObj.name)))

        productType.action_create_spareBom_WF(cr, uid, context['active_ids'], context=context)

        return {
            'name': _('Bill of Materials'),
            'view_type': 'form',
            "view_mode": 'tree,form',
            'res_model': 'mrp.bom',
            'type': 'ir.actions.act_window',
            'domain': "[('product_id','in', [" + ','.join(map(str, context['active_ids'])) + "])]",
        }


class plm_component(orm.Model):
    _inherit = 'product.product'

    #  Work Flow Actions
    def action_create_spareBom_WF(self, cr, uid, ids, context=None):
        """
            Create a new Spare BoM if doesn't exist (action callable from code)
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        for idd in ids:
            self.processedIds=[]
            self._create_spareBom(cr, uid, idd, context=context)
        return False

    #   Internal methods
    def _create_spareBom(self, cr, uid, idd, context=None):
        """
            Create a new Spare BoM (recursive on all EBom children)
        """
        newidBom=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        if idd in self.processedIds:
            return False
        self.processedIds.append(idd)
        checkObj=self.browse(cr, uid, idd, context=context)
        if not checkObj:
            return False
        if '-Spare' in checkObj.name:
            return False
        sourceBomType = context.get('sourceBomType', 'ebom')
        bomType=self.pool['mrp.bom']
        objBoms=bomType.search(cr, uid, [('product_id', '=', idd), ('type', '=', 'spbom'), ('bom_id', '=', False), ('active', '=', True)], context=context)
        idBoms=bomType.search(cr, uid, [('product_id', '=', idd), ('type', '=', 'normal'), ('bom_id', '=', False), ('active', '=', True)], context=context)
        if not idBoms:
            idBoms=bomType.search(cr, uid,
                                    [('product_id', '=', idd), ('type', '=', sourceBomType), ('bom_id', '=', False), ('active', '=', True)], context=context)

        defaults={}
        if not objBoms:
            context['internal_writing']=True
            if checkObj.std_description.bom_tmpl:
                newidBom = bomType.copy(cr, uid, checkObj.std_description.bom_tmpl.id, defaults, context=context)
            if (not newidBom) and idBoms:
                newidBom=bomType.copy(cr, uid, idBoms[0], defaults, context=context)
            if newidBom:
                bomType.write(cr, uid, [newidBom],
                              {'name': checkObj.name, 'product_id': checkObj.id, 'type': 'spbom', 'active': True,}, context=context)
                oidBom=bomType.browse(cr, uid, newidBom, context=context)

                ok_rows=self._summarizeBom(cr, uid, oidBom.bom_lines)
                for bom_line in list(set(oidBom.bom_lines) ^ set(ok_rows)):
                    bomType.unlink(cr, uid, [bom_line.id], context=context)
                for bom_line in ok_rows:
                    bomType.write(cr, uid, [bom_line.id],
                                  {'type': 'spbom', 'source_id': False, 'name': bom_line.product_id.name,
                                   'product_qty': bom_line.product_qty, }, context=context)
                    self._create_spareBom(cr, uid, bom_line.product_id.id, context=context)
        else:
            for bom_line in bomType.browse(cr, uid, objBoms[0], context=context).bom_lines:
                self._create_spareBom(cr, uid, bom_line.product_id.id, context=context)
        return False


class plm_description(orm.Model):
    _inherit = "plm.description"
    _columns = {
        'bom_tmpl': fields.many2one('mrp.bom', 'Choose a BoM', required=False, change_default=True,
                                    help="Select a  BoM as template to drive building Spare BoM."),
    }
    _defaults = {
        'bom_tmpl': lambda *a: False,
    }

# Introduced relationship with mrp.bom to implement Spare Part Bom functionality
