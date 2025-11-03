import requests
import json
import pandas as pd
import os

def process_specification(pdf_file_path):
    """
    调用处理规格表的API
    
    Args:
        pdf_file_path: PDF文件路径
        spec_data: 规格表数据列表
    
    Returns:
        dict: API响应结果
    """
    # API端点
    url = "http://10.5.100.165:7861/api/file/extract-fields1"
    
    # 准备请求数据
    # 确保文件在请求过程中保持打开状态
    with open(pdf_file_path, 'rb') as pdf_file:
        files = {
            'file': pdf_file
        }
        
        
        try:
            # 发送POST请求
            response = requests.post(url, files=files)
            print(response.content)
            # 定义要保存的字符串

            # 打开文件（若不存在则创建），写入内容
            # 参数说明：
            # - 'w' 表示以「写入模式」打开（若文件已存在，会覆盖原有内容）
            # - encoding='utf-8' 确保中文等特殊字符正常保存
            file = open("output.txt", "w", encoding="utf-8")
            file.write(response.content.decode("utf-8"))  # 写入字符串
            file.close()  # 必须关闭文件，否则内容可能未真正写入
                
        except requests.exceptions.RequestException as e:
            print(f"网络请求错误: {e}")
            return None
        except Exception as e:
            print(f"其他错误: {e}")
            return None
    # 文件会在 'with' 语句结束后自动关闭


# 示例用法
if __name__ == "__main__":
        
    # PDF文件路径
    pdf_file_path = r"4.0\pdf\偏光片 23.8 CT03-3 5115-08-AV2 TFT.pdf"  # 替换为实际的PDF文件路径
    # # 调用API
    result = process_specification(pdf_file_path)




