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
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
#
#    To customize report layout :
#
#    1 - Configure final layout using bom_structure.sxw in OpenOffice
#    2 - Compile to bom_structure.rml using ..\base_report_designer\openerp_sxw2rml\openerp_sxw2rml.py
#           python openerp_sxw2rml.py bom_structure.sxw > bom_structure.rml
#
##############################################################################
import os
import logging
from operator import itemgetter

from odoo  import _, models, api
from odoo.report import report_sxw


def _moduleName():
    path = os.path.dirname(__file__)
    return os.path.basename(os.path.dirname(os.path.dirname(path)))
openerpModule=_moduleName()

def _thisModule():
    return os.path.splitext(os.path.basename(__file__))[0]
thisModule=_thisModule()

def _translate(value):
    return _(value)

###############################################################################################################à

def _createtemplate():
    """
        Automatic XML menu creation
    """
    filepath=os.path.dirname(__file__)
    fileName=thisModule+'.xml'
    fileOut = open(os.path.join(filepath,fileName), 'w')
    
    listout=[('bom_structure_all','bom_template_all','BOM All Levels','bom.structure.all')]
    listout.append(('bom_structure_one','bom_template_one','BOM One Level','bom.structure.one'))
    listout.append(('bom_structure_all_sum','bom_template_all_sum','BOM All Levels Summarized','bom.structure.all.sum'))
    listout.append(('bom_structure_one_sum','bom_template_one_sum','BOM One Level Summarized','bom.structure.one.sum'))
    listout.append(('bom_structure_leaves','bom_template_leaves','BOM Only Leaves Summarized','bom.structure.leaves'))
    listout.append(('bom_structure_flat','bom_template_flat','BOM All Flat Summarized','bom.structure.flat'))

    try:
        fileOut.write(u'<?xml version="1.0"?>\n<openerp>\n    <data>\n\n')
        fileOut.write(u'<!--\n       IMPORTANT : DO NOT CHANGE THIS FILE, IT WILL BE REGENERERATED AUTOMATICALLY\n-->\n\n')
      
        for label,template,description,name in listout:
            fileOut.write(u'        <report model="mrp.bom"\n')
            fileOut.write(u'                id="%s"\n                string="%s"\n                name="%s.%s"\n' %(label,description,openerpModule,name))
            fileOut.write(u'                file="%s.report.%s"\n' %(openerpModule,template))
            fileOut.write(u'                report_type="qweb-pdf"\n />\n')
        
        fileOut.write(u'<!--\n       IMPORTANT : DO NOT CHANGE THIS FILE, IT WILL BE REGENERERATED AUTOMATICALLY\n-->\n\n')
        fileOut.write(u'    </data>\n</openerp>\n')
        fileOut.close()
    except Exception as msg:
        logging.error("File '{name}' is not writable: it will use default reports.".format(name=fileName))
        logging.debug("Exception raised was: {msg}.".format(msg=msg))

_createtemplate()

###############################################################################################################à

def BomSort(myObject):
    valid=False
    bomobject=[]
    res={}
    index=0
    for l in myObject:
        res[str(index)]=l.itemnum
        index+=1
        if l.itemnum>0:
            valid=True
    if not valid:
        res={}
        index=0
        for l in myObject:
            res[str(index)]=l.product_id.product_tmpl_id.name
            index+=1
    items = res.items()
    items.sort(key = itemgetter(1))
    for res in items:
        bomobject.append(myObject[int(res[0])])
    return bomobject

