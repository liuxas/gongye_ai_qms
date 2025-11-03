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
from ipdb import set_trace


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
    """规格表提取器（继承自PDFMarkdownExtractor)"""
    
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
        发送SSE请求,流式接收响应,并实时解析最终的数据。
        
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
                                # --- 改进点:检查 'choices' 是否存在且非空 ---
                                if isinstance(chunk_data, dict) and 'choices' in chunk_data and chunk_data['choices']:
                                    delta = chunk_data['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        full_content += content
                                        # 实时打印流式内容（可选)
                                        print(content, end='', flush=True) 
                            except json.JSONDecodeError:
                                # 忽略无法解析的行
                                print(f"警告:无法解析SSE数据行: {data_str}")
                                continue
                else:
                    print(f"请求失败,状态码: {response.status_code}")
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
    
    def extract_values_from_markdown(self, file_name: str, md_content: str, check_pro: list, fix_program: bool) -> list:
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
            {'检验项目': '黏度', '类型': '定量', '上限': '2.94', '下限': '2.46', '单位': 'mPa·S'}, 
            {'检验项目': '固含量', '类型': '定量', '上限': '14', '下限': '13.4', '单位': '%'}, 
            {'检验项目': '膜厚', '类型': '定量', '上限': '2.93', '下限': '2.85', '单位': '%'}, 
            {'检验项目': '线幅', '类型': '定量', '上限': '66.37', '下限': '62.37', '单位': 'um'}, 
            {'检验项目': '白点', '类型': '定量', '上限': '3', '下限': '0.0', '单位': '-'}, 
            {'检验项目': '对比', '类型': '定量', '上限': '∞', '下限': '6842.0', '单位': '-'}, 
            {'检验项目': '固含量批配差', '类型': '定量', '上限': '0.12', '下限': '0.0', '单位': '%'},
            {'检验项目': '色度x', '类型': '定量', '上限': '0.1425', '下限': '0.1395', '单位': '-'}, 
            {'检验项目': '色度y', '类型': '定量', '上限': '0.091', '下限': '0.087', '单位': '-'}, 
            {'检验项目': '色度Y', '类型': '定量', '上限': '10.85', '下限': '9.95', '单位': '-'}, 
            {'检验项目': 'Residual thickness Ratio', '类型': '定量', '上限': '85.6', '下限': '81.6', '单位': '%'}, 
            {'检验项目': '来料运输温度确认', '类型': '定性', '上限': '15', '下限': '0.0', '单位': '℃'}, 
            {'检验项目': '现象时间', '类型': '定量', '上限': '17', '下限': '9.0', '单位': 'sec'}, 
            {'检验项目': '外观标识确认', '类型': '定性', '上限': '0', '下限': '0.0', '单位': '-'}, 
            {'检验项目': '外观标签确认', '类型': '定性', '上限': '0', '下限': '0.0', '单位': '-'}, 
            {'检验项目': '外观确认', '类型': '定性', '上限': '0', '下限': '0.0', '单位': '-'}
            ]
            
            # 准备提示词
            prom = self._build_prompt(file_name, md_content, check_pro, check_pro_sample_fill,fix_program)
            
            # 调用OpenAI API
            # completion = self.client.chat.completions.create(
            #     model="deepseek-v3",
            #     extra_body={"enable_thinking": False},
            #     messages=[
            #         {'role': 'system', 'content': '你是一个专业的材料规格解析助手,请严格按照要求处理数据。'},
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
    
    def _build_prompt(self, file_name: str, md_content: str, check_pro: list, sample_data: list,fix_program: bool) -> str:
        """构建提示词"""
        if fix_program == True:
            languge_ = '''所有检验项目提取CF侧（上偏或者上POL）或者"雾度"有值的那一个型号'''
        else:
            languge_ = '''所有检验项目提取TFT侧（下偏或者下POL）或者"雾度"没有值的那一个型号'''
        return f'''
            #背景#
            -你是一个屏幕制造商的材料规格表维护助手,能从markdown文件中提取检验项目的值,对值进行简单计算替换到材料规格表的上下限中,
            从markdown中找到材料规格表中的检验项目的上下限值。

            下面为材料规格表：
            ======
            {check_pro}
            ======

            下面为材料规格书（markdown文件）文件内容:
            ======
            {md_content}
            ======

            #请严格按以下步骤顺序执行#
            1.先整体分析markdown中是否提到偏光片或者偏光板,若没提到则跳过第2步，若存在这两个字段，则从第2步开始执行,否则从第3步执行
            2.{languge_},并且遵守规则16下的7条规则
            3.从markdown中匹配字段,匹配时优先匹配与材料规格表中检验项目字段名称完全一致的字段,当未匹配到时,匹配名称不同但含义相同的字段,例如water,水,h2o都属于一个含义,例如particle count和颗粒是一个含义,例如固形分和固含量是一个含义，例如整体厚度和总厚度是一个含义，例如有效厚度和有效层是一个含义，例如RO和Δnd是一个含义。
            4.从markdown提取与字段匹配的值。
            5.依据符号计算该字段的上下限值,例如,当提取为1.17±0.03,计算1.17-0.03=1.14,1.17+0.03=1.20,因此上限为1.20,下限为1.14;当提取为890+2-4,表示上限为890+2=892,下限为890-4=886,因此上限为892,下限为886;在进行加减法计算时,请进行严格的加减法运算,得到的数值请严格按照得到的值进行输出。
            6.检查单位换算，当提取的单位和材料规格表中不一致时,上下限的值换算为和材料规格表中单位一致,例如:1000g换算为1kg,1000换算为1。
            7.检查每一检验项目的上下限值,是否遵守规则,特别是长宽,长一定比宽要长,提取后需要对比两个值大小,不符合需要两个交换。
            8.逐一检查响应的结果列表中是否存在相同的检验项目，若存在则保留一个即可，要注意检查重复项目时区分大小写，例如色度Y和色度y是不同的检验项目、Particle 0.5-1.0um和Particle≥1.0um也是不同检验项目
            9.检查结果中的检验项目数量与名称，要求与{check_pro}严格一致，项目定性类型的检验项目必须完整的出现在响应结果中，如有遗漏必须添加上

             #请严格按以下规则执行#
            --规则1：材料规格表中的检验项目即为需在Markdown中匹配的字段，必须严格按原名称进行一对一匹配，不得增加和减少和修改检验项目。，匹配时只匹配检验项目名称，不考虑项目代码。
            --规则2:使用新计算的上下限值替换材料规格表中原来的值,并且不能带有符号,不能确定上下限值时,填充原来的值。
            --规则3:当检验项目的类型为定性时,上下限值保持材料规格表中原来的值。
            --规则4:检验项目中既存在长又存在宽,需要智能识别长和宽,识别时需注意,长的上限大于或等于宽的上限,长的下限大于或等于宽的下限,长与宽的上下限需要结合尺寸精度,不能存在宽大于长的情况,重要。
            --规则5:球标和球标尺寸都是球标尺寸,可从初期全尺寸报告和检查报告范本和尺寸标表中找到,例如,尺寸表中#01代表球标1尺寸,#02代表球标2尺寸,#03代表球标3尺寸,注意区分球标的左右（LRUD）,例如#03R代表球标3右边尺寸，#03L代表球标3左边尺寸,#03U代表球标3上边的尺寸，#03D代表球标3下边尺寸。
            --规则6:<td><x</td>或者<td>&lt;x</td>代表<x,<td>≤x</td>或者<td>&le;x</td>或者<td>&lt;=x</td>代表≤x,<td>≥x</td>或者<td>&ge;x</td>或者<td>&gt;=x</td>代表≥x,<td>>x</td>或者<td>&gt;x</td>代表>x。
            --规则7:在材料规格表中的检验项目中:Tape良率,封装良率,F/T良率,外观良率,出货良率 在markdown中未找到完全相对应内容则按照上限：100，下限：0进行处理。
            --规则8:当检验项目为<保护膜表面阻抗>时在markdown中没有保护膜表面阻抗且存在表面电阻值那么表面电阻值就指的是保护膜表面阻抗。
            --规则9:检查项目为R0时,也有另外一种名字为Δnd。
            --规则10:
                (1)**表面静电阻抗在规则书中找到具体的值按照实际值处理,没有找到对应值则通常按照表面静电阻抗的下限为10的6次方数量级,上限为10的9次方数量级。如果能识别到对应内容 原始的markdown内容可能没有识别到次方,对应的值一定是10的多少次方,需要你帮我修正数据，
                    示例: 保护膜表面阻抗 1.0X106~1X109 → 上限1000000000，下限1000000，
                    示例：保护膜表面阻抗 1.0X10^6~9.9X10^10 → 上限99000000000，下限1000000。
                    示例：阻抗 1012代表10的12次方
                    示例：阻抗 10X10^n代表1.0X10^n+1
                (2)**表面静电阻抗后面有数字且在markdown中没有具体对应的值那它所对应的值需先看是否存在不带数字的检验项目是否存在值，如果存在则上限与下限就取对应的值，如果不存在就按规则10的(1)逻辑取值，
                    示例：保护膜表面阻抗2在markdown中没有对应内容，上限与下限就取保护膜表面阻抗的上限与下限。
            --规则11:在材料规格表的检验项目中，
                (1)检验项目的单位为 % 时：
                    若markdown中没有具体的上限值,则上限最大为：100。
                    若markdown中的上限值为无穷大符号(∞),则上限最大为：100,很重要！。
                        示例: 平行透过率 ≥ 34 则上限100而非∞
                (2)检验项目的单位不为 % 时：
                    若条件为 ≤ X，则上限为X，下限为0。
                        示例：厚度 ≤ 0.5 mm → 上限0.5，下限0。
                    若条件为 ≥ X 或 > X，则下限为X，上限为∞。
                        示例：拉伸强度 ≥ 50 MPa → 下限50，上限∞。
            --规则12:部分特殊处理:
                (1):材料规格表的检验项目中Total pitch确认 在markdown中的同义词为OL total pitch/output side
                (2):正负翘为一个检验项目，负翘的值一般为负值，示例：正翘H≤15mm，负翘H≤5mm，则对应上限为：上限：15，下限：-5
            --规则13:markdown内容中的数据可能为表格数据,需要根据数据规律特征判断,其中需要特别注意的是如果是表格数据那表格中的指标内容可能带有单位
                示例: 氟离子(F) <=50ppm  颗粒(≥0.5μm)  <=50个/ML 这种情况下 氟离子(F) <=50ppm 是一组数据,颗粒(≥0.5μm)  <=50个/ML 是一组数据,其中 颗粒(≥0.5μm) 是项目名称不要把(≥0.5μm)识别成立名称对应的值 
            --规则14：注意负数计算，如：-5+0.1为-4.9，-3-0.4为-3.4
            --规则15：当markdown中材料有多个型号不知道选取哪个型号的上下限值时，依据markdown文件名来选择型号：markdown文件名:{file_name}
            --规则16: 当markdown内容中含有“偏光板”或者“偏光片”时，表明该材料为偏光材料：需要严格按下面7条规则处理：
                (1):总厚度和有效厚度如果在markdown中有匹配的关键字段，则直接提取上下限值，
                (2):上偏（CF侧）有效厚度计算公式为：有效厚度为PMMA层+PVA层+补偿膜层+PSA层的和（或者 AG film(ASG7)层+ Polarizer层+PK3 film补偿膜层+胶层的和）,公差为4层公差的和，并非总厚度的公差25
                (3):下偏（TFT侧）有效厚度计算公式为：有效厚度为PMMA层+PVA层+补偿膜层+PSA层的和（或者  PET film层+ Polarizer层+PK3 film补偿膜层+胶层的和），公差为4层公差的和，并非总厚度的公差25
                (4):直角度在一般为90±n,在90度左右
                (5):Lx代表长，Ly代表宽，当从markdown中找不到长和宽的公差时，长和宽的公差默认为±0.2
                (6)偏光片或者偏光板中保护膜表面阻抗：1*10^6~1*10^9.9可能对应材料规格表里面的多个保护膜表面阻抗，需要转化为上限7943282347，下限1000000。
                (7)偏光片或者偏光板中"Adhesive"的另一种名称为"对基板剥离力","protective flim"也称为“保护膜剥离力”,"Release flime"也称为"离型膜剥离力"
            
            #在处理时请把以上所有内容考虑完整#       
            #响应为列表格式#
            严格响应为如下格式,返回只包含检验代码,检验项目,类型,上限,下限,单位列名,不要返回任何其他内容
            参考如下:
            {sample_data}
            '''
    org = """
            #按以下步骤执行#
            1.理解材料规格表中的检验项目就是要去markdown中匹配的字段,不能多也不能少,检验项目的名称不能改变,其中检验项目中有雾度时,在markdown需严格提取上偏(CF)这个字段下的内容作为输出,同时其他字段也按照上偏规格提取,否则提取下偏(TFT)的字段作为输出。
            2.从markdown中匹配字段,匹配时优先匹配与检验项目字段名称完全一致的字段,当未匹配到时,匹配名称不同但含义相同的字段,例如water,水,h2o都属于一个含义,例如particle count和颗粒是一个含义,例如固形分和固含量是一个含义，例如整体厚度和总厚度是一个含义，例如有效厚度和有效层是一个含义，例如RO和Δnd是一个含义
            3.从markdown提取与字段匹配的值
            4.依据符号计算该字段的上下限值,例如,当提取为1.17±0.03,计算1.17-0.03=1.14,1.17+0.03=1.20,因此上限为1.20,下限为1.14;当提取为890+2-4,表示上限为890+2=892,下限为890-4=886,因此上限为892,下限为886;在进行加减法计算时,请进行严格的加减法运算,得到的数值请严格按照得到的值进行输出
            5.单位换算:1.当提取的单位和材料规格表中不一致时,上下限的值换算为和材料规格表中单位一致,例如:1000g换算为1kg,1000换算为1; 2.当材料规格表中没有单位,请整体检索规格书中出现的测量单位,进行语义匹配,然后进行对应的单位换算
            6.检查每一检验项目的上下限值,是否遵守规则,特别是长宽,长一定比宽要长,提取后需要对比两个值大小,不符合需要两个交换
            7.检查检验项目是否完整,保证和材料规格表上的检验项目数量一致
            

            #遵守下面规则#
            --规则1:使用新计算的上下限值替换材料规格表中原来的值,并且不能带有符号,不能确定上下限值时,填充原来的值；
            --规则2:当检验项目的类型为定性时,上下限值保持材料规格表中原来的值
            --规则3:检验项目中,长的上下限值大于宽的上下限制值,不能填反
            --规则4:球标和球标尺寸都是球标尺寸,可从初期全尺寸报告和检查报告范本和尺寸标表中找到,例如,尺寸表中#01代表球标1尺寸,#02代表球标2尺寸,#03代表球标3尺寸
            --规则5:<td><x</td>或者<td>&lt;x</td>代表<x,<td>≤x</td>或者<td>&le;x</td>或者<td>&lt;=x</td>代表≤x,<td>≥x</td>或者<td>&ge;x</td>或者<td>&gt;=x</td>代表≥x,<td>>x</td>或者<td>&gt;x</td>代表>x
            --规则6:(1)表面静电阻抗在规则书中找到具体的值按照实际值处理,没有找到对应值则通常按照表面静电阻抗的下限为10的6次方数量级,上限为10的9次方数量级
                    (2)在检验项目中保护膜表面阻抗通常为下限：10的6次方数量级，上限为10的10次方数量级，若在检验项目中有，在规格书中为找到，按照这个规则填写
            
            --规格7:在材料规格表的检验项目中，
                    （1）当单位为 % 时：
                        若markdown中没有具体的上限值，则上限最大为：100
                    （2）当单位不为 % 时：
                        若条件为 ≤ X，则上限为X，下限为0。
                            示例：厚度 ≤ 0.5 mm → 上限0.5，下限0。
                        若条件为 ≥ X 或 > X，则下限为X，上限为∞。
                            示例：拉伸强度 ≥ 50 MPa → 下限50，上限∞。
            --规则8:部分特殊处理:
                (1):材料规格表的检验项目中Total pitch确认 在markdown中的同义词为OL total pitch/output side
                (2):正负翘为一个检验项目，负翘的值一般为负值，示例：正翘H≤15mm，负翘H≤5mm，则对应上限为：上限：15，下限：-5
            --规则9:在材料规格表的检验项目中:Tape良率,封装良率,F/T良率,外观良率,出货良率 在规格书中未找到则按照上限：100，下限：0进行处理
"""
    def _parse_response(self, response_content: str) -> list:
        """解析API响应"""
        try:
            # 尝试直接解析JSON
            return json.loads(response_content)
        except json.JSONDecodeError:
            try:
                # 如果不是标准JSON,尝试使用ast.literal_eval
                return ast.literal_eval(response_content)
            except:
                # 如果还是无法解析,尝试提取列表部分
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
            data_list: 包含字典的列表,字典中包含中文键名
            
        Returns:
            list: 包含字典的列表,字典中的键名已替换为英文
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
                # 如果键名在映射中,使用英文键名,否则保留原键名
                english_key = key_mapping.get(chinese_key, chinese_key)
                new_item[english_key] = value
            translated_data.append(new_item)
        
        return translated_data
