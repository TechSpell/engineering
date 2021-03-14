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
{
    'name': 'Engineering & Lifecycle Management',
    'version': '1.0.0',
    'author': 'Didotech srl',
    'website': 'http://www.didotech.com',
    'support': 'support@didotech.com',
    'category': 'Document Management',
    'sequence': 10,
    'summary': 'PLM Engineering integration with main CAD editors',
    'images': ['images/main_screenshot.png'],
    'depends': ['base','board','product','mrp'],
    'description': """
Product Lifecycle Management in Odoo
====================================

This application enables a group of people to intelligently and efficiently manage 3D Models and 2D Drawings, directly from CAD editors.

It manages fundamental revisions of Products and Documents, helps to work in Concurrent Engineering with access policies to documents.

Moreover, it adds many reports and views on Bill of Materials or related to them. It helps to share 2D documents using PDF embedded.

New functionality Compare BoMs helps to understand differences between Bill of Materials.

Key Features :
--------------
    
    * Editor Integration
    * Document Management
    * Document Relationship
    * Engineering Bill of Materials
    * Spare Parts BoM & Reports
    * Compare BoMs
    
    
Supported Editors :
-------------------
   
    * Category : CAD / Mechanical CAD
    
        * ThinkDesign 2016.1 (and above)
        * SolidWorks 2011 (and above)
        * Inventor 2011 (and above except 2014)
        * SolidEdge ST3 (and above)
        * AutoCAD 2013 (and above except 2014)
        * UG NX 10  (and above)
        * Catia V.5
       
    """,
    'data': [
             'security/base_plm_security.xml',
             'security/res.groups.csv',
             'security/ir.model.access.csv',
             'views/component_view.xml',
             'views/checkout_view.xml',
             'views/check_workflow.xml',
             'views/backupdoc_view.xml',
             'views/logging.xml',
             'views/board_view.xml',
             'views/document_view.xml',
             'views/res_config_view.xml',
             'views/compare_bom_view.xml',
             'views/component_view.xml',
             'views/document_relations.xml',
             'views/relations_view.xml',
             'views/description_sequence.xml',
             'views/description_view.xml',
             'views/sparebom_view.xml',            
             'views/material_sequence.xml',
             'views/material_view.xml',
             'views/finishing_sequence.xml',
             'views/finishing_view.xml',
             'views/codelist_view.xml',
             'views/doculist_view.xml',
             'reports/report/spare_parts_templates.xml',
             'reports/report/component_templates.xml',
             'reports/report/component_report.xml',
             'reports/report/component_kanban.xml',            
             'reports/report/document_templates.xml',
             'reports/report/document_report.xml',
             'reports/report/checkout_templates.xml',
             'reports/report/checkout_report.xml',
             'reports/report/bom_structure_templates.xml',
             'reports/report/bom_structure.xml',
             'reports/report/document_structure_templates.xml',
             'reports/mrp_report_structure.xml',
             'data/scheduled_action.xml',
       ],
    'demo': [
        ],
    'test': [
        ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
