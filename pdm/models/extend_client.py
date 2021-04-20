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

from odoo import models


class plm_component(models.Model):
    _name = 'product.product'
    _inherit = 'product.product'
    
###################################################################
#   Override these properties to customize editor properties.     #
###################################################################

    def editorProperties(self, editor=""):
        """
            Assigns generic or specific name to editor properties
        """
        #                                        internal               editor       data
        #                                          name                  name        type
        properties={
                'engineering_code':         [ 'engineering_code',      "COMPNAME",  "char",     ],
                'engineering_revision':     [ 'engineering_revision',  "COMPPROG",  "int",      ],
                'engineering_material':     [ 'engineering_material',  "COMPMAT",   "char",     ],
                'engineering_treatment':    [ 'engineering_treatment', "COMPTTERM", "char",     ],
                'engineering_surface':      [ 'engineering_surface',   "COMPTSUP",  "char",     ],
                'description':              [ 'description',           "COMPDES",   "char",     ],
                'weight':                   [ 'weight',                "COMPPESO",  "float",    ],
                }
        if editor=='thinkdesign':
            properties={
                'engineering_code':         [ 'engineering_code',      "COMPNAME",  "char",     ],
                'engineering_revision':     [ 'engineering_revision',  "COMPPROG",  "int",      ],
                'engineering_material':     [ 'engineering_material',  "COMPMAT",   "char",     ],
                'engineering_treatment':    [ 'engineering_treatment', "COMPTTERM", "char",     ],
                'engineering_surface':      [ 'engineering_surface',   "COMPTSUP",  "char",     ],
                'description':              [ 'description',           "COMPDES",   "char",     ],
                'weight':                   [ 'weight',                "COMPPESO",  "float",    ],
               }
        return properties
    
    def defineProperties(self):
        """
            Defines the property set to be used
        """
        properties = {
                    "name"                  :{"changed":"", "enabled":True,  "mandatory":True,   "default":"",   "limit":40,                     },   
                    "engineering_code"      :{"changed":"", "enabled":True,  "mandatory":True,   "default":"",   "limit":40,                     },   
                    "engineering_revision"  :{"changed":"", "enabled":False, "mandatory":True,   "default":0 ,                                   },   
                    "std_description"       :{"changed":"", "enabled":True,  "mandatory":False,  "default":"",   "limit":40,                     },   
                    "state"                 :{"changed":"", "enabled":False, "mandatory":False,  "default":"draft",                              },   
                    "tmp_material"          :{"changed":"", "enabled":True,  "mandatory":False,  "default":"",                                   },   
                    "tmp_surface"           :{"changed":"", "enabled":True,  "mandatory":False,  "default":"",   "limit":40,                     },   
                    "weight"                :{"changed":"", "enabled":True,  "mandatory":False,  "default": 0.0,                                 },   
                    "engineering_material"  :{"changed":"", "enabled":True,  "mandatory":False,  "default":"",                                   },   
                    "engineering_surface"   :{"changed":"", "enabled":True,  "mandatory":False,  "default":"",   "limit":40,                     },   
                    "description"           :{"changed":"", "enabled":True,  "mandatory":False,  "default":"",   "limit":40, "multiline": True,  },   
                    "description_sale"      :{"changed":"", "enabled":True,  "mandatory":False,  "default":"",   "limit":40, "multiline": True,  },   
                    "description_purchase"  :{"changed":"", "enabled":True,  "mandatory":False,  "default":"",   "limit":40, "multiline": True,  },   
                    "linkeddocuments"       :{"changed":"", "enabled":True,  "mandatory":False,  "default":0,                "viewonly":True,    },   
                     }                       # ========================================= User Setup ============================================== #   
        #   Defines code rules when needed:
        properties['name'].update(                                          # Entity field to consider as P/N
            {"code": {
                "entity"        : "plm.codelist",                           # Entity where list values to choose
                "field"         : "name",                                   # Field to use evaluating P/N
                "alias"         : "engineering_code",                       # Other field which writing value
#                 "showcolumns"   : ["name", "description", "sequence"],      # Entity fields to show on ListCtrl
                            } 
            })
        properties['engineering_code'].update(
            {"code": {
                "entity"        : "plm.codelist", 
                "field"         : "name",
                "alias"         : "name",
#                 "showcolumns"   : ["name", "description", "sequence"],  
                            } 
            })
        #   Defines automation when needed:
