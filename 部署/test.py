import requests
import json
from pdb import set_trace

def process_specification(pdf_file_path, spec_data):
    """
    调用处理规格表的API
    
    Args:
        pdf_file_path: PDF文件路径
        spec_data: 规格表数据列表
    
    Returns:
        dict: API响应结果
    """
    # API端点
    url = "http://localhost:7861/api/file/extract-fields"
    
    # 准备请求数据
    files = {
        'file': open(pdf_file_path, 'rb')
    }
    
    data = {
        'dataList': json.dumps(spec_data, ensure_ascii=False)
    }
    
    try:
        # 发送POST请求
        response = requests.post(url, files=files, data=data)
        
        # 检查响应状态
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("处理成功！")
                return result
            else:
                print(f"处理失败: {result.get('message')}")
                return result
        else:
            print(f"请求失败，状态码: {response.status_code}")
            print(f"错误信息: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return None
    except Exception as e:
        print(f"其他错误: {e}")
        return None
    finally:
        # 确保文件被关闭
        if 'file' in files:
            files['file'].close()

# 示例用法
if __name__ == "__main__":
    # 示例规格表数据
    spec_data = [
    {'项目代码': 'A01', '检验项目': '粘度25°C', '类型': '定量', '上限': '', '下限': '', '单位': 'cSt'},
    {'项目代码': 'A02', '检验项目': '涂膜硬度', '类型': '定量', '上限': '', '下限': '', '单位': 'Shore A'},
    {'项目代码': 'A04', '检验项目': '剪切强度', '类型': '定量', '上限': '', '下限': '', '单位': 'MPa'},
    {'项目代码': 'A05', '检验项目': '体积电阻率', '类型': '定量', '上限': '', '下限': '', '单位': 'Ω.cm'},
    {'项目代码': 'A06', '检验项目': '包装外观', '类型': '定性', '上限': '0', '下限': '0', '单位': '-'},
    {'项目代码': 'A07', '检验项目': '标签、标识', '类型': '定性', '上限': '0', '下限': '0', '单位': '-'},
    {'项目代码': 'A08', '检验项目': '材料有效期确认', '类型': '定性', '上限': '0', '下限': '0', '单位': '-'}
]
    
    # PDF文件路径
    pdf_file_path = r"test_pdf/test_data/材料规格承认书-透明UV防湿绝缘胶_3329-2.pdf"  # 替换为实际的PDF文件路径
    
    # 调用API
    result = process_specification(pdf_file_path, spec_data)
    
    if result and result.get('success'):
        # 打印处理结果
        print("\n处理结果:")
        print(json.dumps(result['dataList'], ensure_ascii=False, indent=2))
        
        # 可选：保存结果到文件
        with open('processed_result.json', 'w', encoding='utf-8') as f:
            json.dump(result['dataList'], f, ensure_ascii=False, indent=2)
        print("结果已保存到 processed_result.json")
