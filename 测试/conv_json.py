import os
import json
import pandas as pd
from pathlib import Path

def excel_to_json(input_folder, output_folder):
    """
    将文件夹中的所有Excel文件转换为JSON格式
    """
    # 创建输出文件夹
    os.makedirs(output_folder, exist_ok=True)
    
    # 获取所有Excel文件
    excel_files = [f for f in Path(input_folder).glob('*') if f.suffix.lower() in ['.xlsx', '.xls']]
    
    for excel_file in excel_files:
        try:
            # 读取Excel文件
            df = pd.read_excel(excel_file)
            
            # 清理数据
            df = df.dropna(how='all')
            
            json_data = []
            for _, row in df.iterrows():
                # 检查必要数据是否存在
                if pd.isna(row.get('项目代码')) or pd.isna(row.get('检验项目')):
                    continue
                
                # 获取数据
                project_code = str(row['项目代码']).strip()
                inspection_item = str(row['检验项目']).strip()
                data_type = str(row['类型']).strip() if not pd.isna(row.get('类型')) else "定量"
                unit = str(row['单位']).strip() if not pd.isna(row.get('单位')) else ""
                
                # 根据类型设置上下限
                upper_limit = "0" if data_type == "定性" else ""
                lower_limit = "0" if data_type == "定性" else ""
                
                # 构建JSON对象
                item = {
                    "项目代码": project_code,
                    "检验项目": inspection_item,
                    "类型": data_type,
                    "单位": unit,
                    "上限": upper_limit,
                    "下限": lower_limit
                }
                json_data.append(item)
            
            # 保存JSON文件
            output_path = Path(output_folder) / f"{excel_file.stem}.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=4)
            
            print(f"成功转换: {excel_file.name} -> {output_path.name}")
            
        except Exception as e:
            print(f"处理文件 {excel_file.name} 时出错: {e}")

# 使用示例
if __name__ == "__main__":
    input_folder = r"D:\HKC\4.0\POL测试\excel"    # Excel文件所在文件夹
    output_folder = r"D:\HKC\4.0\POL测试\json"    # JSON文件输出文件夹
    
    excel_to_json(input_folder, output_folder)