import os
import json
import ast
import requests
import regex as re
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.utils.enum_class import MakeMode
from mineru.backend.vlm.vlm_analyze import doc_analyze as vlm_doc_analyze
from mineru.backend.pipeline.pipeline_analyze import doc_analyze as pipeline_doc_analyze
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make as pipeline_union_make
from mineru.backend.pipeline.model_json_to_middle_json import result_to_middle_json as pipeline_result_to_middle_json
from mineru.backend.vlm.vlm_middle_json_mkcontent import union_make as vlm_union_make
from openai import OpenAI


class PDFMarkdownExtractor:
    """PDF转Markdown提取器基类"""
    
    def __init__(self, backend: str = "pipeline"):
        """
        初始化PDF提取器
        
        Args:
            backend: 使用的后端解析引擎 ("pipeline" 或 "vlm-*")
        """
        self.backend = backend
    
    def parse_pdf_to_markdown(self, pdf_bytes: bytes) -> str:
        """
        解析PDF为Markdown字符串
        
        Args:
            pdf_bytes: PDF文件的字节内容
        
        Returns:
            str: 解析后的Markdown内容
        """
        try:
            # 使用pipeline后端解析
            if self.backend == "pipeline":
                return self._parse_with_pipeline(pdf_bytes)
            
            # 使用VLM后端解析
            elif self.backend.startswith("vlm-"):
                backend_type = self.backend[4:]
                return self._parse_with_vlm(pdf_bytes, backend_type)
                
        except Exception as e:
            logger.error(f"PDF解析失败: {e}")
            raise
        
        return ""
    
    def _parse_with_pipeline(self, pdf_bytes: bytes) -> str:
        """使用pipeline后端解析PDF"""
        pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
        infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = pipeline_doc_analyze(
            [pdf_bytes], ["ch"], parse_method="auto", formula_enable=True, table_enable=True
        )
        
        if infer_results and len(infer_results) > 0:
            model_list = infer_results[0]
            images_list = all_image_lists[0]
            pdf_doc = all_pdf_docs[0]
            
            # 创建临时目录用于存储
            temp_dir = Path("/tmp/mineru_temp")
            temp_dir.mkdir(exist_ok=True)
            image_writer = FileBasedDataWriter(str(temp_dir))
            
            middle_json = pipeline_result_to_middle_json(
                model_list, images_list, pdf_doc, image_writer, "ch", ocr_enabled_list[0], True
            )
            
            pdf_info = middle_json["pdf_info"]
            md_content_str = pipeline_union_make(pdf_info, MakeMode.MM_MD, "")
            return md_content_str
        
        return ""
    
    def _parse_with_vlm(self, pdf_bytes: bytes, backend_type: str) -> str:
        """使用VLM后端解析PDF"""
        pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
        
        temp_dir = Path("/tmp/mineru_temp")
        temp_dir.mkdir(exist_ok=True)
        image_writer = FileBasedDataWriter(str(temp_dir))
        
        middle_json, _ = vlm_doc_analyze(pdf_bytes, image_writer=image_writer, backend=backend_type, server_url=None)
        
        pdf_info = middle_json["pdf_info"]
        md_content_str = vlm_union_make(pdf_info, MakeMode.MM_MD, "")
        return md_content_str


