## -*- coding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2016 TechSpell srl (<http://techspell.eu>). All Rights Reserved
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
import time
from operator import itemgetter

from openerp  import _, models, api
from openerp.report import report_sxw


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

    fileOut.write(u'<?xml version="1.0"?>\n<openerp>\n    <data>\n\n')
    fileOut.write(u'<!--\n       IMPORTANT : DO NOT CHANGE THIS FILE, IT WILL BE REGENERERATED AUTOMATICALLY\n-->\n\n')
  
    for label,template,description,name in listout:
        fileOut.write(u'        <report model="mrp.bom"\n')
        fileOut.write(u'                id="report_%s"\n                string="%s"\n                name="%s.%s"\n' %(label,description,openerpModule,template))
        fileOut.write(u'                report_type="qweb-pdf"\n />\n')
    
    fileOut.write(u'<!--\n       IMPORTANT : DO NOT CHANGE THIS FILE, IT WILL BE REGENERERATED AUTOMATICALLY\n-->\n\n')
    fileOut.write(u'    </data>\n</openerp>\n')
    fileOut.close()
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


class BomStructureAllReport(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(BomStructureAllReport, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_children':self.get_children,
            'bom_type':bom_type,
        })

    def get_children(self, myObject, level=0):
        result=[]

        def _get_rec(bomobject,level):
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
                res['uname']=l.product_uom.name
                res['pweight']=product.weight
                res['code']=l.product_id.default_code
                res['level']=level
                result.append(res)
                for bomId in l.product_id.bom_ids:
                    if bomId.type == l.bom_id.type:
                        _get_rec(bomId.bom_line_ids,level+1)
            return result

        children=_get_rec(myObject,level+1)
        return children

class report_bom_template_all(models.AbstractModel):
    _name = 'report.%s.bom_template_all' %(openerpModule)
    _inherit = 'report.abstract_report'
    _template = '%s.bom_template_all' %(openerpModule)
    _wrapped_report_class = BomStructureAllReport


class BomStructureOneReport(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(BomStructureOneReport, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_children':self.get_children,
            'bom_type':bom_type,
        })

    def get_children(self, myObject, level=0):
        result=[]

        def _get_rec(bomobject,level):
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
                res['uname']=l.product_uom.name
                res['pweight']=product.weight
                res['code']=l.product_id.default_code
                res['level']=level
                result.append(res)
            return result

        children=_get_rec(myObject,level+1)
        return children

class report_bom_template_one(models.AbstractModel):
    _name = 'report.%s.bom_template_one' %(openerpModule)
    _inherit = 'report.abstract_report'
    _template = '%s.bom_template_one' %(openerpModule)
    _wrapped_report_class = BomStructureOneReport


class BomStructureAllSumReport(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(BomStructureAllSumReport, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_children':self.get_children,
            'bom_type':bom_type,
        })


    def get_children(self, myObject, level=0):
        result=[]
        results={}

        def _get_rec(bomobject, listedBoM, level, ancestor=""):
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
                        res['uname']=l.product_uom.name
                        res['pweight']=product.weight
                        res['code']=l.product_id.default_code
                        res['level']=level
                        tmp_result.append(res)
                        
                        for bomId in l.product_id.bom_ids:
                            if bomId.type == l.bom_id.type:
                                if bomId.bom_line_ids:
                                    tmp_result.extend(_get_rec(bomId.bom_line_ids,listedBoM,level+1,fatherName))
            return tmp_result

        results=SummarizeBom(myObject,level+1,results)
        result.extend(_get_rec(myObject,results,level+1))
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


class report_bom_template_all_sum(models.AbstractModel):
    _name = 'report.%s.bom_template_all_sum' %(openerpModule)
    _inherit = 'report.abstract_report'
    _template = '%s.bom_template_all_sum' %(openerpModule)
    _wrapped_report_class = BomStructureAllSumReport


class BomStructureOneSumReport(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(BomStructureOneSumReport, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_children':self.get_children,
            'bom_type':bom_type,
        })

    def get_children(self, myObject, level=0):
        result=[]

        def _get_rec(bomobject,level):
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
                    res['uname']=l.product_uom.name
                    res['pweight']=product.weight
                    res['code']=l.product_id.default_code
                    res['level']=level
                    tmp_result.append(res)
                    listed[l.product_id.name]=keyIndex
                    keyIndex+=1
            return result.extend(tmp_result)

        children=_get_rec(myObject,level+1)

        return result

class report_bom_template_one_sum(models.AbstractModel):
    _name = 'report.%s.bom_template_one_sum' %(openerpModule)
    _inherit = 'report.abstract_report'
    _template = '%s.bom_template_one_sum' %(openerpModule)
    _wrapped_report_class = BomStructureOneSumReport


class BomStructureLeavesReport(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(BomStructureLeavesReport, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_children':self.get_children,
            'bom_type':bom_type,
        })

    def get_children(self, myObject, level=0):
        result=[]
        results={}
        listed=[]

        def _get_rec(bomobject, listedBoM, listed, level, ancestor=""):
            
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
                            res['uname']=l.product_uom.name
                            res['pweight']=product.weight
                            res['code']=l.product_id.default_code
                            res['level']=level
                            tmp_result.append(res)
                        
                        for bomId in l.product_id.bom_ids:
                            if bomId.type == l.bom_id.type:
                                if bomId.bom_line_ids:
                                    tmp_result.extend(_get_rec(bomId.bom_line_ids,listedBoM,listed,level+1,fatherName))
            return tmp_result

        results=SummarizeBom(myObject,level+1,results)
        result.extend(_get_rec(myObject,results,listed,level+1))
        return result

class report_bom_template_leaves(models.AbstractModel):
    _name = 'report.%s.bom_template_leaves' %(openerpModule)
    _inherit = 'report.abstract_report'
    _template = '%s.bom_template_leaves' %(openerpModule)
    _wrapped_report_class = BomStructureLeavesReport


class BomStructureFlatReport(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(BomStructureFlatReport, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_children':self.get_children,
            'bom_type':bom_type,
        })

    def get_children(self, myObject, level=0):
        result=[]
        results={}
        listed=[]

        def _get_rec(bomobject, listedBoM, listed, level, ancestor=""):
            
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
                        res['uname']=l.product_uom.name
                        res['pweight']=product.weight
                        res['code']=l.product_id.default_code
                        res['level']=level
                        tmp_result.append(res)
                        
                        for bomId in l.product_id.bom_ids:
                            if bomId.type == l.bom_id.type:
                                if bomId.bom_line_ids:
                                    tmp_result.extend(_get_rec(bomId.bom_line_ids,listedBoM,listed,level+1,fatherName))
            return tmp_result

        results=SummarizeBom(myObject,level+1,results)
        result.extend(_get_rec(myObject,results,listed,level+1))
        return result
        
class report_bom_template_flat(models.AbstractModel):
    _name = 'report.%s.bom_template_flat' %(openerpModule)
    _inherit = 'report.abstract_report'
    _template = '%s.bom_template_flat' %(openerpModule)
    _wrapped_report_class = BomStructureFlatReport