def SummarizeBom(bomobject, level=1, result={}, ancestorName=""):

    for l in bomobject:
        evaluate=True
        fatherName=l.bom_id.product_id.name
        productName=l.product_id.name
        fatherRef="%s-%d" %(fatherName,level-1)
        productRef="%s-%s-%d" %(ancestorName,productName,level)
        if fatherRef in result:
            listed=result[fatherRef]
        else:
            result[fatherRef]={}
            listed={}
            
        if productRef in listed and listed[productRef]['father']==fatherName:
            res=listed[productRef]
            res['pqty']=res['pqty']+l.product_qty
            evaluate=False
        else:
            res={}
            res['product']=l.product_id
            res['name']=l.product_id.name
            res['ancestor']=ancestorName
            res['father']=fatherName
            res['pqty']=l.product_qty
            res['level']=level
            listed[productRef]=res
        
        result[fatherRef]=listed
        if evaluate:
            for bomId in l.product_id.bom_ids:
                if bomId.type == l.bom_id.type:
                    if bomId.bom_line_ids:
                        result.update(SummarizeBom(bomId.bom_line_ids, level+1, result,fatherName))
                        break

    return result

def QuantityInBom(listedBoM={}, productName=""):
    found=[]
    result=0.0
    for fatherRef in listedBoM.keys():
        for listedName in listedBoM[fatherRef]:
            listedline=listedBoM[fatherRef][listedName]
            if (listedline['name'] == productName) and not (listedline['father'] in found):
                result+=listedline['pqty'] * QuantityInBom(listedBoM, listedline['father'])    
                found.append(listedline['father'])
                break
    if not found:
        result=1.0
    return result

def bom_type(myObject):
    result = dict(myObject.fields_get()['type']['selection']).get(myObject.type, '')
    return _(result)

class BomStructureAllReport(models.AbstractModel):
    _name = 'report.%s.bom.structure.all' %(openerpModule)

    def get_children(self, myObject, level=0):
        result=[]

        def getLevelObjects(bomobject,level):
            myObject=BomSort(bomobject)

            for l in myObject:
                res={}
                product=l.product_id.product_tmpl_id
                res['name']=product.name
                res['item']=l.itemnum
                res['ancestor']=l.bom_id.product_id
                res['pname']=product.name
                res['pdesc']=_(product.description)
                res['pcode']=l.product_id.default_code
                res['previ']=product.engineering_revision
                res['pqty']=l.product_qty
                res['uname']=l.product_uom_id.name
                res['pweight']=product.weight
                res['code']=l.product_id.default_code
                res['level']=level
                result.append(res)
                for bomId in l.product_id.bom_ids:
                    if bomId.type == l.bom_id.type:
                        getLevelObjects(bomId.bom_line_ids,level+1)
            return result

        return getLevelObjects(myObject,level+1)

    @api.multi
    def render_html(self, docids, data=None):
        docargs = {
            'doc_ids': docids,
            'doc_model': 'mrp.bom',
            'docs': self.env['mrp.bom'].browse(docids),
            'get_children': self.get_children,
            'bom_type':bom_type,
            'data': data,
        }
        return self.env['report'].render('%s.bom_template_all'%(openerpModule), docargs)


class BomStructureOneReport(models.AbstractModel):
    _name = 'report.%s.bom.structure.one' %(openerpModule)

    def get_children(self, myObject, level=0):
        result=[]

        def getLevelObjects(bomobject,level):
            myObject=BomSort(bomobject)
            for l in myObject:
                res={}
                product=l.product_id.product_tmpl_id
                res['name']=product.name
                res['item']=l.itemnum
                res['pname']=product.name
                res['pdesc']=_(product.description)
                res['pcode']=l.product_id.default_code
                res['previ']=product.engineering_revision
                res['pqty']=l.product_qty
                res['uname']=l.product_uom_id.name
                res['pweight']=product.weight
                res['code']=l.product_id.default_code
                res['level']=level
                result.append(res)
            return result

        return getLevelObjects(myObject,level+1)

    @api.multi
    def render_html(self, docids, data=None):
        docargs = {
            'doc_ids': docids,
            'doc_model': 'mrp.bom',
            'docs': self.env['mrp.bom'].browse(docids),
            'get_children': self.get_children,
            'bom_type':bom_type,
            'data': data,
        }
        return self.env['report'].render('%s.bom_template_one'%(openerpModule), docargs)