#         properties['uom_id'].update(                                            # Entity field to apply automation button
#             {"automation": {
#                 "source"        : { "entity" : "product.product",               # Entity where list values to choose
#                                     "field"  : "uom_id",                        # Field to use as data source (reading its value).
#                                     "alias"  : "uom_id",                        # Field to use as data source (alternative to 'field', if Void value).
#                                 },
#                 "method"        : { "entity" : "product.product",               # Entity where to invoke the method
#                                     "name"   : "GetUoM",                        # Method name to invoke on server
#                                 },
#                 "destination"   : { "entity" : "product.product",               # Entity where list values to choose
#                                     "fields" : ["uom_po_id",],                  # Fields to use as destination (writing the value)
#                                 },
#                             } 
#     })
#         properties['uom_id'].update(                                            # Entity field to apply automation button
#             {"automation": {
#                 "destination"   : { "fields" : ["uom_po_id",],                  # Fields to use as destination (writing the value)
#                                 },
#                             } 
#              })
#         properties['uom_po_id'].update(                                         # Entity field to apply automation button
#             {"automation": {
#                 "destination"   : { "fields" : ["uom_id",],                     # Fields to use as destination (writing the value)
#                                 },
#                             } 
#              })
        properties['tmp_material'].update(                                        # Entity field to apply automation button
            {"automation": {
                "source"        : { 
                                    "objectfield"  : "name",                      # Field to be used as data source (reading its value) for chosen object related.
                                },
                "destination"   : { 
                                    "fields" : ["engineering_material",],         # Fields to use as destination (writing the value)
                                },
                            },
            })
        properties['tmp_surface'].update(                                         # Entity field to apply automation button
            {"automation": {
                "source"        : { 
                                    "objectfield"  : "name",                      # Field to be used as data source (reading its value) for chosen object related.
                                },
                "destination"   : { 
                                    "fields" : ["engineering_surface",],          # Fields to use as destination (writing the value)
                                },
                            },
            })
        return properties

###################################################################
#   Override these properties to customize editor properties.     #
###################################################################

    def WFStatuses(self):
        statuses={
            'draft':         { "label": "In Progress",  "entity":"", },
            'confirmed':     { "label": "Confirmed",    "entity":"", },
            'released':      { "label": "Released",     "entity":"", },
            'obsoleted':     { "label": "Obsoleted",    "entity":"", },
            'uploaded':      { "label": "Uploaded",     "entity":"", },
            }
        return statuses

    def WFTransitions(self):
        transitions={
            'draft_confirmed':  {
                                "label": "Confirm",  
                                "initial":   {"status":"draft",      "action":""}, 
                                "final":     {"status":"confirmed",  "action":""}, 
                                },
            'confirmed_draft':  {
                                "label": "Correct",  
                                "initial":   {"status":"confirmed",  "action":""}, 
                                "final":     {"status":"draft",      "action":""}, 
                                },
            'confirmed_released':  { 
                                "label": "Release",  
                                "initial":   {"status":"confirmed",  "action":""}, 
                                "final":     {"status":"released",   "action":""}, 
                                },
            'released_obsoleted':  { 
                                "label": "Obsolete",  
                                "initial":   {"status":"released",  "action":""}, 
                                "final":     {"status":"obsoleted", "action":""}, 
                                },
            'obsoleted_released':  { 
                                "label": "Reactivate",  
                                "initial":   {"status":"obsoleted",  "action":""}, 
                                "final":     {"status":"released",   "action":""}, 
                                },
            'draft_uploaded':   { 
                                "label": "In Upload",  
                                "initial":   {"status":"draft",      "action":""}, 
                                "final":     {"status":"uploaded",   "action":""}, 
                                },
            'uploaded_draft':   {
                                "label": "From Upload",  
                                "initial":   {"status":"uploaded",   "action":""}, 
                                "final":     {"status":"draft",      "action":""}, 
                                },
            }
        return transitions

    def WFActions(self):
        actions={
            'todraft':          { "label": "To InProgress",     "method":"", },
            'toconfirm':        { "label": "To Confirm",        "method":"", },
            'torelease':        { "label": "To Release",        "method":"", },
            'toobsolete':       { "label": "To Obsolete",       "method":"", },
            'toreactivate':     { "label": "To Reactivate",     "method":"", },
            'toupload':         { "label": "To Upload",         "method":"", },
            }
        return actions


class plm_document(models.Model):
    _name = 'plm.document'
    _inherit = 'plm.document'

