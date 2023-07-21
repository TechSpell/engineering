# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2011-2015 OmniaSolutions srl (<http://www.omniasolutions.eu>). All Rights Reserved
#    Copyright (C) 2016-2020 Techspell srl (<http://www.techspell.eu>). All Rights Reserved
#    Copyright (C) 2020-2021 Didotech srl (<http://www.didotech.com>). All Rights Reserved
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

import re
import json

from odoo import api, models, _
from odoo.tools import float_round

def remove_html_tags(text):
    """Remove html tags from a string"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

class ReportBomStructure(models.AbstractModel):
    _inherit = 'report.mrp.report_bom_structure'

    def _add_engineering_data(self, components):
        for line in components:
            line['prod_desc'] = line.get('description',"")
            line['prod_revi'] = line.get('engineering_revision',"")
            line['prod_stat'] = line.get('state',"")

        return True

    def _add_engineering_void_data(self, operations):
        """
            Maintains coherence column showing data.
        """
        for line in operations:
            line['description'] = ""
            line['engineering_revision'] = ""
            line['state'] = ""
        return operations
   
### OVERRIDDEN STANDARD METHODS 

    @api.model
    def _get_component_data(self, parent_bom, warehouse, bom_line, line_quantity, level, index, product_info, ignore_stock=False):
        company = parent_bom.company_id or self.env.company
        key = bom_line.product_id.id
        if key not in product_info:
            product_info[key] = {'consumptions': {'in_stock': 0}}

        price = bom_line.product_id.uom_id._compute_price(bom_line.product_id.with_company(company).standard_price, bom_line.product_uom_id) * line_quantity
        rounded_price = company.currency_id.round(price)

        bom_key = parent_bom.id
        if not product_info[key].get(bom_key):
            product_info[key][bom_key] = self.with_context(product_info=product_info, parent_bom=parent_bom)._get_resupply_route_info(warehouse, bom_line.product_id, line_quantity)
        route_info = product_info[key].get(bom_key, {})

        quantities_info = {}
        if not ignore_stock:
            # Useless to compute quantities_info if it's not going to be used later on
            quantities_info = self._get_quantities_info(bom_line.product_id, bom_line.product_uom_id, parent_bom, product_info)
        availabilities = self._get_availabilities(bom_line.product_id, line_quantity, product_info, bom_key, quantities_info, level, ignore_stock)

        attachment_ids = []
        if not self.env.context.get('minimized', False):
            attachment_ids = self.env['mrp.document'].search(['|', '&', ('res_model', '=', 'product.product'), ('res_id', '=', bom_line.product_id.id),
                                                              '&', ('res_model', '=', 'product.template'), ('res_id', '=', bom_line.product_id.product_tmpl_id.id)]).ids

        return {
            'type': 'component',
            'index': index,
            'bom_id': False,
            'product': bom_line.product_id,
            'product_id': bom_line.product_id.id,
            'link_id': bom_line.product_id.id if bom_line.product_id.product_variant_count > 1 else bom_line.product_id.product_tmpl_id.id,
            'link_model': 'product.product' if bom_line.product_id.product_variant_count > 1 else 'product.template',
            'name': bom_line.product_id.display_name,
            'code': '',
            'currency': company.currency_id,
            'currency_id': company.currency_id.id,
            'quantity': line_quantity,
            'quantity_available': quantities_info.get('free_qty', 0),
            'quantity_on_hand': quantities_info.get('on_hand_qty', 0),
            'base_bom_line_qty': bom_line.product_qty,
            'engineering_revision': bom_line.product_id.engineering_revision,
            'state': bom_line.product_id.state,
            'description': bom_line.product_id.description,
            'uom': bom_line.product_uom_id,
            'uom_name': bom_line.product_uom_id.name,
            'prod_cost': rounded_price,
            'bom_cost': rounded_price,
            'route_type': route_info.get('route_type', ''),
            'route_name': route_info.get('route_name', ''),
            'route_detail': route_info.get('route_detail', ''),
            'lead_time': route_info.get('lead_time', False),
            'stock_avail_state': availabilities['stock_avail_state'],
            'resupply_avail_delay': availabilities['resupply_avail_delay'],
            'availability_display': availabilities['availability_display'],
            'availability_state': availabilities['availability_state'],
            'availability_delay': availabilities['availability_delay'],
            'parent_id': parent_bom.id,
            'level': level or 0,
            'attachment_ids': attachment_ids,
        }

    @api.model
    def _get_bom_array_lines(self, data, level, unfolded_ids, unfolded, parent_unfolded=True):
        bom_lines = data['components']
        lines = []
        for bom_line in bom_lines:
            line_unfolded = ('bom_' + str(bom_line['index'])) in unfolded_ids
            line_visible = level == 1 or unfolded or parent_unfolded
            lines.append({
                'bom_id': bom_line['bom_id'],
                'name': bom_line['name'],
                'type': bom_line['type'],
                'quantity': bom_line['quantity'],
                'quantity_available': bom_line['quantity_available'],
                'quantity_on_hand': bom_line['quantity_on_hand'],
                'producible_qty': bom_line.get('producible_qty', False),
                'engineering_revision': bom_line['engineering_revision'],
                'state': bom_line['state'],
                'description': bom_line['description'],
                'uom': bom_line['uom_name'],
                'prod_cost': bom_line['prod_cost'],
                'bom_cost': bom_line['bom_cost'],
                'route_name': bom_line['route_name'],
                'route_detail': bom_line['route_detail'],
                'lead_time': bom_line['lead_time'],
                'level': bom_line['level'],
                'code': bom_line['code'],
                'availability_state': bom_line['availability_state'],
                'availability_display': bom_line['availability_display'],
                'visible': line_visible,
            })
            if bom_line.get('components'):
                lines += self._get_bom_array_lines(bom_line, level + 1, unfolded_ids, unfolded, line_visible and line_unfolded)

        if data['operations']:
            lines.append({
                'name': _('Operations'),
                'type': 'operation',
                'quantity': data['operations_time'],
                'uom': _('minutes'),
                'bom_cost': data['operations_cost'],
                'level': level,
                'visible': parent_unfolded,
            })
            operations_unfolded = unfolded or (parent_unfolded and ('operations_' + str(data['index'])) in unfolded_ids)
            for operation in data['operations']:
                lines.append({
                    'name': operation['name'],
                    'type': 'operation',
                    'quantity': operation['quantity'],
                    'uom': _('minutes'),
                    'bom_cost': operation['bom_cost'],
                    'level': level + 1,
                    'visible': operations_unfolded,
                })
        if data['byproducts']:
            lines.append({
                'name': _('Byproducts'),
                'type': 'byproduct',
                'uom': False,
                'quantity': data['byproducts_total'],
                'bom_cost': data['byproducts_cost'],
                'level': level,
                'visible': parent_unfolded,
            })
            byproducts_unfolded = unfolded or (parent_unfolded and ('byproducts_' + str(data['index'])) in unfolded_ids)
            for byproduct in data['byproducts']:
                lines.append({
                    'name': byproduct['name'],
                    'type': 'byproduct',
                    'quantity': byproduct['quantity'],
                    'uom': byproduct['uom'],
                    'prod_cost': byproduct['prod_cost'],
                    'bom_cost': byproduct['bom_cost'],
                    'level': level + 1,
                    'visible': byproducts_unfolded,
                })
        return lines

    @api.model
    def _get_bom_data(self, bom, warehouse, product=False, line_qty=False, bom_line=False, level=0, parent_bom=False, index=0, product_info=False, ignore_stock=False):
        """ Gets recursively the BoM and all its subassemblies and computes availibility estimations for each component and their disponibility in stock.
            Accepts specific keys in context that will affect the data computed :
            - 'minimized': Will cut all data not required to compute availability estimations.
            - 'from_date': Gives a single value for 'today' across the functions, as well as using this date in products quantity computes.
        """
        is_minimized = self.env.context.get('minimized', False)
        if not product:
            product = bom.product_id or bom.product_tmpl_id.product_variant_id
        if not line_qty:
            line_qty = bom.product_qty

        if not product_info:
            product_info = {}
        key = product.id
        if key not in product_info:
            product_info[key] = {'consumptions': {'in_stock': 0}}

        company = bom.company_id or self.env.company
        current_quantity = line_qty
        if bom_line:
            current_quantity = bom_line.product_uom_id._compute_quantity(line_qty, bom.product_uom_id) or 0

        prod_cost = 0
        attachment_ids = []
        if not is_minimized:
            if product:
                prod_cost = product.uom_id._compute_price(product.with_company(company).standard_price, bom.product_uom_id) * current_quantity
                attachment_ids = self.env['mrp.document'].search(['|', '&', ('res_model', '=', 'product.product'),
                                                                 ('res_id', '=', product.id), '&', ('res_model', '=', 'product.template'),
                                                                 ('res_id', '=', product.product_tmpl_id.id)]).ids
            else:
                # Use the product template instead of the variant
                prod_cost = bom.product_tmpl_id.uom_id._compute_price(bom.product_tmpl_id.with_company(company).standard_price, bom.product_uom_id) * current_quantity
                attachment_ids = self.env['mrp.document'].search([('res_model', '=', 'product.template'), ('res_id', '=', bom.product_tmpl_id.id)]).ids

        bom_key = bom.id
        if not product_info[key].get(bom_key):
            product_info[key][bom_key] = self.with_context(product_info=product_info, parent_bom=parent_bom)._get_resupply_route_info(warehouse, product, current_quantity, bom)
        route_info = product_info[key].get(bom_key, {})
        quantities_info = {}
        if not ignore_stock:
            # Useless to compute quantities_info if it's not going to be used later on
            quantities_info = self._get_quantities_info(product, bom.product_uom_id, parent_bom, product_info)

        description = remove_html_tags(product.description or bom.product_tmpl_id.description)
        status = product.state or bom.product_tmpl_id.state
        bom_report_line = {
            'index': index,
            'bom': bom,
            'bom_id': bom and bom.id or False,
            'bom_code': bom and bom.code or False,
            'type': 'bom',
            'quantity': current_quantity,
            'quantity_available': quantities_info.get('free_qty', 0),
            'quantity_on_hand': quantities_info.get('on_hand_qty', 0),
            'base_bom_line_qty': bom_line.product_qty if bom_line else False,  # bom_line isn't defined only for the top-level product
            'name': product.display_name or bom.product_tmpl_id.display_name,
            'engineering_revision': product.engineering_revision or bom.product_tmpl_id.engineering_revision,
            'state': status,
            'description': description,
            'uom': bom.product_uom_id if bom else product.uom_id,
            'uom_name': bom.product_uom_id.name if bom else product.uom_id.name,
            'route_type': route_info.get('route_type', ''),
            'route_name': route_info.get('route_name', ''),
            'route_detail': route_info.get('route_detail', ''),
            'lead_time': route_info.get('lead_time', False),
            'currency': company.currency_id,
            'currency_id': company.currency_id.id,
            'product': product,
            'product_id': product.id,
            'link_id': (product.id if product.product_variant_count > 1 else product.product_tmpl_id.id) or bom.product_tmpl_id.id,
            'link_model': 'product.product' if product.product_variant_count > 1 else 'product.template',
            'code': bom and bom.display_name or '',
            'prod_cost': prod_cost,
            'bom_cost': 0,
            'level': level or 0,
            'attachment_ids': attachment_ids,
            'phantom_bom': bom.type == 'phantom',
            'parent_id': parent_bom and parent_bom.id or False,
        }

        if not is_minimized:
            operations = self._get_operation_line(product, bom, float_round(current_quantity, precision_rounding=1, rounding_method='UP'), level + 1, index)
            bom_report_line['operations'] = operations
            bom_report_line['operations_cost'] = sum([op['bom_cost'] for op in operations])
            bom_report_line['operations_time'] = sum([op['quantity'] for op in operations])
            bom_report_line['bom_cost'] += bom_report_line['operations_cost']

        components = []
        for component_index, line in enumerate(bom.bom_line_ids):
            new_index = f"{index}{component_index}"
            if product and line._skip_bom_line(product):
                continue
            line_quantity = (current_quantity / (bom.product_qty or 1.0)) * line.product_qty
            if line.child_bom_id:
                component = self.with_context(parent_product_id=product.id)._get_bom_data(line.child_bom_id, warehouse, line.product_id, line_quantity, bom_line=line, level=level + 1, parent_bom=bom,
                                                                                          index=new_index, product_info=product_info, ignore_stock=ignore_stock)
            else:
                component = self.with_context(parent_product_id=product.id)._get_component_data(bom, warehouse, line, line_quantity, level + 1, new_index, product_info, ignore_stock)
            components.append(component)
            bom_report_line['bom_cost'] += component['bom_cost']
        bom_report_line['components'] = components
        bom_report_line['producible_qty'] = self._compute_current_production_capacity(bom_report_line)

        if not is_minimized:
            byproducts, byproduct_cost_portion = self._get_byproducts_lines(product, bom, current_quantity, level + 1, bom_report_line['bom_cost'], index)
            bom_report_line['byproducts'] = byproducts
            bom_report_line['cost_share'] = float_round(1 - byproduct_cost_portion, precision_rounding=0.0001)
            bom_report_line['byproducts_cost'] = sum(byproduct['bom_cost'] for byproduct in byproducts)
            bom_report_line['byproducts_total'] = sum(byproduct['quantity'] for byproduct in byproducts)
            bom_report_line['bom_cost'] *= bom_report_line['cost_share']

        availabilities = self._get_availabilities(product, current_quantity, product_info, bom_key, quantities_info, level, ignore_stock, components)
        bom_report_line.update(availabilities)

        if level == 0:
            # Gives a unique key for the first line that indicates if product is ready for production right now.
            bom_report_line['components_available'] = all([c['stock_avail_state'] == 'available' for c in components])
        return bom_report_line

#     def _get_bom_array_lines(self, data, level, unfolded_ids, unfolded, parent_unfolded=True):
#         bom_lines = data['components']
#         lines = []
#         for bom_line in bom_lines:
#             line_unfolded = ('bom_' + str(bom_line['index'])) in unfolded_ids
#             line_visible = level == 1 or unfolded or parent_unfolded
#             lines.append({
#                 'bom_id': bom_line['bom_id'],
#                 'name': bom_line['name'],
#                 'type': bom_line['type'],
#                 'quantity': bom_line['quantity'],
#                 'quantity_available': bom_line['quantity_available'],
#                 'quantity_on_hand': bom_line['quantity_on_hand'],
#                 'producible_qty': bom_line.get('producible_qty', False),
#                 'engineering_revision': bom_line['engineering_revision'],
#                 'state': bom_line['state'],
#                 'description': bom_line['description'],
#                 'uom': bom_line['uom_name'],
#                 'prod_cost': bom_line['prod_cost'],
#                 'bom_cost': bom_line['bom_cost'],
#                 'route_name': bom_line['route_name'],
#                 'route_detail': bom_line['route_detail'],
#                 'lead_time': bom_line['lead_time'],
#                 'level': bom_line['level'],
#                 'code': bom_line['code'],
#                 'availability_state': bom_line['availability_state'],
#                 'availability_display': bom_line['availability_display'],
#                 'visible': line_visible,
#             })
#             if bom_line.get('components'):
#                 lines += self._get_bom_array_lines(bom_line, level + 1, unfolded_ids, unfolded, line_visible and line_unfolded)
# 
#         if data['operations']:
#             lines.append({
#                 'name': _('Operations'),
#                 'type': 'operation',
#                 'quantity': data['operations_time'],
#                 'uom': _('minutes'),
#                 'bom_cost': data['operations_cost'],
#                 'level': level,
#                 'visible': parent_unfolded,
#             })
#             operations_unfolded = unfolded or (parent_unfolded and ('operations_' + str(data['index'])) in unfolded_ids)
#             for operation in data['operations']:
#                 lines.append({
#                     'name': operation['name'],
#                     'type': 'operation',
#                     'quantity': operation['quantity'],
#                     'uom': _('minutes'),
#                     'bom_cost': operation['bom_cost'],
#                     'level': level + 1,
#                     'visible': operations_unfolded,
#                 })
#         if data['byproducts']:
#             lines.append({
#                 'name': _('Byproducts'),
#                 'type': 'byproduct',
#                 'uom': False,
#                 'quantity': data['byproducts_total'],
#                 'bom_cost': data['byproducts_cost'],
#                 'level': level,
#                 'visible': parent_unfolded,
#             })
#             byproducts_unfolded = unfolded or (parent_unfolded and ('byproducts_' + str(data['index'])) in unfolded_ids)
#             for byproduct in data['byproducts']:
#                 lines.append({
#                     'name': byproduct['name'],
#                     'type': 'byproduct',
#                     'quantity': byproduct['quantity'],
#                     'uom': byproduct['uom'],
#                     'prod_cost': byproduct['prod_cost'],
#                     'bom_cost': byproduct['bom_cost'],
#                     'level': level + 1,
#                     'visible': byproducts_unfolded,
#                 })
#         return lines

    def _get_bom_lines(self, bom, bom_quantity, product, line_id, level):
        components, total = super(ReportBomStructure, self)._get_bom_lines(bom, bom_quantity, product, line_id, level)
        self._add_engineering_data(components)
        return components, total

    def _get_pdf_line(self, bom_id, product_id=False, qty=1, unfolded_ids=None, unfolded=False):
        data = super(ReportBomStructure, self)._get_pdf_line(bom_id, product_id, qty, unfolded_ids, unfolded)
        self._add_engineering_data(data['lines'])
        return data

    def _get_operation_line(self, product, bom, qty, level, index):
        data = super(ReportBomStructure, self)._get_operation_line(product, bom, qty, level, index)
        self._add_engineering_void_data(data)
        return data
 
    @api.model
    def _get_report_values(self, docids, data=None):
        data['childs']=False
        data['quantity']=1
        if data.get('unfolded_ids'):
            if not list(set(json.loads(data.get('unfolded_ids')))):
                data.pop('unfolded_ids')
        return super(ReportBomStructure, self)._get_report_values(docids, data)

### OVERRIDDEN STANDARD METHODS 