class BomStructureAllSumReport(models.AbstractModel):
    _name = 'report.%s.bom.structure.all.sum' %(openerpModule)

    def get_children(self, myObject, level=0):
        result=[]
        results={}

        def getLevelObjects(bomobject, listedBoM, level, ancestor=""):
            listed=[]
            myObject=BomSort(bomobject)
            tmp_result=[]
            for l in myObject:
                productName=l.product_id.name
                if productName in listed:
                    continue
                res={}
                listed.append(productName)
                fatherName=l.bom_id.product_id.name
                fatherRef="%s-%d" %(fatherName, level-1)
                if fatherRef in listedBoM.keys():
                    listedName="%s-%s-%d" %(ancestor, productName, level)
                    if listedName in listedBoM[fatherRef]:
                        listedline=listedBoM[fatherRef][listedName]
                        product=listedline['product']
                        res['name']=product.name
                        res['item']=l.itemnum
                        res['pfather']=fatherName
                        res['pname']=product.name
                        res['pdesc']=_(product.description)
                        res['pcode']=l.product_id.default_code
                        res['previ']=product.engineering_revision
                        res['pqty']=listedline['pqty']
                        res['uname']=l.product_uom_id.name
                        res['pweight']=product.weight
                        res['code']=l.product_id.default_code
                        res['level']=level
                        tmp_result.append(res)
                        
                        for bomId in l.product_id.bom_ids:
                            if bomId.type == l.bom_id.type:
                                if bomId.bom_line_ids:
                                    tmp_result.extend(getLevelObjects(bomId.bom_line_ids,listedBoM,level+1,fatherName))
            return tmp_result

        results=SummarizeBom(myObject,level+1,results)
        result.extend(getLevelObjects(myObject,results,level+1))
        return result

    @api.multi
    def render_html(self, docids, data=None):
        docargs = {
            'doc_ids': docids,
            'doc_model': 'mrp.bom',
            'docs': self.env['mrp.bom'].browse(docids),
            'get_children': self.get_children,
            'bom_type':bom_type,
            'data': data,
        }
        return self.env['report'].render('%s.bom_template_all_sum'%(openerpModule), docargs)


class BomStructureOneSumReport(models.AbstractModel):
    _name = 'report.%s.bom.structure.one.sum' %(openerpModule)

    def get_children(self, myObject, level=0):
        result=[]

        def getLevelObjects(bomobject,level):
            myObject=BomSort(bomobject)
            tmp_result=[]
            listed={}
            keyIndex=0
            for l in myObject:
                res={}
                product=l.product_id.product_tmpl_id
                if product.name in listed.keys():
                    res=tmp_result[listed[product.name]]
                    res['pqty']=res['pqty']+l.product_qty
                    tmp_result[listed[product.name]]=res
                else:
                    res['name']=product.name
                    res['item']=l.itemnum
                    res['pname']=product.name
                    res['pdesc']=_(product.description)
                    res['pcode']=l.product_id.default_code
                    res['previ']=product.engineering_revision
                    res['pqty']=l.product_qty
                    res['uname']=l.product_uom_id.name
                    res['pweight']=product.weight
                    res['code']=l.product_id.default_code
                    res['level']=level
                    tmp_result.append(res)
                    listed[l.product_id.name]=keyIndex
                    keyIndex+=1
            result.extend(tmp_result)

        getLevelObjects(myObject,level+1)

        return result

    @api.multi
    def render_html(self, docids, data=None):
        docargs = {
            'doc_ids': docids,
            'doc_model': 'mrp.bom',
            'docs': self.env['mrp.bom'].browse(docids),
            'get_children': self.get_children,
            'bom_type':bom_type,
            'data': data,
        }
        return self.env['report'].render('%s.bom_template_one_sum'%(openerpModule), docargs)


