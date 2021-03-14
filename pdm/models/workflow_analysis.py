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
from .common import moduleName
import xxlimited

openerpModule=moduleName()

from .common import move_workflow, wf_message_post


class plm_component(models.Model):
    _inherit = 'product.product'

    @api.model
    def _getNewChildrenBom(self, level=0, currlevel=0):
        """
            Returns a flat list of each child, listed once, in a Bom ( level = 0 one level only, level = 1 all levels)
        """
        result = self.env['product.product']
        if (level == 0) and (currlevel > 1):
            return result
        for product_id in self:
            for bomid in product_id.bom_ids:
                for bomline in bomid.bom_line_ids:
                    result += bomline.product_id
                    result += bomline.product_id._getNewChildrenBom(level, currlevel+1)
        return result

    ##  Work Flow Internal Methods
    @api.model
    def _get_new_recursive_parts(self, excludeStatuses, includeStatuses, release=False):
        """
           Gets all ids related to current one as children
        """
        product_ids = self.env['product.product']
        options=self.env['plm.config.settings'].GetOptions()
        children = []
        for product_id in self:
            product_ids += product_id
            children = product_id._getNewChildrenBom(level=1)
            for child in children:
                if ((not child.state in excludeStatuses) and (not child.state in includeStatuses)) \
                        and (release and not(options.get('opt_obsoletedinbom', False))):
                    logging.warning("Part (%r - %d) is in a status '%s' not allowed."
                                    %(child.engineering_code, child.engineering_revision, child.state))
                    continue
                if child.state in includeStatuses:
                    if not child in product_ids:
                        product_ids += child
        return product_ids

    @api.model
    def _get_linked_documents(self, checked_in=False):
        """
            Gets linked documents, (all or checked-in).
        """
        document_ids = documentType = self.env['plm.document']
        for product_id in self:
            for document_id in product_id.linkeddocuments:
                if (document_id not in document_ids):
                    if checked_in:
                        if documentType.ischecked_in(document_id.id):
                            document_ids += document_id
                    else:
                        document_ids += document_id
        return document_ids

    ##  Specialized Actions callable interactively
    @api.model
    def action_check_workflow(self, operationParams):
        """
            Create a new Spare BoM if doesn't exist (action callable from views)
        """
        excludeStatuses=operationParams['excludeStatuses']
        includeStatuses=operationParams['includeStatuses']

        tempType = self.env["plm.temporary"]
        product_ids = productType = self.env['product.product']
        document_ids = documentType = self.env['plm.document']
        part_ids = checkProductType = self.env["plm.check.product"]
        docu_ids = checkDocumentType = self.env["plm.check.document"]
        
        if self:
            product_ids=self._get_new_recursive_parts(excludeStatuses, includeStatuses)
            document_ids = product_ids._get_linked_documents(checked_in=False)
        
            if product_ids or document_ids:
                name_operation = _('Check Workflow moving to "{}"'.format(operationParams["statusName"]))
                tmp_id = tempType.create({'name': name_operation})
                if tmp_id:
                    context = dict(self.env.context or {})
                    context.update({
                        'active_id': tmp_id.id,
                        'operationParams': operationParams
                        })
                    for product_id in product_ids:
                        discharge = False
                        values = {
                            'part_id': product_id.id,
                            'temp_id': tmp_id.id,
                            }
                        values.update({
                            'choice': not discharge,
                            })
                        part_ids += checkProductType.create(values)
                        
                    for document_id in document_ids:
                        discharge = False
                        values = {
                            'docu_id': document_id.id,
                            'temp_id': tmp_id.id,
                            }
                        if document_id.is_checkout or document_id.state in excludeStatuses or not(document_id.state in includeStatuses): 
                            discharge = True
                            if document_id.state in excludeStatuses or not(document_id.state in includeStatuses):
                                values.update({
                                    'notallowalble': discharge,
                                    'reason': _('Document is not in allowable status.'),
                                    })
                            elif document_id.is_checkout:
                                values.update({
                                    'discharge': discharge,
                                    'reason': _('Document is Checked-Out to: {}.'.format(document_id.checkout_user)),
                                    })
                        values.update({
                            'choice': not discharge,
                            })
                        docu_ids += checkDocumentType.create(values) 
                        
                    view_name = "{}.plm_check_wf_form_view".format(openerpModule)
                        
                    return {
                        'domain': [],
                        'name': name_operation,
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_model': 'plm.temporary',
                        'res_id': tmp_id.id,
                        'view_id': self.env.ref(view_name).id,
                        'type': 'ir.actions.act_window',
                        'context': context,
                    }

    @api.model
    def apply_workflow_action(self, operationParams):
        """
            Action to be executed to complete workflow operations.
            Launched from plm.temporary form
        """
        product_ids = self.env["product.product"]
             
        for product_id in self:
            product_ids += product_id
            
        action = operationParams['action']
        status = operationParams['status']
        default = operationParams['default']
        if product_ids:
            if (action == 'release'):
                for product_id in self:
                    for last_id in self._getbyrevision(product_id.engineering_code, product_id.engineering_revision - 1):
                        move_workflow(self, last_id.id, 'obsolete', 'obsoleted')
            move_workflow(self, product_ids.ids, action, status)
            self.logging_workflow(product_ids.ids, action, status)
            product_ids.with_context({'internal_writing':True}).write(default)
            wf_message_post(self, product_ids.ids, body='Status moved to: {status}.'.format(status=status))
        return product_ids