###################################################################
#   Override these properties to customize editor properties.     #
###################################################################
    def editorProperties(self, editor=""):
        """
            Assigns generic or specific name to editor properties
        """
        #                             internal               editor       data
        #                               name                  name        type
        properties={
               "name":             [ "name",               "DOCNAME",    "char",     ],
               "revisionid":       [ "revisionid",         "DOCPROG",    "int" ,     ],
               "minorrevision":    [ "minorrevision",      "DOCMINPROG", "char",     ],
               "usedforspare":     [ "usedforspare",       "SPAREFLAG",  "bool",     ],
#                "docudescription":  [ "docudescription",    "DOCDES",     "char",     ],               "create_date":      [ "created",            "DOCCDATE",   "date",     ],
               "create_date":      [ "created",            "DOCCDATE",   "date",     ],
               "create_uid":       [ "creator",            "DOCOPEC",    "char",     ],
               "write_uid":        [ "modified",           "DOCOPEM",    "char",     ],
               "write_date":       [ "modifier",           "DOCMDATE",   "date",     ],
                }
        if editor=='thinkdesign':
            properties={
               "name":             [ "name",               "DOCNAME",    "char",     ],
               "revisionid":       [ "revisionid",         "DOCPROG",    "int" ,     ],
               "minorrevision":    [ "minorrevision",      "DOCMINPROG", "char",     ],
               "usedforspare":     [ "usedforspare",       "SPAREFLAG",  "bool",     ],
#                "docudescription":  [ "docudescription",    "DOCDES",     "char",     ],
               "create_date":      [ "created",            "DOCCDATE",   "date",     ],
               "create_uid":       [ "creator",            "DOCOPEC",    "char",     ],
               "write_uid":        [ "modified",           "DOCOPEM",    "char",     ],
               "write_date":       [ "modifier",           "DOCMDATE",   "date",     ],
                }
        return properties
    
    def defineProperties(self):
        """
            Defines the property set to be used
        """
        properties = {
                    "name"                  :{"changed":"",  "enabled":True,  "mandatory":True,   "limit":40, "default":"",      "code":True,                                  },   
                    "revisionid"            :{"changed":"",  "enabled":False, "mandatory":True,               "default":0,                                                     },   
                    "minorrevision"         :{"changed":"",  "enabled":False, "mandatory":True,   "limit":40, "default":"A",                                                   },   
                    "usedforspare"          :{"changed":"",  "enabled":True,  "mandatory":False,              "default":False,                                                 },   
                    "state"                 :{"changed":"",  "enabled":False, "mandatory":False,  "limit":40, "default":"draft",                                               },   
#                     "docudescription"       :{"changed":"",  "enabled":True,  "mandatory":False,  "limit":40, "default":"",      "multiline":True,                             },   
                    "create_date"           :{"changed":"",  "enabled":False, "mandatory":True,   "limit":40, "default":"now()", "show":"date",                                },   
                    "write_date"            :{"changed":"",  "enabled":False, "mandatory":True,   "limit":40, "default":"now()", "show":"date", "format": "%Y-%m-%d %H:%M:%S", },   
                    "linkedcomponents"      :{"changed":"",  "enabled":False, "mandatory":False,              "default":0,       "viewonly":True,                              },   
                   }                       # =========================================================== User Setup ========================================================== #
        #   Defines code rules when needed:
        properties['name'].update(                                          # Entity field to consider as P/N
            {"code": {
                "entity"        : "plm.doculist",                           # Entity where list values to choose
                "field"         : "name",                                   # Field to use evaluating P/N
#                 "alias"         : "alter_code",                             # Other field which writing value
#                 "showcolumns"   : ["name", "description", "sequence"],      # Entity fields to show on ListCtrl
                    } 
            })
        #   Defines automation when needed:
#         properties['name'].update(
#             {"automation": {
#                 "source"        : {"entity":"product.product", "field":"name", "alias": "engineering_code"},  
#                 "method"        : {"name":"GetNextDocumentName", "side":"server"},  
#                 "destination"   : {"entity":"plm.document", "field":"name"},  
#                             } 
#             })
        return properties

###################################################################
#   Override these properties to customize editor properties.     #
###################################################################

    def WFStatuses(self):
        statuses={
            'draft':         { "label": "In Progress",  "entity":"", },
            'confirmed':     { "label": "Confirmed",    "entity":"", },
            'released':      { "label": "Released",     "entity":"", },
            'obsoleted':     { "label": "Obsoleted",    "entity":"", },
            'uploaded':      { "label": "Uploaded",     "entity":"", },
            }
        return statuses

    def WFTransitions(self):
        transitions={
            'draft_confirmed':  {
                                "label": "Confirm",  
                                "initial":   {"status":"draft",      "action":""}, 
                                "final":     {"status":"confirmed",  "action":""}, 
                                },
            'confirmed_draft':  {
                                "label": "Correct",  
                                "initial":   {"status":"confirmed",  "action":""}, 
                                "final":     {"status":"draft",      "action":""}, 
                                },
            'confirmed_released':  { 
                                "label": "Release",  
                                "initial":   {"status":"confirmed",  "action":""}, 
                                "final":     {"status":"released",   "action":""}, 
                                },
            'released_obsoleted':  { 
                                "label": "Obsolete",  
                                "initial":   {"status":"released",  "action":""}, 
                                "final":     {"status":"obsoleted", "action":""}, 
                                },
            'obsoleted_released':  { 
                                "label": "Reactivate",  
                                "initial":   {"status":"obsoleted",  "action":""}, 
                                "final":     {"status":"released",   "action":""}, 
                                },
            'draft_uploaded':   { 
                                "label": "In Upload",  
                                "initial":   {"status":"draft",      "action":""}, 
                                "final":     {"status":"uploaded",   "action":""}, 
                                },
            'uploaded_draft':   {
                                "label": "From Upload",  
                                "initial":   {"status":"uploaded",   "action":""}, 
                                "final":     {"status":"draft",      "action":""}, 
                                },
            }
        return transitions

    def WFActions(self):
        actions={
            'todraft':          { "label": "To InProgress",     "method":"", },
            'toconfirm':        { "label": "To Confirm",        "method":"", },
            'torelease':        { "label": "To Release",        "method":"", },
            'toobsolete':       { "label": "To Obsolete",       "method":"", },
            'toreactivate':     { "label": "To Reactivate",     "method":"", },
            'toupload':         { "label": "To Upload",         "method":"", },
            }
        return actions


