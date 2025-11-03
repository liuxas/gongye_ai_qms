import requests
import json
import pandas as pd
import os

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
    url = "http://10.5.100.165:7861/api/file/extract-fields"
    
    # 准备请求数据
    # 确保文件在请求过程中保持打开状态
    with open(pdf_file_path, 'rb') as pdf_file:
        files = {
            'file': pdf_file
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
    # 文件会在 'with' 语句结束后自动关闭

def save_result_to_excel(result_data_list, pdf_file_path, output_excel_path):
    """
    将处理结果保存到Excel文件的一个新sheet中，sheet名与PDF文件名一致。

    Args:
        result_data_list (list): API返回的 dataList。
        pdf_file_path (str): 原始PDF文件的路径。
        output_excel_path (str): 输出Excel文件的路径。
    """
    if not result_data_list:
        print("没有数据可保存到Excel。")
        return

    # 1. 将数据列表转换为 Pandas DataFrame
    df = pd.DataFrame(result_data_list)

    # 2. 获取PDF文件名（不含扩展名）作为sheet名称
    pdf_filename_without_ext = os.path.splitext(os.path.basename(pdf_file_path))[0]
    sheet_name = pdf_filename_without_ext

    # 3. 使用 Pandas 将 DataFrame 保存到 Excel
    try:
        # 如果Excel文件已存在，需要以追加模式打开
        if os.path.exists(output_excel_path):
             # 读取现有Excel文件
            with pd.ExcelWriter(output_excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        else:
            # 如果文件不存在，则创建新文件
            with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"结果已成功保存到 Excel 文件 '{output_excel_path}' 的 '{sheet_name}' 表中。")

    except Exception as e:
        print(f"保存Excel文件时出错: {e}")


# 示例用法
if __name__ == "__main__":
    # 示例规格表数据
#     spec_data = [
#     {"项目代码": "POL004", "检验项目": "整体厚度", "类型": "定量", "上限": "", "下限": "", "单位": "um"},
#     {"项目代码": "POL005", "检验项目": "有效厚度", "类型": "定量", "上限": "", "下限": "", "单位": "um"},
#     {"项目代码": "POL006", "检验项目": "PSA厚度", "类型": "定量", "上限": "", "下限": "", "单位": "um"},
#     {"项目代码": "POL007", "检验项目": "正负翘", "类型": "定量", "上限": "", "下限": "", "单位": "MM"},
#     {"项目代码": "POL044", "检验项目": "宽幅", "类型": "定量", "上限": "", "下限": "", "单位": "MM"},
#     {"项目代码": "POL045", "检验项目": "波浪褶波高", "类型": "定量", "上限": "", "下限": "", "单位": "MM"},
#     {"项目代码": "POL051", "检验项目": "接头数", "类型": "定性", "上限": "3", "下限": "0", "单位": "-"},
#     {"项目代码": "POL009", "检验项目": "单体透过率", "类型": "定量", "上限": "", "下限": "", "单位": "%"},
#     {"项目代码": "POL010", "检验项目": "平行透过率", "类型": "定量", "上限": "", "下限": "", "单位": "%"},
#     {"项目代码": "POL011", "检验项目": "交叉透过率", "类型": "定量", "上限": "", "下限": "", "单位": "%"},
#     {"项目代码": "POL012", "检验项目": "380nm透过率", "类型": "定量", "上限": "", "下限": "", "单位": "%"},
#     {"项目代码": "POL013", "检验项目": "R0", "类型": "定量", "上限": "", "下限": "", "单位": "nm"},
#     {"项目代码": "POL014", "检验项目": "Rth", "类型": "定量", "上限": "", "下限": "", "单位": "nm"},
#     {"项目代码": "POL015", "检验项目": "偏振度", "类型": "定量", "上限": "", "下限": "", "单位": "%"},
#     {"项目代码": "POL017", "检验项目": "色调a值", "类型": "定量", "上限": "", "下限": "", "单位": "NBS"},
#     {"项目代码": "POL018", "检验项目": "色调b值", "类型": "定量", "上限": "", "下限": "", "单位": "NBS"},
#     {"项目代码": "POL019", "检验项目": "吸收轴角度", "类型": "定量", "上限": "", "下限": "", "单位": "°"},
#     {"项目代码": "POL020", "检验项目": "雾度(上偏)", "类型": "定量", "上限": "", "下限": "", "单位": "%"},
#     {"项目代码": "POL026", "检验项目": "混料", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL027", "检验项目": "片反", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL028", "检验项目": "粘片", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL029", "检验项目": "断面", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL030", "检验项目": "压点", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL031", "检验项目": "折伤", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL032", "检验项目": "Mura", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL033", "检验项目": "缺/残胶", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL034", "检验项目": "保/离膜脏污", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL035", "检验项目": "保/离膜气泡", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL036", "检验项目": "保/离膜异物", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL037", "检验项目": "本体气泡", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL038", "检验项目": "本体异物", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL039", "检验项目": "本体划伤", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL043", "检验项目": "其他外观不良", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL016", "检验项目": "3H硬度(上偏)", "类型": "定性", "上限": "0", "下限": "0", "单位": "-"},
#     {"项目代码": "POL021", "检验项目": "保护膜剥离力", "类型": "定量", "上限": "", "下限": "", "单位": "N/25mm"},
#     {"项目代码": "POL022", "检验项目": "离型纸剥离力", "类型": "定量", "上限": "", "下限": "", "单位": "N/25mm"},
#     {"项目代码": "POL023", "检验项目": "对基板剥离力", "类型": "定量", "上限": "", "下限": "", "单位": "N/25mm"},
#     {"项目代码": "POL024", "检验项目": "保护膜表面阻抗", "类型": "定量", "上限": "", "下限": "", "单位": "Ω.cm"},
#     {"项目代码": "POL025", "检验项目": "PSA表面阻抗", "类型": "定量", "上限": "", "下限": "", "单位": "Ω.cm"},
#     {"项目代码": "POL046", "检验项目": "保护膜表面阻抗2", "类型": "定量", "上限": "", "下限": "", "单位": "Ω.cm"},
#     {"项目代码": "POL047", "检验项目": "保护膜表面阻抗3", "类型": "定量", "上限": "", "下限": "", "单位": "Ω.cm"},
#     {"项目代码": "POL048", "检验项目": "保护膜表面阻抗4", "类型": "定量", "上限": "", "下限": "", "单位": "Ω.cm"},
#     {"项目代码": "POL049", "检验项目": "保护膜表面阻抗5", "类型": "定量", "上限": "", "下限": "", "单位": "Ω.cm"},
#     {"项目代码": "POL050", "检验项目": "卷装良率", "类型": "定量", "上限": "", "下限": "", "单位": "%"}
# ]
    

        
    # PDF文件路径
    pdf_file_path = r"4.0\pdf\偏光片 23.8 CT03-3 5115-08-AV2 TFT.pdf"  # 替换为实际的PDF文件路径
    json_path = r"4.0\json\偏光片 23.8 CT03-3 5115-08-AV2 TFT.json"
    with open(json_path, 'r', encoding='utf-8') as file:
        spec_data = json.load(file)    
    # 输出Excel文件路径
    output_excel_path = "4.0/processed_results_new.xlsx" # 您可以指定任何您想要的Excel文件名

    # # 调用API
    result = process_specification(pdf_file_path, spec_data)
    
    if result and result.get('success'):
        # 打印处理结果
        print("\n处理结果:")
        print(json.dumps(result['dataList'], ensure_ascii=False, indent=2))
        
        # 保存结果到Excel
        save_result_to_excel(result['dataList'], pdf_file_path, output_excel_path)




