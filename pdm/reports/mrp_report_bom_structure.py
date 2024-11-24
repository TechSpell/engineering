# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2011-2015 OmniaSolutions srl (<http://www.omniasolutions.eu>). All Rights Reserved
#    Copyright (C) 2016-2020 Techspell srl (<http://www.techspell.eu>). All Rights Reserved
#    Copyright (C) 2020-2021 Didotech srl (<http://www.didotech.com>). All Rights Reserved
#    Copyright (C) 2024-2024 Codebeex srl (<http://www.codebeex.com>). All Rights Reserved
#    
#    Created on : 2024-10-04
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
from collections import defaultdict

from odoo import api, models, _
from odoo.tools import float_round

def remove_html_tags(text):
    """Remove html tags from a string"""
    ret = ""
    if isinstance(text, (str, bytes)):
        clean = re.compile('<.*?>')
        ret = re.sub(clean, '', text)
    return ret

class ReportBomStructure(models.AbstractModel):
    _inherit = 'report.mrp.report_bom_structure'

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
                                                                
    def _get_component_data(self, parent_bom, parent_product, warehouse, bom_line, line_quantity, level, index, product_info, ignore_stock=False):
        component =  super(ReportBomStructure, self)._get_component_data(parent_bom, parent_product, warehouse, bom_line, line_quantity, level, index, product_info, ignore_stock=ignore_stock)
        product_id = component.get('product', False)
        component['engineering_revision'] = 0 
        component['state'] = ''        
        component['bom_line_id'] = bom_line.id if bom_line else False
        component['bom_type'] = bom_line.type if bom_line else False
        
        if product_id:                 
            description = remove_html_tags(product_id.description)
            component['engineering_revision'] = product_id.engineering_revision
            component['state'] = product_id.state
            component['description'] = description
        return component               
                                                                
    @api.model
    def _get_bom_data(self, bom, warehouse, product=False, line_qty=False, bom_line=False, level=0, parent_bom=False, parent_product=False, index=0, product_info=False, ignore_stock=False, simulated_leaves_per_workcenter=False):
        """ Gets recursively the BoM and all its subassemblies and computes availibility estimations for each component and their disponibility in stock.
            Accepts specific keys in context that will affect the data computed :
            - 'minimized': Will cut all data not required to compute availability estimations.
            - 'from_date': Gives a single value for 'today' across the functions, as well as using this date in products quantity computes.
        """
        is_minimized = self.env.context.get('minimized', False)
        if not product:
            product = bom.product_id or bom.product_tmpl_id.product_variant_id
        if line_qty is False:
            line_qty = bom.product_qty
        if not product_info:
            product_info = {}
        if simulated_leaves_per_workcenter is False:
            simulated_leaves_per_workcenter = defaultdict(list)

        company = bom.company_id or self.env.company
        current_quantity = line_qty
        if bom_line:
            current_quantity = bom_line.product_uom_id._compute_quantity(line_qty, bom.product_uom_id) or 0

        prod_cost = 0
        has_attachments = False
        if not is_minimized:
            if product:
                prod_cost = product.uom_id._compute_price(product.with_company(company).standard_price, bom.product_uom_id) * current_quantity
                has_attachments = self.env['product.document'].search_count(['&', '&', ('attached_on_mrp', '=', 'bom'), ('active', '=', 't'), '|', '&', ('res_model', '=', 'product.product'),
                                                                 ('res_id', '=', product.id), '&', ('res_model', '=', 'product.template'),
                                                                 ('res_id', '=', product.product_tmpl_id.id)], limit=1) > 0
            else:
                # Use the product template instead of the variant
                prod_cost = bom.product_tmpl_id.uom_id._compute_price(bom.product_tmpl_id.with_company(company).standard_price, bom.product_uom_id) * current_quantity
                has_attachments = self.env['product.document'].search_count(['&', '&', ('attached_on_mrp', '=', 'bom'), ('active', '=', 't'),
                                                                    '&', ('res_model', '=', 'product.template'), ('res_id', '=', bom.product_tmpl_id.id)], limit=1) > 0

        key = product.id
        bom_key = bom.id
        qty_product_uom = bom.product_uom_id._compute_quantity(current_quantity, product.uom_id or bom.product_tmpl_id.uom_id)
        self._update_product_info(product, bom_key, product_info, warehouse, qty_product_uom, bom=bom, parent_bom=parent_bom, parent_product=parent_product)
        route_info = product_info[key].get(bom_key, {})
        quantities_info = {}
        if not ignore_stock:
            # Useless to compute quantities_info if it's not going to be used later on
            quantities_info = self._get_quantities_info(product, bom.product_uom_id, product_info, parent_bom, parent_product)

        bom_report_line = {
            'index': index,
            'bom': bom,
            'bom_id': bom and bom.id or False,
            'bom_code': bom and bom.code or False,
            'type': 'bom',
            'quantity': current_quantity,
            'quantity_available': quantities_info.get('free_qty') or 0,
            'quantity_on_hand': quantities_info.get('on_hand_qty') or 0,
            'free_to_manufacture_qty': quantities_info.get('free_to_manufacture_qty') or 0,
            'base_bom_line_qty': bom_line.product_qty if bom_line else False,  # bom_line isn't defined only for the top-level product
            'name': product.display_name or bom.product_tmpl_id.display_name,
            'uom': bom.product_uom_id if bom else product.uom_id,
            'uom_name': bom.product_uom_id.name if bom else product.uom_id.name,
            'engineering_revision': product.engineering_revision if product else 0,
            'state': product.state if product else '',
            'description': remove_html_tags(product.description)  if product else '',
            'bom_line_id': bom_line.id if bom_line else False,
            'bom_type': bom_line.type if bom_line else False,
            'route_type': route_info.get('route_type', ''),
            'route_name': route_info.get('route_name', ''),
            'route_detail': route_info.get('route_detail', ''),
            'route_alert': route_info.get('route_alert', False),
            'currency': company.currency_id,
            'currency_id': company.currency_id.id,
            'product': product,
            'product_id': product.id,
            'product_template_id': product.product_tmpl_id.id,
            'link_id': (product.id if product.product_variant_count > 1 else product.product_tmpl_id.id) or bom.product_tmpl_id.id,
            'link_model': 'product.product' if product.product_variant_count > 1 else 'product.template',
            'code': bom and bom.display_name or '',
            'prod_cost': prod_cost,
            'bom_cost': 0,
            'level': level or 0,
            'has_attachments': has_attachments,
            'phantom_bom': bom.type == 'phantom',
            'parent_id': parent_bom and parent_bom.id or False,
        }

        components = []
        no_bom_lines = self.env['mrp.bom.line']
        line_quantities = {}
        for line in bom.bom_line_ids:
            if product and line._skip_bom_line(product):
                continue
            line_quantity = (current_quantity / (bom.product_qty or 1.0)) * line.product_qty
            line_quantities[line.id] = line_quantity
            if not line.child_bom_id:
                no_bom_lines |= line
                # Update product_info for all the components before computing closest forecasted.
                qty_product_uom = line.product_uom_id._compute_quantity(line_quantity, line.product_id.uom_id)
                self._update_product_info(line.product_id, bom.id, product_info, warehouse, qty_product_uom, bom=False, parent_bom=bom, parent_product=product)
        components_closest_forecasted = self._get_components_closest_forecasted(no_bom_lines, line_quantities, bom, product_info, product, ignore_stock)
        for component_index, line in enumerate(bom.bom_line_ids):
            new_index = f"{index}{component_index}"
            if product and line._skip_bom_line(product):
                continue
            line_quantity = line_quantities.get(line.id, 0.0)
            if line.child_bom_id:
                component = self._get_bom_data(line.child_bom_id, warehouse, line.product_id, line_quantity, bom_line=line, level=level + 1, parent_bom=bom,
                                               parent_product=product, index=new_index, product_info=product_info, ignore_stock=ignore_stock,
                                               simulated_leaves_per_workcenter=simulated_leaves_per_workcenter)
            else:
                component = self.with_context(
                    components_closest_forecasted=components_closest_forecasted,
                )._get_component_data(bom, product, warehouse, line, line_quantity, level + 1, new_index, product_info, ignore_stock)
            for component_bom in components:
                if component['product_id'] == component_bom['product_id'] and component['uom'].id == component_bom['uom'].id:
                    self._merge_components(component_bom, component)
                    break
            else:
                components.append(component)
            bom_report_line['bom_cost'] += component['bom_cost']
        bom_report_line['components'] = components
        bom_report_line['producible_qty'] = self._compute_current_production_capacity(bom_report_line)

        availabilities = self._get_availabilities(product, current_quantity, product_info, bom_key, quantities_info, level, ignore_stock, components, report_line=bom_report_line)
        # in case of subcontracting, lead_time will be calculated with components availability delay
        bom_report_line['lead_time'] = route_info.get('lead_time', False)
        bom_report_line['manufacture_delay'] = route_info.get('manufacture_delay', False)
        bom_report_line.update(availabilities)

        if not is_minimized:

            operations = self._get_operation_line(product, bom, float_round(current_quantity, precision_rounding=1, rounding_method='UP'), level + 1, index, bom_report_line, simulated_leaves_per_workcenter)
            bom_report_line['operations'] = operations
            bom_report_line['operations_cost'] = sum(op['bom_cost'] for op in operations)
            bom_report_line['operations_time'] = sum(op['quantity'] for op in operations)
            bom_report_line['operations_delay'] = max((op['availability_delay'] for op in operations), default=0)
            if 'simulated' in bom_report_line:
                bom_report_line['availability_state'] = 'estimated'
                max_component_delay = bom_report_line['max_component_delay']
                bom_report_line['availability_delay'] = max_component_delay + max(bom.produce_delay, bom_report_line['operations_delay'])
                bom_report_line['availability_display'] = self._format_date_display(bom_report_line['availability_state'], bom_report_line['availability_delay'])
            bom_report_line['bom_cost'] += bom_report_line['operations_cost']

            byproducts, byproduct_cost_portion = self._get_byproducts_lines(product, bom, current_quantity, level + 1, bom_report_line['bom_cost'], index)
            bom_report_line['byproducts'] = byproducts
            bom_report_line['cost_share'] = float_round(1 - byproduct_cost_portion, precision_rounding=0.0001)
            bom_report_line['byproducts_cost'] = sum(byproduct['bom_cost'] for byproduct in byproducts)
            bom_report_line['byproducts_total'] = sum(byproduct['quantity'] for byproduct in byproducts)
            bom_report_line['bom_cost'] *= bom_report_line['cost_share']

        if level == 0:
            # Gives a unique key for the first line that indicates if product is ready for production right now.
            bom_report_line['components_available'] = all([c['stock_avail_state'] == 'available' for c in components])
        return bom_report_line

    def _get_bom_array_lines(self, data, level, unfolded_ids, unfolded, parent_unfolded=True):
        bom_lines = data['components'] 
        lines = []                     
        for bom_line in bom_lines:     
            line_unfolded = ('bom_' + str(bom_line['index'])) in unfolded_ids
            line_visible = level == 1 or unfolded or parent_unfolded
            description = remove_html_tags(bom_line['description'])
            lines.append({             
                'bom_id': bom_line['bom_id'],
                'bom_line_id': bom_line['bom_line_id'],
                'bom_type': bom_line['bom_type'],
                'type': bom_line['type'],
                'name': bom_line['name'],
                'quantity': bom_line['quantity'],
                'quantity_available': bom_line['quantity_available'],
                'quantity_on_hand': bom_line['quantity_on_hand'],
                'producible_qty': bom_line.get('producible_qty', False),
                'engineering_revision': bom_line['engineering_revision'],
                'state': bom_line['state'],
                'description': description,
                'prod_revi': bom_line['engineering_revision'],
                'prod_stat': bom_line['state'],
                'prod_desc': description,
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
    def _get_operation_line(self, product, bom, qty, level, index, bom_report_line, simulated_leaves_per_workcenter):
        data = super(ReportBomStructure, self)._get_operation_line(product, bom, qty, level, index, bom_report_line, simulated_leaves_per_workcenter)
        self._add_engineering_void_data(data)
        return data
 
    def _get_report_values(self, docids, data=None):
        data['childs']=False
        data['quantity']=1
        if data.get('unfolded_ids'):
            if not list(set(json.loads(data.get('unfolded_ids')))):
                data.pop('unfolded_ids')
        return super(ReportBomStructure, self)._get_report_values(docids, data)

### OVERRIDDEN STANDARD METHODS 