class plm_relation(models.Model):
    _name = 'mrp.bom'
    _inherit = 'mrp.bom'

###################################################################
#   Override these properties to customize editor properties.     #
###################################################################
    def editorProperties(self, editor=""):
        """
            Assigns generic or specific name to editor properties
        """
        #                             internal               editor       data
        #                               name                  name        type
        properties={
               "itemnum":          [ "itemnum",            "RELPOS",    "int",     ],
               "product_qty":      [ "itemqty",            "RELQTY",    "float" ,  ],
                }
        if editor=='thinkdesign':
            properties={
               "itemnum":          [ "itemnum",            "RELPOS",    "int",     ],
               "product_qty":      [ "itemqty",            "RELQTY",    "float" ,  ],
                }
        return properties
    
    def defineProperties(self):
        """
            Defines the property set to be used
        """
        properties = {
                    "itemlbl"        :{"changed":"", "enabled":True,  "mandatory":False,  "default":"",   "limit":40,                     },   
                    "itemnum"        :{"changed":"", "enabled":True,  "mandatory":False,  "default":0 ,                                   },   
                    "product_qty"    :{"changed":"", "enabled":True,  "mandatory":False,  "default":0.0 ,                                 },   
                    "itemdim1"       :{"changed":"", "enabled":True,  "mandatory":False,  "default":0.0 ,                                 },   
                    "itemdim2"       :{"changed":"", "enabled":True,  "mandatory":False,  "default":0.0 ,                                 },   
                    "itemdim3"       :{"changed":"", "enabled":True,  "mandatory":False,  "default":0.0 ,                                 },   
                    }                # ========================================= User Setup ============================================== #   
        return properties

    def WFStatuses(self):
        statuses={
            'draft':         { "label": "In Progress",  "entity":"", },
            'confirmed':     { "label": "Confirmed",    "entity":"", },
            'released':      { "label": "Released",     "entity":"", },
            'obsoleted':     { "label": "Obsoleted",    "entity":"", },
            }
        return statuses

    def WFTransitions(self):
        transitions={
            'draft_confirmed':  {
                                "label": "Confirm",  
                                "initial":   {"status":"draft",      "action":""}, 
                                "final":     {"status":"confirmed",  "action":""}, 
                                },
            'confirmed_draft':  {
                                "label": "Correct",  
                                "initial":   {"status":"confirmed",  "action":""}, 
                                "final":     {"status":"draft",      "action":""}, 
                                },
            'confirmed_released':  { 
                                "label": "Release",  
                                "initial":   {"status":"confirmed",  "action":""}, 
                                "final":     {"status":"released",   "action":""}, 
                                },
            'released_obsoleted':  { 
                                "label": "Obsolete",  
                                "initial":   {"status":"released",  "action":""}, 
                                "final":     {"status":"obsoleted", "action":""}, 
                                },
            'obsoleted_released':  { 
                                "label": "Reactivate",  
                                "initial":   {"status":"obsoleted",  "action":""}, 
                                "final":     {"status":"released",   "action":""}, 
                                },
            }
        return transitions

    def WFActions(self):
        actions={
            'todraft':          { "label": "To InProgress",     "method":"", },
            'toconfirm':        { "label": "To Confirm",        "method":"", },
            'torelease':        { "label": "To Release",        "method":"", },
            'toobsolete':       { "label": "To Obsolete",       "method":"", },
            'toreactivate':     { "label": "To Reactivate",     "method":"", },
            'toupload':         { "label": "To Upload",         "method":"", },
            }
        return actions