class plm_document(models.Model):
    _inherit = 'plm.document'

    @api.model
    def action_check_workflow(self, operationParams):
        """
            Create a new Spare BoM if doesn't exist (action callable from views)
        """
        excludeStatuses=operationParams['excludeStatuses']
        includeStatuses=operationParams['includeStatuses']

        tempType = self.env["plm.temporary"]
        document_ids = documentType = self.env['plm.document']
        docu_ids = checkDocumentType = self.env["plm.check.document"]
        
        for document_id in self:
            document_ids += document_id
        
        if document_ids:
            document_ids += document_ids.getRelatedDocuments()
            
            name_operation = _('Check Workflow moving to "{}"'.format(operationParams["statusName"]))
            tmp_id = tempType.create({'name': name_operation})
            if tmp_id:
                context = dict(self.env.context or {})
                context.update({
                    'active_id': tmp_id.id,
                    'operationParams': operationParams
                    })

                for document_id in document_ids:
                    discharge = False
                    values = {
                        'docu_id': document_id.id,
                        'temp_id': tmp_id.id,
                        }
                    if document_id.is_checkout or document_id.state in excludeStatuses or not(document_id.state in includeStatuses): 
                        discharge = True
                        if document_id.state in excludeStatuses or not(document_id.state in includeStatuses):
                            values.update({
                                'notallowalble': discharge,
                                'reason': _('Document is not in allowable status.'),
                                })
                        elif document_id.is_checkout:
                            values.update({
                                'discharge': discharge,
                                'reason': _('Document is Checked-Out to: {}.'.format(document_id.checkout_user)),
                                })
                    values.update({
                        'choice': not discharge,
                        })
                    docu_ids += checkDocumentType.create(values) 
                    
                view_name = "{}.plm_check_wf_form_view".format(openerpModule)
                    
                return {
                    'domain': [],
                    'name': name_operation,
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'plm.temporary',
                    'res_id': tmp_id.id,
                    'view_id': self.env.ref(view_name).id,
                    'type': 'ir.actions.act_window',
                    'context': context,
                }

    @api.model
    def apply_workflow_action(self, operationParams):
        """
            Action to be executed to complete workflow operations.
            Launched from plm.temporary form
        """
        document_ids = self.env["plm.document"]
        action = operationParams['docaction']
        status = operationParams['status']
        default = operationParams['doc_default']

        for document_id in self:
            document_ids += document_id
            
        if document_ids:
            movement = True
            if (action == 'release'):
                for document_id in self:
                    for last_id in self._getbyaltminorevision(document_id):
                        move_workflow(self, last_id.id, 'obsolete', 'obsoleted')
                    for last_id in self._getbyrevision(document_id.name, document_id.revisionid - 1):
                        move_workflow(self, last_id.id, 'obsolete', 'obsoleted')
            elif (action in ['obsolete','reactivate']):
                movement = False
                self.logging_workflow(document_ids.ids, action, status)
                wf_message_post(self, document_ids.ids, body='Status moved to: {status}.'.format(status=status))
                document_ids.with_context({'internal_writing':True}).write(default)

            if movement:
                move_workflow(self, document_ids.ids, action, status)
                self.logging_workflow(document_ids.ids, action, status)
                document_ids.with_context({'internal_writing':True}).write(default)
                wf_message_post(self, document_ids.ids, body='Status moved to: {status}.'.format(status=status))
        return document_ids

    @api.model
    def getRelatedDocuments(self):
        """
            Action to be executed to complete workflow operations.
            Launched from plm.temporary form
        """
        fthkindList = ['RfTree', 'LyTree']          # Get relation names due to fathers
        chnkindList = ['HiTree','RfTree', 'LyTree'] # Get relation names due to children
        documentRelation = self.env['plm.document.relation']
        ret = self.env['plm.document']
        for document_id in self:
            for docLink in documentRelation.search([('child_id', '=', document_id.id), ('link_kind', 'in', fthkindList)]):
                ret += docLink.parent_id
            for docLink in documentRelation.search([('parent_id', '=', document_id.id), ('link_kind', 'in', chnkindList)]):
                ret += docLink.child_id
        return ret

class plm_temporary(osv.osv.osv_memory):
    _inherit = "plm.temporary"

    @api.multi
    def action_workflow_apply(self):
        """
            Action to be executed to complete workflow operations.
            Launched from plm.temporary form
        """
        context = dict(self.env.context or {})
        operationParams = context.get('operationParams', False)
        activeId = context.get('active_id', False)
        if activeId and operationParams:
            product_ids = self.env["product.product"]
            document_ids = self.env["plm.document"]
            
            for part_id in self.part_ids:
                if part_id.choice and not(part_id.discharge) and not(part_id.notallowalble): 
                    product_ids += part_id.part_id
            if product_ids:
                product_ids.apply_workflow_action(operationParams)
               
            for docu_id in self.docu_ids:
                if docu_id.choice and not(docu_id.discharge) and not(docu_id.notallowalble): 
                    document_ids += docu_id.docu_id
                         
            if document_ids:
                document_ids.apply_workflow_action(operationParams)

            self.write({'executed': True})
