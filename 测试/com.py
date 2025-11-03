import pandas as pd
import numpy as np
from pathlib import Path

def values_equal(val1, val2):
    """
    自定义函数，用于判断两个值是否相等，包括数值类型的不同但值相同的情况。
    例如：1 和 1.0, '1.0' 和 1.0, 'abc' 和 'abc'。
    对于数字，会尝试转换后比较。
    对于非数字，直接比较字符串。
    """

    if val1=='无穷大':
        val1 = '∞'
    if val2=='无穷大':
        val2 = '∞'

    # 处理 NaN 情况：pandas 中 NaN != NaN，但我们认为两个 NaN 是相同的。
    if pd.isna(val1) and pd.isna(val2):
        return True
    if pd.isna(val1) or pd.isna(val2):
        return False

    # 尝试将两个值都转换为浮点数进行比较
    try:
        # 使用 numpy 的 isclose 来处理浮点数精度问题
        # rtol=1e-05, atol=1e-08 是 isclose 的默认值，对于大多数情况足够
        # equal_nan=True 使得两个 NaN 被认为是相等的（虽然上面已经处理了）
        return np.isclose(float(val1), float(val2), equal_nan=True)
    except (ValueError, TypeError):
        # 如果转换失败（例如，包含非数字字符），则比较字符串形式
        return str(val1) == str(val2)

def calculate_consistency_for_sheet(df):
    """
    计算单个DataFrame（代表一个sheet）的一致性。
    使用自定义的 values_equal 函数来判断相等。

    假设DataFrame包含列: '检验项目', '上限', '下限', '上限(ai)', '下限(ai)'
    比较 '上限' 与 '上限(ai)' 以及 '下限' 与 '下限(ai)'。

    Args:
        df (pd.DataFrame): 包含所需列的DataFrame。

    Returns:
        dict: 包含该sheet一致性结果的字典。
    """
    # required_columns = ['检验项目', '上限真实值(PDF)','下限真实值(PDF)', '上限新', '下限新']
    required_columns = ['检验项目', '上限新','下限新', '上限', '下限']

    if not all(col in df.columns for col in required_columns):
        missing_cols = set(required_columns) - set(df.columns)
        print(f"  警告: 缺少必要列 {missing_cols}，无法计算一致性。")
        return {
            "总单元格数": 0,
            "相同数": 0,
            "不同数": 0,
            "一致率 (%)": 0.0
        }
    
    # 只取定量的数据
    df = df[df['类型'] == '定量']
    

    # 计算行数（检验项目数）
    num_items = len(df)
    
    # 总单元格数：每个检验项目有上限和下限两个值需要比较
    total_cells = num_items * 2
    
    if total_cells == 0:
        print("  警告: 该sheet没有数据行。")
        return {
            "总单元格数": 0,
            "相同数": 0,
            "不同数": 0,
            "一致率 (%)": 0.0
        }

    # 使用 apply 和自定义函数进行比较
    # 比较 '上限' 与 '上限(ai)'
    # axis=1 表示按行应用函数


    upper_comparison_series = df.apply(lambda row: values_equal(row['上限新'], row['上限']), axis=1)
    same_upper = upper_comparison_series.sum()

    # 比较 '下限' 与 '下限(ai)'
    lower_comparison_series = df.apply(lambda row: values_equal(row['下限新'], row['下限']), axis=1)
    same_lower = lower_comparison_series.sum()
    
    # 相同的单元格总数
    same_count = same_upper + same_lower
    
    # 不同的单元格总数
    no_same_count = total_cells - same_count
    
    # 计算一致率
    consistency_rate = (same_count / total_cells) * 100 if total_cells > 0 else 0.0

    return {
        "总单元格数": total_cells,
        "相同数": same_count,
        "不同数": no_same_count,
        "一致率 (%)": consistency_rate
    }

def process_excel_file(file_path):
    """
    处理整个Excel文件，计算每个sheet的一致性。

    Args:
        file_path (str): Excel文件的路径。
    """
    file_path = Path(file_path)

    # 检查文件是否存在
    if not file_path.exists():
        print(f"错误: 文件 '{file_path}' 不存在。")
        return

    try:
        # # 判断文件类型，自动选择 engine
        # if file_path.suffix.lower() == '.xls':
        #     engine = 'xlrd'
        # elif file_path.suffix.lower() in ['.xlsx', '.xlsm']:
        #     engine = 'openpyxl'
        # else:
        #     raise ValueError(f"不支持的文件格式: {file_path.suffix}")
        # 使用ExcelFile对象来获取所有sheet名称
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names

        if not sheet_names:
            print(f"警告: 文件 '{file_path}' 中没有找到任何sheet。")
            return

        print(f"正在处理文件: {file_path.name}")
        print("-" * 50)

        overall_total_cells = 0
        overall_same_count = 0
        overall_no_same_count = 0

        # 遍历每个sheet
        for sheet_name in sheet_names:
            print(f"正在处理 sheet: '{sheet_name}'")
            # if(sheet_name != '滁州HKC_43LG_PET_91.NR432.59Y_91'):
            #     continue
            try:
                # 读取当前sheet的数据
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                
                # 计算当前sheet的一致性
                results = calculate_consistency_for_sheet(df)
                
                # 打印当前sheet的结果
                print(f"  总单元格数: {results['总单元格数']}")
                print(f"  相同数: {results['相同数']}")
                print(f"  不同数: {results['不同数']}")
                print(f"  一致率: {results['一致率 (%)']:.2f}%")
                print("-" * 30)
                
                # 累计总体结果
                overall_total_cells += results['总单元格数']
                overall_same_count += results['相同数']
                overall_no_same_count += results['不同数']

            except Exception as e:
                print(f"  处理 sheet '{sheet_name}' 时发生错误: {e}")
                print("-" * 30)

        # 计算并打印总体结果
        if overall_total_cells > 0:
            overall_consistency_rate = (overall_same_count / overall_total_cells) * 100
            print("\n=== 所有Sheet总体统计 ===")
            print(f"总单元格数: {overall_total_cells}")
            print(f"总相同数: {overall_same_count}")
            print(f"总不同数: {overall_no_same_count}")
            print(f"总体一致率: {overall_consistency_rate:.2f}%")
        else:
            print("\n=== 所有Sheet总体统计 ===")
            print("没有有效的数据用于计算总体一致率。")

    except Exception as e:
        print(f"读取或处理文件 '{file_path}' 时发生错误: {e}")

if __name__ == "__main__":
    # --- 配置区域 ---
    # 请确保此文件与脚本在同一目录下，或者提供完整路径
    excel_file_to_process = r"D:\HKC\4.0\20251030.xlsx"
    # --- 配置区域结束 ---

    # 执行处理
    process_excel_file(excel_file_to_process)