class SpecificationExtractor(PDFMarkdownExtractor):
    """规格表提取器（继承自PDFMarkdownExtractor）"""
    
    def __init__(self, backend: str = "pipeline"):
        super().__init__(backend)
        # self.client = OpenAI(
        #     api_key=os.getenv("DASHSCOPE_API_KEY"),
        #     base_url=os.getenv("DASHSCOPE_API_URL"),
        # )
        self.url = os.getenv("HK_API_URL")
        self.headers = {
            "Content-Type":"application/json",
            "x-ai-token":os.getenv("x-ai-token"),
            "x-user-code":os.getenv("x-user-code")
        }
    # content to datalist
    def process_content(self,full_content):
        try:
            # 1. 移除 <think>...</think> 标签及其内容
            cleaned_content = re.sub(r'<think>.*?</think>', '', full_content, flags=re.DOTALL)
            # 2. 移除残留的孤立标签
            cleaned_content = re.sub(r'</?think>', '', cleaned_content)
            # 3. 尝试提取并解析最外层的 [...] 结构
            # 使用正则表达式匹配最外层的方括号内容
            match = re.search(r'\[(?:[^[\]]|(?R))*\]', cleaned_content)
            outermost_content = match.group(0) if match else ""
            # 4.去除换行并转化为datalist
            clean_text = outermost_content.replace("\n", "")
            data_list = ast.literal_eval(clean_text)
            print("--- 清理后的内容 ---")
            print(data_list)
            print("--- 清理内容结束 ---\n")
            return data_list
        except:
            print("full_content decode is erro!")

    
    # --- 改进后的流式处理和解析函数 ---
    def stream_and_parse_sse_response(self, url: str, payload: dict, headers: dict) -> List[Dict[str, Any]]:
        """
        发送SSE请求，流式接收响应，并实时解析最终的数据。
        
        Args:
            url (str): 请求地址。
            payload (dict): 请求体。
            headers (dict): 请求头。
            
        Returns:
            string: 解析出的内容。
        """
        full_content = ""
        try:
            with requests.post(url, json=payload, headers=headers, stream=True) as response:
                if response.status_code == 200:
                    for line in response.iter_lines(decode_unicode=True):
                        if line and line.startswith('data:'):
                            data_str = line[5:].strip() # Remove 'data:'
                            if data_str == '[DONE]':
                                break
                            try:
                                chunk_data = json.loads(data_str)
                                # 标准OpenAI SSE流式响应结构
                                # --- 改进点：检查 'choices' 是否存在且非空 ---
                                if isinstance(chunk_data, dict) and 'choices' in chunk_data and chunk_data['choices']:
                                    delta = chunk_data['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        full_content += content
                                        # 实时打印流式内容（可选）
                                        print(content, end='', flush=True) 
                            except json.JSONDecodeError:
                                # 忽略无法解析的行
                                print(f"警告：无法解析SSE数据行: {data_str}")
                                continue
                else:
                    print(f"请求失败，状态码: {response.status_code}")
                    print(response.text) # 打印错误响应体
                    return ""

            # --- 解析累积的 full_content ---
            print("\n--- 接收到的完整内容 ---")
            print(full_content)
            print("--- 内容结束 ---\n")
            return full_content
        except Exception as e:
            print(f"流式处理或解析过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def extract_values_from_markdown(self, md_content: str, check_pro: list) -> list:
        """
        从Markdown内容中提取检验项目的值并填充规格表
        
        Args:
            md_content: Markdown内容字符串
            check_pro: 检验项目规格表数据列表
        
        Returns:
            list: 填充后的规格表数据列表
        """
        try:
            # 示例数据
            check_pro_sample_fill = [
            {'项目代码': 'RE01', '检验项目': '黏度', '类型': '定量', '上限': '2.94', '下限': '2.46', '单位': 'mPa·S'}, 
            {'项目代码': 'RE02', '检验项目': '固含量', '类型': '定量', '上限': '14', '下限': '13.4', '单位': '%'}, 
            {'项目代码': 'RE03', '检验项目': '膜厚', '类型': '定量', '上限': '2.93', '下限': '2.85', '单位': '%'}, 
            {'项目代码': 'RE04', '检验项目': '线幅', '类型': '定量', '上限': '66.37', '下限': '62.37', '单位': 'um'}, 
            {'项目代码': 'RE05', '检验项目': '白点', '类型': '定量', '上限': '3', '下限': '0.0', '单位': '-'}, 
            {'项目代码': 'RE07', '检验项目': '对比', '类型': '定量', '上限': '∞', '下限': '6842.0', '单位': '-'}, 
            {'项目代码': 'RE08', '检验项目': '固含量批配差', '类型': '定量', '上限': '0.12', '下限': '0.0', '单位': '%'},
            {'项目代码': 'RE09', '检验项目': '色度x', '类型': '定量', '上限': '0.1425', '下限': '0.1395', '单位': '-'}, 
            {'项目代码': 'RE10', '检验项目': '色度y', '类型': '定量', '上限': '0.091', '下限': '0.087', '单位': '-'}, 
            {'项目代码': 'RE11', '检验项目': '色度Y', '类型': '定量', '上限': '10.85', '下限': '9.95', '单位': '-'}, 
            {'项目代码': 'RE12', '检验项目': 'Residual thickness Ratio', '类型': '定量', '上限': '85.6', '下限': '81.6', '单位': '%'}, 
            {'项目代码': 'RE31', '检验项目': '来料运输温度确认', '类型': '定性', '上限': '15', '下限': '0.0', '单位': '℃'}, 
            {'项目代码': 'RE06', '检验项目': '现象时间', '类型': '定量', '上限': '17', '下限': '9.0', '单位': 'sec'}, 
            {'项目代码': 'RE27', '检验项目': '外观标识确认', '类型': '定性', '上限': '0', '下限': '0.0', '单位': '-'}, 
            {'项目代码': 'RE28', '检验项目': '外观标签确认', '类型': '定性', '上限': '0', '下限': '0.0', '单位': '-'}, 
            {'项目代码': 'RE29', '检验项目': '外观确认', '类型': '定性', '上限': '0', '下限': '0.0', '单位': '-'}
            ]
            
            # 准备提示词
            prom = self._build_prompt(md_content, check_pro, check_pro_sample_fill)
            
            # 调用OpenAI API
            # completion = self.client.chat.completions.create(
            #     model="deepseek-v3",
            #     extra_body={"enable_thinking": False},
            #     messages=[
            #         {'role': 'system', 'content': '你是一个专业的材料规格解析助手，请严格按照要求处理数据。'},
            #         {'role': 'user', 'content': prom}
            #     ]
            # )
            payload = {
            "model": "Qwen3-32B",
            "stream": True,      
            "messages": [
                {
                    "role": "user",
                    "content": prom
                }
            ]
        }

            # sse接口
            response_content = self.stream_and_parse_sse_response(self.url,payload,self.headers)
            
            # 获取API响应
            # response_content = completion.choices[0].message.content
            
            # 解析响应内容
            # result_data = self._parse_response(response_content)
            result_data = self.process_content(response_content)
            
            return result_data
            
        except Exception as e:
            logger.error(f"值提取失败: {e}")
            raise
    
    def _build_prompt(self, md_content: str, check_pro: list, sample_data: list) -> str:
        """构建提示词"""
        return f'''
            #背景#
            -你是一个屏幕制造商的材料规格表维护助手，能从markdown文件中提取检验项目的值，对值进行简单计算替换到材料规格表的上下限中,
            材料规格表中检验项目就是要去markdown中匹配的关键字段。
            下面为markdown文件内容:
            ======
            {md_content}
            ======
            下面为材料规格表
            ======
            {check_pro}
            ======

            #按以下步骤执行#
            1.理解材料规格表中的检验项目就是要去markdown中匹配的字段，不能多也不能少，检验项目的名称不能改变
            2.从markdown中匹配字段，匹配时优先匹配与检验项目字段名称完全一致的字段，当未匹配到时，匹配名称不同但含义相同的字段，例如water,水,h2o都属于一个含义，例如particle count和颗粒是一个含义，例如固形分和固含量是一个含义
            3.从markdown提取与字段匹配的值
            4.依据符号计算该字段的上下限值，例如，当提取为1.17±0.03,计算1.17-0.03=1.14,1.17+0.03=1.20,因此上限为1.20,下限为1.14
            5.单位换算，当提取的单位和材料规格表中不一致时,上下限的值换算为和材料规格表中单位一致,例如:1000g换算为1kg,1000换算为1 
            6.检查每一检验项目的上下限值，是否遵守规则，特别是长宽填反了要修正过来
            7.检查检验项目是否完整，保证和材料规格表上的检验项目数量一致

            #遵守下面规则#
            --规则1：使用新计算的上下限值替换材料规格表中原来的值，并且不能带有符号,不能确定上下限值时，填充原来的值
            --规则2：当检验项目的类型为定性时，上下限值保持材料规格表中原来的值
            --规则3：检验项目中，长的上下限值大于宽的上下限制值，不能填反
            --规则4：球标和球标尺寸都是球标尺寸，可从初期全尺寸报告和检查报告范本和尺寸标表中找到，例如，尺寸表中#01代表球标1尺寸，#02代表球标2尺寸，#03代表球标3尺寸
            --规则5：<td><x</td>或者<td>&lt;x</td>代表<x，<td>≤x</td>或者<td>&le;x</td>或者<td>&lt;=x</td>代表≤x，<td>≥x</td>或者<td>&ge;x</td>或者<td>&gt;=x</td>代表≥x，<td>>x</td>或者<td>&gt;x</td>代表>x
            --规则6：通常表面静电阻抗的下限为10的6次方数量级，上限为10的9次方数量级

                    
            #响应为列表格式#
            严格响应为如下格式，返回只包含检验代码，检验项目，类型，上限，下限，单位列名，不要返回任何其他内容
            参考如下：
            {sample_data}
            '''
    
    def _parse_response(self, response_content: str) -> list:
        """解析API响应"""
        try:
            # 尝试直接解析JSON
            return json.loads(response_content)
        except json.JSONDecodeError:
            try:
                # 如果不是标准JSON，尝试使用ast.literal_eval
                return ast.literal_eval(response_content)
            except:
                # 如果还是无法解析，尝试提取列表部分
                import re
                list_pattern = r'\[.*\]'
                match = re.search(list_pattern, response_content, re.DOTALL)
                if match:
                    return ast.literal_eval(match.group(0))
                else:
                    raise ValueError("无法解析API响应为列表格式")
    
    def translate_keys(self, data_list: List[Dict]) -> List[Dict]:
        """
        将字典列表中的中文键名替换为英文键名
        
        Args:
            data_list: 包含字典的列表，字典中包含中文键名
            
        Returns:
            list: 包含字典的列表，字典中的键名已替换为英文
        """
        # 定义中英文键名映射
        key_mapping = {
            "项目代码": "pro_code",
            "检验项目": "pro_name", 
            "类型": "pro_type",
            "上限": "pro_up",
            "下限": "pro_down",
            "单位": "pro_unit"
        }
        
        # 创建新的数据列表
        translated_data = []
        
        for item in data_list:
            new_item = {}
            for chinese_key, value in item.items():
                # 如果键名在映射中，使用英文键名，否则保留原键名
                english_key = key_mapping.get(chinese_key, chinese_key)
                new_item[english_key] = value
            translated_data.append(new_item)
        
        return translated_data
