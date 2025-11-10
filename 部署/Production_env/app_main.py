import os
os.environ["CUDA_VISIBLE_DEVICES"] = "2,3"
import json
from flask import Flask, request, jsonify
from ipdb  import set_trace
from loguru import logger
import pandas as pd
from typing import List, Dict, Any
import logging
import pdb
from bs4 import BeautifulSoup
import markdown
import re
import pdb
import sys
logger = logging.getLogger(__name__)

# 导入自定义类
from qms.pdf_markdown_extractor import SpecificationExtractor

log_file = open("/sgl-workspace/sglang/hkc/Production_env/log_output.log","w",encoding="utf-8")
sys.stdout = log_file
sys.stderr = log_file

app = Flask(__name__)

@app.route('/api/file/extract-fields', methods=['POST'])
def process_specification():
    """
    Flask接口：处理PDF和检验项目规格表
    """
    try:
        # 检查请求中是否包含文件
        if 'file' not in request.files:
            return jsonify({'error': '未提供PDF文件'}), 400
        
        # 检查是否提供了规格表数据（JSON格式）
        if not request.form.get('dataList'):
            return jsonify({'error': '未提供规格表数据(JSON格式)'}), 400
        
        # 获取上传的文件
        pdf_file = request.files['file']
        
        # 获取规格表JSON数据
        spec_data_json = request.form.get('dataList')
        
        try:
            # 解析JSON数据
            spec_data = json.loads(spec_data_json)
            
            # 验证数据格式
            if not isinstance(spec_data, list):
                return jsonify({'error': '规格表数据必须是列表格式'}), 400
                
            # 检查每个项目是否包含必需字段
            required_fields = ["项目代码", "检验项目", "类型", "上限", "下限", "单位"]
            for i, item in enumerate(spec_data):
                if not isinstance(item, dict):
                    return jsonify({'error': f'第{i+1}个项目必须是字典格式'}), 400
                
                missing_fields = [field for field in required_fields if field not in item]
                if missing_fields:
                    return jsonify({'error': f'第{i+1}个项目缺少必需字段: {missing_fields}'}), 400
            
            check_pro = spec_data
            map_pro = create_inspection_mapping(spec_data)
            check_pro = remove_key_from_list_dicts(check_pro, "项目代码")
            fix_program_list = [item["检验项目"] for item in check_pro]
            fix_program = any("雾度" in s for s in fix_program_list )

        except json.JSONDecodeError:
            return jsonify({'error': '规格表数据不是有效的JSON格式'}), 400
        
        # 读取PDF文件内容
        pdf_bytes = pdf_file.read()
        
        # 创建提取器实例
        extractor = SpecificationExtractor(backend="pipeline")
        
        # 解析PDF为Markdown
        logger.info("开始解析PDF...")
        md_content = extractor.parse_pdf_to_markdown(pdf_bytes)
        # 从Markdown中提取值并填充规格表
        logger.info("开始提取检验项目值...")
        filled_check_pro = extractor.extract_values_from_markdown(pdf_file, optimize_markdown_content(md_content), check_pro,fix_program)
        #添加项目代码
        filled_check_pro = complete_project_codes(filled_check_pro,map_pro)
        #大于100000的值转化为科学计数
        filled_check_pro = convert_large_numbers_to_scientific(filled_check_pro)

        # 返回结果
        return jsonify({
            'success': True,
            'dataList': filled_check_pro,
            'msg': '处理成功'
        })
        
    except Exception as e:
        logger.exception("处理失败: %s", e)  # 自动记录完整堆栈
        return jsonify({
            'success': False,
            'error': str(e),
            'msg': '处理失败'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({'status': 'healthy'})

@app.route('/api/file/extract-fields1', methods=['POST'])
def process_specification1():
    # 获取上传的文件
    pdf_file = request.files['file']
    # 读取PDF文件内容
    pdf_bytes = pdf_file.read()
    
    # 创建提取器实例
    extractor = SpecificationExtractor(backend="pipeline")
    
    # 解析PDF为Markdown
    logger.info("开始解析PDF...")
    md_content = extractor.parse_pdf_to_markdown(pdf_bytes)

    return md_content

def remove_key_from_list_dicts(data_list, key_to_remove):
    """
    从字典列表中删除指定的键
    
    参数:
    data_list: list - 字典列表
    key_to_remove: str - 要删除的键名
    
    返回:
    list - 删除指定键后的字典列表
    """
    return [
        {k: v for k, v in item.items() if k != key_to_remove}
        for item in data_list
    ]

# =================== 优化函数：移除图片 + 优化表格 ===================
def optimize_markdown_content(md_content: str) -> str:
    """
    极致简化 Markdown 内容以最小化 token 数量
    """
    # 删除图片
    content = re.sub(r'!\[.*?\]\(.*?\)', '', md_content)
    
    # 转换HTML表格为精简Markdown表格
    def simple_table(match):
        table_html = match.group(0)
        soup = BeautifulSoup(table_html, 'html.parser')
        table = soup.find('table')
        if not table:
            return ''
        
        rows = []
        for tr in table.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if cells:
                rows.append('|' + '|'.join(cells) + '|')
        
        if len(rows) < 2:
            return rows[0] if rows else ''
        
        sep = '|' + '|'.join(['---'] * (rows[0].count('|')-1)) + '|'
        return rows[0] + '\n' + sep + '\n' + '\n'.join(rows[1:])
    
    content = re.sub(r'<table.*?</table>', simple_table, content, flags=re.DOTALL)
    
    # 极致空白优化
    content = re.sub(r' +', ' ', content)  # 压缩多个空格为单个空格
    content = re.sub(r'[ \t]+\n', '\n', content)  # 删除行尾空格
    content = re.sub(r'\n{2,}', '\n\n', content)  # 压缩多余空行
    
    return content.strip()

def create_inspection_mapping(data_list):
    """
    建立检验项目到项目代码的映射字典
    
    Args:
        data_list: 包含检验项目数据的列表
    
    Returns:
        dict: 检验项目到项目代码的映射字典
    """
    mapping = {}
    for item in data_list:
        project_code = item.get("项目代码")
        inspection_item = item.get("检验项目")
        if project_code and inspection_item:
            mapping[inspection_item] = project_code
    return mapping

def complete_project_codes(data_list, mapping_dict):
    """
    根据映射字典为数据列表中缺失项目代码的项补充项目代码
    
    Args:
        data_list: 需要处理的数据列表（可能某些项缺少项目代码）
        mapping_dict: 检验项目到项目代码的映射字典
    
    Returns:
        list: 处理后的数据列表
    """
    for item in data_list:
        project_code = item.get("项目代码")
        inspection_item = item.get("检验项目")
        
        # 如果有检验项目但没有项目代码，且该检验项目在映射字典中
        if inspection_item and (not project_code or project_code == "") and inspection_item in mapping_dict:
            item["项目代码"] = mapping_dict[inspection_item]
    
    return data_list

def convert_large_numbers_to_scientific(data_list, threshold=100000):
    """
    将数据列表中上下限值大于阈值的数值转换为科学计数法（使用大写E）
    
    Args:
        data_list: 包含检验项目信息的字典列表
        threshold: 阈值，大于此值的数值将被转换为科学计数法，默认为100000
    
    Returns:
        list: 转换后的数据列表
    """
    def convert_value(value):
        """转换单个值为科学计数法（如果需要）"""
        try:
            # 排除无穷大、空值和非数值的情况
            if value in ['∞', '', None] or not isinstance(value, str):
                return value
            
            num = float(value)
            if abs(num) > threshold:
                # 使用大写E的科学计数法
                return f"{num:.2E}"
            else:
                return value
        except (ValueError, TypeError):
            return value
    
    # 创建副本以避免修改原始数据
    converted_list = []
    for item in data_list:
        converted_item = item.copy()
        converted_item['上限'] = convert_value(converted_item['上限'])
        converted_item['下限'] = convert_value(converted_item['下限'])
        converted_list.append(converted_item)
    
    return converted_list


if __name__ == '__main__':
    # 设置模型下载源（如果需要）
    os.environ['MINERU_MODEL_SOURCE'] = "local"
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=os.getenv("x-ai-port"), debug=False)