class BomStructureLeavesReport(models.AbstractModel):
    _name = 'report.%s.bom.structure.leaves' %(openerpModule)

    def get_children(self, myObject, level=0):
        result=[]
        results={}
        listed=[]

        def getLevelObjects(bomobject, listedBoM, listed, level, ancestor=""):
            
            myObject=BomSort(bomobject)
            tmp_result=[]
            for l in myObject:
                productName=l.product_id.name
                if productName in listed:
                    continue
                res={}
                listed.append(productName)
                fatherName=l.bom_id.product_id.name
                fatherRef="%s-%d" %(fatherName, level-1)
                if fatherRef in listedBoM.keys():
                    listedName="%s-%s-%d" %(ancestor, productName, level)
                    if listedName in listedBoM[fatherRef]:
                        listedline=listedBoM[fatherRef][listedName]
                        product=listedline['product']
                        productRef="%s-%d" %(product.name, level)
                        if not productRef in listedBoM.keys():
                            quantity=QuantityInBom(listedBoM, product.name)
                            res['name']=product.name
                            res['item']=l.itemnum
                            res['pfather']=fatherName
                            res['pname']=product.name
                            res['pdesc']=_(product.description)
                            res['pcode']=l.product_id.default_code
                            res['previ']=product.engineering_revision
                            res['pqty']=quantity
                            res['uname']=l.product_uom_id.name
                            res['pweight']=product.weight
                            res['code']=l.product_id.default_code
                            res['level']=level
                            tmp_result.append(res)
                        
                        for bomId in l.product_id.bom_ids:
                            if bomId.type == l.bom_id.type:
                                if bomId.bom_line_ids:
                                    tmp_result.extend(getLevelObjects(bomId.bom_line_ids,listedBoM,listed,level+1,fatherName))
            return tmp_result

        results=SummarizeBom(myObject,level+1,results)
        result.extend(getLevelObjects(myObject,results,listed,level+1))
        return result

    @api.multi
    def render_html(self, docids, data=None):
        docargs = {
            'doc_ids': docids,
            'doc_model': 'mrp.bom',
            'docs': self.env['mrp.bom'].browse(docids),
            'get_children': self.get_children,
            'bom_type':bom_type,
            'data': data,
        }
        return self.env['report'].render('%s.bom_template_leaves'%(openerpModule), docargs)


class BomStructureFlatReport(models.AbstractModel):
    _name = 'report.%s.bom.structure.flat' %(openerpModule)

    def get_children(self, myObject, level=0):
        result=[]
        results={}
        listed=[]

        def getLevelObjects(bomobject, listedBoM, listed, level, ancestor=""):
            
            myObject=BomSort(bomobject)
            tmp_result=[]
            for l in myObject:
                productName=l.product_id.name
                if productName in listed:
                    continue
                res={}
                listed.append(productName)
                fatherName=l.bom_id.product_id.name
                fatherRef="%s-%d" %(fatherName, level-1)
                if fatherRef in listedBoM.keys():
                    listedName="%s-%s-%d" %(ancestor, productName, level)
                    if listedName in listedBoM[fatherRef]:
                        listedline=listedBoM[fatherRef][listedName]
                        product=listedline['product']
                        quantity=QuantityInBom(listedBoM, product.name)
                        res['name']=product.name
                        res['item']=l.itemnum
                        res['pfather']=fatherName
                        res['pname']=product.name
                        res['pdesc']=_(product.description)
                        res['pcode']=l.product_id.default_code
                        res['previ']=product.engineering_revision
                        res['pqty']=quantity
                        res['uname']=l.product_uom_id.name
                        res['pweight']=product.weight
                        res['code']=l.product_id.default_code
                        res['level']=level
                        tmp_result.append(res)
                        
                        for bomId in l.product_id.bom_ids:
                            if bomId.type == l.bom_id.type:
                                if bomId.bom_line_ids:
                                    tmp_result.extend(getLevelObjects(bomId.bom_line_ids,listedBoM,listed,level+1,fatherName))
            return tmp_result

        results=SummarizeBom(myObject,level+1,results)
        result.extend(getLevelObjects(myObject,results,listed,level+1))
        return result
        
    @api.multi
    def render_html(self, docids, data=None):
        docargs = {
            'doc_ids': docids,
            'doc_model': 'mrp.bom',
            'docs': self.env['mrp.bom'].browse(docids),
            'get_children': self.get_children,
            'bom_type':bom_type,
            'data': data,
        }
        return self.env['report'].render('%s.bom_template_flat'%(openerpModule), docargs)
