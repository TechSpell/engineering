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

import base64

from odoo import api, models

from .book_collector import packDocuments
from .common import usefulInfos, emptyDocument, moduleName

thisModuleName=moduleName()


class report_plm_document(models.AbstractModel):
    _name = 'report.%s.document_pdf' %(thisModuleName)
    _description = 'Report PDF Document'

    @api.model
    def get_pdf_content(self, documents=None):
        ret = emptyDocument
        if len(documents)>0:
            docRepository, bookCollector = usefulInfos(self.env)
            documentContent=packDocuments(docRepository, documents, bookCollector)
            if len(documentContent)>0:
                ret=documentContent[0]
        return ret

    @api.model
    def render_qweb_pdf(self, documents=None, data=None):
        content = self.get_pdf_content(documents)
        byteString = b"data:application/pdf;base64," + base64.encodebytes(content)
        return byteString.decode('UTF-8')

    @api.model
    def _get_report_values(self, docids, data=None):
        documents = self.env['plm.document'].browse(docids)
        return {'docs': documents,
                'get_content': self.render_qweb_pdf}


class report_document_structure(models.AbstractModel):
    _template='%s.document_structure' %(thisModuleName)
    _name='report.%s' %(_template)
    _description = "Document Structure PDF Report"

    @api.model
    def get_structure(self, docids):
        children=[]
        docRels=self.env['plm.document.relation'].search([('parent_id', 'in', docids._ids),('link_kind', '=', 'HiTree')])
        for docRel in docRels:
            children.append(docRel.child_id)
        return list(set(children))

    @api.multi
    def get_children(self, myObject, level=0):
        result=[]

        def getLevelObjects(docobject, level):
            for l in docobject:
                for docId in self.get_structure(l):
                    res={}
                    res['name']=docId.name
                    res['revi']=docId.revisionid
                    res['minor']=docId.minorrevision
                    res['state']=docId.state
                    res['checkedout']=docId.checkout_user
                    res['preview']=docId.preview
                    res['level']=level
                    result.append(res)
                    getLevelObjects(docId, level+1)
            return result

        return getLevelObjects(myObject, level+1)

    @api.model
    def _get_report_values(self, docids, data=None):
        return {'docs': self.env['plm.document'].browse(docids),
                'get_children': self.get_children}

    @api.model
    def render_html(self, docids, data=None):
        report_obj = self.env['report']
        report_obj._get_report_from_name(self._template)
        docargs = {
            'doc_ids': docids,
            'doc_model': 'plm.document',
            'docs': self,
            'data': data,
            'get_children': self.get_children,
        }
        return self.env['report'].render(self._template, docargs)


class report_document_where_used(models.AbstractModel):
    _template='%s.document_where_used' %(thisModuleName)
    _name='report.%s' %(_template)
    _description = "Document Structure PDF Report"

    @api.model
    def get_where_used(self, docids):
        fathers=[]
        docRels=self.env['plm.document.relation'].search([('child_id', 'in', docids._ids),('link_kind', '=', 'HiTree')])
        for docRel in docRels:
            fathers.append(docRel.parent_id)
        return list(set(fathers))

    @api.multi
    def get_fathers(self, myObject, level=0):
        result=[]

        def getLevelObjects(docobject, level):
            for l in docobject:
                for docId in self.get_where_used(l):
                    res={}
                    res['name']=docId.name
                    res['revi']=docId.revisionid
                    res['minor']=docId.minorrevision
                    res['state']=docId.state
                    res['checkedout']=docId.checkout_user
                    res['preview']=docId.preview
                    res['level']=level
                    result.append(res)
                    getLevelObjects(docId, level+1)
            return result

        return getLevelObjects(myObject, level+1)

    @api.model
    def _get_report_values(self, docids, data=None):
        return {'docs': self.env['plm.document'].browse(docids),
                'get_children': self.get_fathers}

    @api.model
    def render_html(self, docids, data=None):
        report_obj = self.env['report']
        report_obj._get_report_from_name(self._template)
        docargs = {
            'doc_ids': docids,
            'doc_model': 'plm.document',
            'docs': self,
            'data': data,
            'get_children': self.get_fathers,
        }
        return self.env['report'].render(self._template, docargs)
