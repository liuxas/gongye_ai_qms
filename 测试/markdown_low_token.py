import tiktoken
from bs4 import BeautifulSoup
import re

# =================== Token 计算函数 ===================
def count_tokens(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    """计算文本的 token 数量"""
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        print(f"未知模型 {model_name}，使用默认编码器 cl100k_base")
        encoding = tiktoken.get_encoding("cl100k_base")
    
    tokens = encoding.encode(text)
    return len(tokens)

# =================== 章节分析函数 ===================
def analyze_sections_token_usage(md_content: str, model_name: str = "gpt-3.5-turbo") -> list:
    """
    分析Markdown文档中每个章节的token使用情况
    返回包含章节信息的列表
    """
    lines = md_content.split('\n')
    sections = []
    current_section = []
    current_title = ""
    current_level = 0
    
    for line in lines:
        # 检测标题行 (# ## ### 等)
        heading_match = re.match(r'^(#+)\s+(.+)$', line.strip())
        
        if heading_match:
            # 保存前一个章节
            if current_section and current_title:
                section_content = '\n'.join(current_section)
                token_count = count_tokens(section_content, model_name)
                sections.append({
                    'title': current_title,
                    'level': current_level,
                    'token_count': token_count,
                    'content_preview': section_content[:100] + '...' if len(section_content) > 100 else section_content
                })
            
            # 开始新章节
            current_title = heading_match.group(2).strip()
            current_level = len(heading_match.group(1))
            current_section = [line]
        elif line.strip() or current_section:
            # 添加到当前章节
            current_section.append(line)
    
    # 处理最后一个章节
    if current_section and current_title:
        section_content = '\n'.join(current_section)
        token_count = count_tokens(section_content, model_name)
        sections.append({
            'title': current_title,
            'level': current_level,
            'token_count': token_count,
            'content_preview': section_content[:100] + '...' if len(section_content) > 100 else section_content
        })
    
    return sections

# =================== 优化函数：移除图片 + 转换表格 + 压缩空行 ===================
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

def write_optimized_markdown(optimized_content: str, filename: str = "optimized_document.md"):
    """
    将优化后的内容写入Markdown文件
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(optimized_content)
    print(f"✅ 优化后的内容已保存到: {filename}")


# =================== 主函数 ===================
def optimize_and_compare(md_content: str, model_name: str = "gpt-3.5-turbo") -> dict:
    """综合优化并对比 token"""
    print("=== Markdown 优化与 Token 对比 ===\n")

    # 分析原始内容的章节token分布
    print("📊 原始内容章节Token分析:")
    original_sections = analyze_sections_token_usage(md_content, model_name)
    
    total_original_tokens = 0
    for i, section in enumerate(original_sections, 1):
        indent = "  " * (section['level'] - 1)
        print(f"  {i:2d}. {indent}{section['title']}")
        print(f"      Token数量: {section['token_count']}")
        total_original_tokens += section['token_count']
    
    print(f"\n📝 原始内容总Token数量: {total_original_tokens}")

    # 优化内容
    optimized_content = optimize_markdown_content(md_content)
    
    # 分析优化后内容的章节token分布
    print("\n📊 优化后内容章节Token分析:")
    optimized_sections = analyze_sections_token_usage(optimized_content, model_name)
    
    total_optimized_tokens = 0
    for i, section in enumerate(optimized_sections, 1):
        indent = "  " * (section['level'] - 1)
        print(f"  {i:2d}. {indent}{section['title']}")
        print(f"      Token数量: {section['token_count']}")
        total_optimized_tokens += section['token_count']
    
    print(f"\n✅ 优化后内容总Token数量: {total_optimized_tokens}")

    # 计算节省情况
    saved = total_original_tokens - total_optimized_tokens
    saving_rate = (saved / total_original_tokens * 100) if total_original_tokens > 0 else 0
    
    print(f"\n📈 优化效果:")
    print(f"   节省 Token: {saved}")
    print(f"   节省比例: {saving_rate:.1f}%")

    # 找出token消耗最大的章节
    if original_sections:
        max_section = max(original_sections, key=lambda x: x['token_count'])
        print(f"\n🔥 Token消耗最大的章节:")
        print(f"   章节: {max_section['title']}")
        print(f"   Token数量: {max_section['token_count']}")
        print(f"   占总Token比例: {max_section['token_count']/total_original_tokens*100:.1f}%")
    write_optimized_markdown(optimized_content)
    return {
        "optimized_content": optimized_content,
        "original_tokens": total_original_tokens,
        "optimized_tokens": total_optimized_tokens,
        "saving_rate": saving_rate,
        "original_sections": original_sections,
        "optimized_sections": optimized_sections
    }

# =================== 使用示例 ===================
if __name__ == "__main__":
    markdown_text = '''
# Model Name：

32寸 PMMA/COP Model PT320AT02-5机种 Issue Date: 2024/7/2

Version:1.1

<table><tr><td>Buyer Affirmance</td></tr><tr><td>滁州惠科光电科技有限公司</td></tr><tr><td>sign</td></tr></table>

<table><tr><td>Supplier Affirmance</td></tr><tr><td>恒美光电</td></tr><tr><td></td></tr></table>

# 內 容

(Contents)

1. 适用范围(Scope of Application)

2. 构造(Structure)

3. 产品规格&检验方法(Appearance & Methodology)

4. 包装规格(Packing)

5. 仕样书有效性(Guarantee term)

6. 保存条件（Storage condition）

7. 其它（other）

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

<table><tr><td rowspan=1 colspan=5>型号清单</td></tr><tr><td rowspan=2 colspan=1>序号</td><td rowspan=1 colspan=2>型号名称</td><td rowspan=2 colspan=1>偏光片类型</td><td rowspan=2 colspan=1>尺寸</td></tr><tr><td rowspan=1 colspan=1>恒美光电</td><td rowspan=1 colspan=1>滁州惠科</td></tr><tr><td rowspan=2 colspan=1>1</td><td rowspan=1 colspan=1>VW2-AGA-Z0003</td><td rowspan=1 colspan=1>220025023260</td><td rowspan=1 colspan=1>VA AG</td><td rowspan=1 colspan=1>710.835*406.085</td></tr><tr><td rowspan=1 colspan=1>VW2-Z0003</td><td rowspan=1 colspan=1>220025023290</td><td rowspan=1 colspan=1>VA Clear</td><td rowspan=1 colspan=1>703.685*402.57</td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr></table>

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

文件修改履历表  

<table><tr><td rowspan=1 colspan=1>修订日期</td><td rowspan=1 colspan=1>版本</td><td rowspan=1 colspan=1>页次</td><td rowspan=1 colspan=1>改定内容</td></tr><tr><td rowspan=1 colspan=1>2024.6.7</td><td rowspan=1 colspan=1>1.0</td><td rowspan=1 colspan=1>ALL</td><td rowspan=1 colspan=1>新制定</td></tr><tr><td rowspan=1 colspan=1>2024.7.2</td><td rowspan=1 colspan=1>1.1</td><td rowspan=1 colspan=1>P18</td><td rowspan=1 colspan=1>更新客户图面</td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr></table>

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

# 恒美光电 Hengmei Optoelectronic

# 1.适用范围(Scope of Application)

本规格书适用于恒美光电出货至滁州惠科光电科技有限公司之32寸光学补偿用偏光板的规格适用，其它制品规格详细记载于个别规格书，规格书与个别规格书内容相矛盾时以个别规格书优先。

# 2.构造(Structure)

2.1 VW2-AGA-Z0003保护膜 厚度约 $5 3 { \pm } 6 { \mathsf { u m } }$ 表面处理PMMA 厚度约 $4 5 { \pm } 7 { \mathsf { u m } }$ PVA 厚度约 $1 8 \pm 6 \mathsf { u m }$ 补偿膜 厚度约 $5 2 { \pm } 7 { \mathsf { u m } }$ PSA 厚度约 $2 0 { \pm } 5 { \mathsf { u m } }$ 离型膜 厚度约 $3 8 { \pm } 5 { \mathsf { u m } }$

![](/3a64e643247071a600cdb5ee43103af86d7abd2c98872fc226a55095d0525748.jpg)

2.2 VW2-Z0003保护膜 厚度约 $5 3 { \pm } 6 { \mu } { \ m m }$ 表面处理PMMA 厚度约 $4 0 { \pm } 7 { \mu \mathrm { m } }$ PVA 厚度约 $1 8 \pm 6 \mathsf { u m }$ 补偿膜 厚度约 $5 2 { \pm } 7 { \mathsf { u m } }$ PSA 厚度约 $2 0 { \pm } 5 { \mathsf { u m } }$ 离型膜 厚度约 $3 8 { \pm } 5 { \mathsf { u m } }$ 注:上述之各层膜厚为参考值,实际之产品厚度以出货检验报告为准.

![](/a8cf094c1c8984ab637862af80e2df42d4397ed811b99725a1adc877e985d8d2.jpg)

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

# 3.外观规格及检验方法(Appearance Specification item & Methodology)

# 3.1偏光片本体外观规格

# 3.1.1外观不良规格及项目

<table><tr><td rowspan=24 colspan=1>外观</td><td rowspan=1 colspan=2>项目</td><td rowspan=1 colspan=1>检测方式</td><td rowspan=1 colspan=1>规格</td></tr><tr><td rowspan=6 colspan=1>保护膜表面离型层表面</td><td rowspan=1 colspan=1>刮伤</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>不伤及本体</td></tr><tr><td rowspan=1 colspan=1>打痕</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>SP 加压脱泡不可见（5KG,50℃，1min）PF不伤及本体</td></tr><tr><td rowspan=1 colspan=1>胶污</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>不可转印，不可造成二枚取</td></tr><tr><td rowspan=1 colspan=1>水雾</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>不可造成粘片</td></tr><tr><td rowspan=1 colspan=1>气泡</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>直径≤2mm</td></tr><tr><td rowspan=1 colspan=1>矢印方向</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>VA 机种斜对角双矢印</td></tr><tr><td rowspan=4 colspan=1>切断面</td><td rowspan=1 colspan=1>溢胶/残胶</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>不可有（日光灯下）</td></tr><tr><td rowspan=1 colspan=1>毛边</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>不可有</td></tr><tr><td rowspan=1 colspan=1>裁切不良</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>不可有</td></tr><tr><td rowspan=1 colspan=1>撞伤</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>不可有</td></tr><tr><td rowspan=3 colspan=1>保护膜内</td><td rowspan=1 colspan=1>点状欠点</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>直径≤0.2mm，不可伤及本体</td></tr><tr><td rowspan=1 colspan=1>线状欠点</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>长≤ 1.88mm,宽≤ 0.03mm</td></tr><tr><td rowspan=1 colspan=1>剥离&amp;浮起</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>1mm</td></tr><tr><td rowspan=7 colspan=1>基板</td><td rowspan=1 colspan=1>AG层剥离</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>有效区域不可有</td></tr><tr><td rowspan=1 colspan=1>AG层斑</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>有效区域不可有</td></tr><tr><td rowspan=1 colspan=1>气泡</td><td rowspan=1 colspan=1>目视</td><td rowspan=2 colspan=1>0.15mm&lt;Φ≤0.2mm N≤2不可有碎亮点</td></tr><tr><td rowspan=1 colspan=1>点状欠点</td><td rowspan=1 colspan=1>目视</td></tr><tr><td rowspan=1 colspan=1>线状欠点</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>W&lt;0.10mm、L&lt;1.6mm，N≤2不可有碎亮点</td></tr><tr><td rowspan=1 colspan=1>糊欠</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>有效区域不可有</td></tr><tr><td rowspan=1 colspan=1>打痕</td><td rowspan=1 colspan=1>目视</td><td rowspan=1 colspan=1>不可有</td></tr><tr><td rowspan=1 colspan=1>放置方式</td><td rowspan=1 colspan=1>-</td><td rowspan=1 colspan=1>直尺</td><td rowspan=1 colspan=1>保护膜面朝上</td></tr><tr><td rowspan=2 colspan=1>淘面</td><td rowspan=1 colspan=1>正负翘</td><td rowspan=1 colspan=1>直尺</td><td rowspan=1 colspan=1>正翘 H≤15mm，负翘 H≤10mm</td></tr><tr><td rowspan=1 colspan=1>波浪翘</td><td rowspan=1 colspan=1>直尺</td><td rowspan=1 colspan=1>3mm 以上不可有，长边≤3个，短边≤2个；≤0.5mm不计</td></tr></table>

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

无效区域：距偏光片边缘1mm ，白边 $\leqslant 0 . 2 \mathrm { m m }$ ；

异物判定方法：

![](/75104a0b48deeb07aa594d4c306180e019bec323d6d8e38bb77e2b3c6034afbf.jpg)

异物规格判定： $\Phi \mathrm { = \mathrm { ~ \left( a \mathrm { ~ + ~ } b \right) / 2 } }$ （无效区域内的不良不进行判定）

翘曲的测量方法：

所检测的样片（包含离型膜和保护膜）需如下图所示方式平坦放置，检测翘曲值 H 是否在指定范围之内,翘曲实验所用的样片必须为刚打开包装的样片,测试温度为 $2 3 { \pm } 2 ^ { \circ } \mathrm { C }$ ，测试湿度为 $6 5 \pm 1 5 \%$ 。

![](/48c2ef007ea97cffe54a85a23fa77e86a3aeab18f0ff5f58b10d0c53f4bbe1b9.jpg)  
翘曲测量方法示意图

波浪翘：

判定方法：离型面朝上，3mm 以上不可有，长边 $\leqslant 3$ 个， 短边 ${ \leqslant } 2$ 个; $\leqslant ~ 0 . ~ 5 \mathrm { { m m } }$ 不计

![](/772b6ead252b4850d0ba866ec307f744ec453e830f57fa77c719d40fc049ad54.jpg)  
波浪翘测量示意图

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

4.检验方法(Methodology)

4.1光学性质

4.1.1 试验条件

试验样本的大小及数量是随试验方法的规定而不同，偏光板在试验时，要小心拿取且不能有妨碍试验的动作。

4.1.2 单体透过率& 380nm透过率

取1枚长 $4 0 \mathrm { m m } \times$ 宽 $3 0 \mathrm { { m m } }$ 偏光板，使用积分球式分光亮度计依JIS Z 8701 2度视野XYZ系视感度补正$( 7 8 0 ^ { \sim } 3 8 0 \mathrm { n m }$ ，取每 $5 \mathrm { n m } ,$ )测定单体透过率。再取380nm波长处之透过率，即为380nm透过率。

# 4.1.3 偏光度

取2枚长 $4 0 \mathrm { m m } \times$ 宽 $3 0 \mathrm { m m } ^ { \prime }$ 偏光板，测定样本透过率，延伸轴平行时之透过率为H0，直交时为H90，偏光度(V)依下列公式求出。

$$
V = \sqrt { \frac { H _ { \circ } - H _ { \mathfrak { s o } } } { H _ { \circ } + H _ { \mathfrak { s o } } } } \times 1 0 0 \%
$$

平行透过率(H0)﹕2枚偏光板延伸轴平行方向测定。  
直交透过率(H90)﹕2枚偏光板延伸轴垂直方向测定。

4.1.4 平均倾斜角β、厚度方向Re值、配向轴角度(依厂商检查表)以原材料厂商之出货检查表提供的数值为数据。

# 4.1.5 色相

取1枚长 $4 0 \mathrm { m m } \times$ 宽 $3 0 \mathrm { { m m } }$ 偏光板，使用积分球式分光亮度计依JIS Z 8701 2度视野XYZ系视感度补正( $7 8 0  3 8 0 \ r { \mathrm { n m } }$ ，取每 $\mathrm { 5 n m } ,$ )测量色相a、b值。

# 4.1.6 雾度

依JIS K 710564项基准，使用雾度计测定。

# 4.1.7 厚度

使用厚度计测量3点，求其平均值。

4.1.8 吸收轴角度(θ1)之定义为保护膜面朝上时量测。

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

![](/bc3d65dbe2321f93a245da575b5b929e074c0741c202a759a9a0a41c45090979.jpg)  
吸收轴测量示意图

4.1.9 表面硬度

将测试样品贴于玻璃，以铅笔硬度计于 $3 0 0 \mathrm { g }$ 荷重，使用标准铅笔,以 $1 . 4 \mathrm { m m } / s$ 的速度，在试片上画出5条约1cm的线，再以橡皮擦将表面铅笔痕迹擦除，以目视观察试片上是否有刮痕，如刮痕 $\leq 3$ 条则判定为该等级之铅笔硬度合格。

# 4.1.10离型膜及保护膜剥离力

取样本 $2 5 \times 1 5 0 \ m$ ，使用拉力机以每分钟300mm速度，将样本以 $1 8 0 ^ { \circ }$ 方向剥离。

4.1.11 PSA粘着性能（glass剥离力）

取样本 $2 5 \times 1 5 0 \mathrm { m m }$ ，撕开离型膜及保护膜，贴在洗净的玻璃板上，用重 $2 \mathrm { k g } ^ { \cdot }$ 滚轮以每秒 $5 0 \mathrm { m m }$ 速度来回滚压1次，放置30分钟后，使用拉力机以每分钟300mm速度，将样本以 $1 8 0 ^ { \circ }$ 方向剥离。

# 4.1.12耐久试验(最终评估)

依品名的不同其单体透过率变化量、偏光度变化量请参照个别规格书。  
经过耐久性测试后应注意其外观变化，是否有显著的剥离、发泡、变色等其它外观。

<table><tr><td rowspan=1 colspan=2>项目</td><td rowspan=1 colspan=1>Unit</td><td rowspan=1 colspan=1>条件</td><td rowspan=1 colspan=1>CF侧</td><td rowspan=1 colspan=1>TFT侧</td></tr><tr><td rowspan=2 colspan=1>耐热性</td><td rowspan=1 colspan=1>穿透率变化</td><td rowspan=1 colspan=1>%</td><td rowspan=2 colspan=1>80°℃,500hrs</td><td rowspan=1 colspan=2>±5%</td></tr><tr><td rowspan=1 colspan=1>色度变化</td><td rowspan=1 colspan=1>二</td><td rowspan=1 colspan=2>△ab&lt;5</td></tr><tr><td rowspan=2 colspan=1>耐湿性</td><td rowspan=1 colspan=1>穿透率变化</td><td rowspan=1 colspan=1>%</td><td rowspan=2 colspan=1>60°C，90%RH,500hrs</td><td rowspan=1 colspan=2>±5%</td></tr><tr><td rowspan=1 colspan=1>色度变化</td><td rowspan=1 colspan=1>:</td><td rowspan=1 colspan=2>△ab&lt;5</td></tr><tr><td rowspan=2 colspan=1>耐寒性</td><td rowspan=1 colspan=1>穿透率变化</td><td rowspan=1 colspan=1>%</td><td rowspan=2 colspan=1>-35°C,500hrs</td><td rowspan=1 colspan=2>±5%</td></tr><tr><td rowspan=1 colspan=1>色度变化</td><td rowspan=1 colspan=1>:</td><td rowspan=1 colspan=2>△ab&lt;5</td></tr><tr><td rowspan=2 colspan=1>冷热冲击</td><td rowspan=1 colspan=1>穿透率变化</td><td rowspan=1 colspan=1>%</td><td rowspan=2 colspan=1>-35°C-70°℃,100 循环</td><td rowspan=1 colspan=2>±5%</td></tr><tr><td rowspan=1 colspan=1>色度变化</td><td rowspan=1 colspan=1>:-</td><td rowspan=1 colspan=2>△ab&lt;5</td></tr></table>

注：计算公式

$$
\Delta a b = \sqrt { \Delta a ^ { 2 } + \Delta b ^ { 2 } }
$$

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

-耐热性

取规格为 $4 0 \times 3 0 \mathrm { { m m } }$ 的样品，用滚轮将其贴附在洁净的玻璃上置于 $8 0 ^ { \circ }$ C \*5kgf/cm2 环境中 15分钟后，判定 $8 0 ^ { \circ }$ °C，500 小时的耐热性是否符合规格。

-耐湿性

取规格为 $4 0 \times 3 0 \mathrm { { m m } }$ 的样品，用滚轮将其贴附在洁净的玻璃上。置于 $5 0 ^ { \circ } \mathrm { ~ C ~ } { * 5 } \mathrm { k g f / c m 2 }$ 环境中15分钟后，判定 $6 0 ^ { \circ }$ °C ， $9 0 \% \mathrm { R H }$ ，500 小时的耐湿性是否符合规格。

-耐寒性

取规格为 $4 0 \times 3 0 \mathrm { { m m } }$ 的样品，用滚轮将其贴附在洁净的玻璃上。置于 $5 ~ 5 0 ^ { \circ } ~ \mathrm { ~ C ~ } { * } 5 \mathrm { k g f / c m 2 }$ 环境中15分钟后，判定 $- 3 5 ^ { \circ }$ °C，500 小时的耐寒性是否符合规格。

-耐冷热冲击性

取规格为 $4 0 \times 3 0 \mathrm { { m m } }$ 的样品，用滚轮将其贴附在洁净的玻璃上。置于 $5 0 ^ { \circ } \mathrm { ~ C ~ } { * 5 } \mathrm { k g f / c m 2 }$ 环境中15分钟后，判定 $- 3 5 ^ { \circ } \mathrm { ~ C ~ } ^ { \sim } 7 0 ^ { \circ } \mathrm { ~ C ~ }$ ，100个循环的耐冷热冲击性是否符合规格。

# 4.1.13 尺寸收缩率

偏光片尺寸收缩程度，取 $1 3 0 \times 2 3 0 \mathrm { m m }$ 的样本贴在干净的玻璃板上，经加压处理后，撕开保护膜，再把样本投入到 $6 0 ^ { \circ } \mathrm { C } \times 9 0 \% \mathrm { R H }$ 环境下，240小时后取出检测而得。

（\*加压处理条件： $5 0 ^ { \circ } \mathrm { C } \times 5 \mathrm { k g f } / \mathrm { c m } ^ { 2 } \times 1 5$ min）

（长 $^ +$ 宽）0hr或240hr尺寸 $=$ 2

计算公式为：尺寸收缩率 [（240hr尺寸 $- 0 \mathrm { h r }$ 尺寸）/ 0hr尺寸] $* 1 0 0 \%$

5.仕样书有效性(Guarantee term)：至异动。

6.保存条件（Storage condition）

# 6.1 保证期限

货到滁州惠科光电科技有限公司端在包装不拆的条件下尚有6个月之有效期限。

# 6.2 保存条件

6.2.1保存环境 $2 2 ^ { \circ } \mathrm { C } \pm 4 ^ { \circ } \mathrm { C }$ ， $5 5 \%$ ± $1 0 \%$ RH。

# 6.3其它注意事项：

6.3.1 偏光板具有吸湿的特性，所以容易造成翘曲之现象发生。因此偏光板需于有温湿度控制的无尘室方能将防潮袋开封，且开封后应尽快使用。  
6.3.2 因为溶剂会对粘着剂造成侵蚀、影响耐久性及外观之污染，所以对溶剂的使用须十分注意，防止对偏光板造成腐蚀。  
6.3.3 偏光板在出厂时，皆保存于固定之空调环境下，所以客户之保存环境亦应于有固定之空调环境下，若长时间置于没有空调之环境可能会造成以下之不良情形发生:(1) 偏光板PSA 面的凹凸不良。  
(2) 耐久性受到影响。  
(3) 粘着剂溢胶所造成之脏污。

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

7.包装规格

7.1 Tray盘 $^ +$ 纸箱

7.1.1包装数量

<table><tr><td rowspan=1 colspan=1>尺寸</td><td rowspan=1 colspan=1>32”</td></tr><tr><td rowspan=3 colspan=1>数量</td><td rowspan=1 colspan=1>50pcs/Tray盘</td></tr><tr><td rowspan=1 colspan=1>250pcs/箱</td></tr><tr><td rowspan=1 colspan=1>2500pcs/栈板</td></tr></table>

7.1.2 包装规格（构成和材料）

<table><tr><td rowspan=1 colspan=2>构成部件</td><td rowspan=1 colspan=1>材料</td></tr><tr><td rowspan=5 colspan=1>内包装</td><td rowspan=2 colspan=1>包装袋</td><td rowspan=1 colspan=1>32”离型膜</td></tr><tr><td rowspan=1 colspan=1>32”铝箔袋</td></tr><tr><td rowspan=1 colspan=1>保护材</td><td rowspan=1 colspan=1>32”包装垫片</td></tr><tr><td rowspan=1 colspan=1>托盘</td><td rowspan=1 colspan=1>32”Tray盘</td></tr><tr><td rowspan=1 colspan=1>粘着胶带</td><td rowspan=1 colspan=1>胶带</td></tr><tr><td rowspan=3 colspan=1>外包装</td><td rowspan=1 colspan=1>外包装箱</td><td rowspan=1 colspan=1>32”纸箱</td></tr><tr><td rowspan=1 colspan=1>粘着胶带</td><td rowspan=1 colspan=1>胶带</td></tr><tr><td rowspan=1 colspan=1>承载</td><td rowspan=1 colspan=1>55“塑胶栈板</td></tr></table>

# 7.1.3 包装规格

7.1.3.1 膜面朝向：保膜面朝上

7.1.3.2 内包装要求：

（1）包装数量：1PCS包装垫片+50PCS产品+1PCS包装垫片（2）在上层包装垫片的矢印章位置用Mark笔画圈标记。（3）使用离型膜包装后，用胶带密封（矢印章位于产品右上角）

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

# 恒美光电 Hengmei Optoelectronic

![](/3d56c4ffbe866f701d35608aaeac8e93559b9a322db027653abfd3803d8edf33.jpg)

（4）产品入铝箔袋，封口，矢印章位置位于左下角

（5）内标签张贴于矢印章位置

（6）铝箔袋多余部分先折短边，后折长边，并用胶带固定

![](/30ffcf505cba99093d1d49d8aba69723ec64767aae6e5623a9bbbe8ffff47029.jpg)

（7）将产品放入Tray盘中，并使用上Tray胶带固定

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

# 恒美光电 Hengmei Optoelectronic

![](/5e99a09cbe5165df5a0ac3c97af1e6353f030d5bf3210da86c387271cc5e49ba.jpg)  
（8）放置5个Tray盘于纸箱内，封箱

![](/25e448090bfa625f0307c6d44971e408423c3ba189602f84861d0d7d1d35249f.jpg)

# 恒美光电 Hengmei Optoelectronic

# 7.1.3.3 外包装要求：

（1）1个栈板盛2列产品，每列放5层，共10箱每栈板

![](/2fa1049a0abe44ac24631b1db255fc05e11a2a6f24e855e555612e3cd2e9ce56.jpg)

（2）外层整个使用打包带固定，缠绕膜包覆。

内外标签对应位置：

![](/a1e6434e95b06c67c4b78a66d7b0223c482c352e576e122d5cb69e5f516c15b9.jpg)

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

# 7.2 乐扣盒包装

# 7.2.1 包装数量

<table><tr><td rowspan=1 colspan=1>尺寸</td><td rowspan=1 colspan=1>32”</td></tr><tr><td rowspan=3 colspan=1>数量</td><td rowspan=1 colspan=1>250pcs/BOX</td></tr><tr><td rowspan=1 colspan=1>2列共12盒/栈板</td></tr><tr><td rowspan=1 colspan=1>3000 pcs /栈板</td></tr></table>

# 7.2.2 包装材料

<table><tr><td rowspan=1 colspan=2>构成部件</td><td rowspan=1 colspan=1>材料</td></tr><tr><td rowspan=4 colspan=1>内包装</td><td rowspan=2 colspan=1>保护材</td><td rowspan=1 colspan=1>磨边垫片</td></tr><tr><td rowspan=1 colspan=1>包装垫片</td></tr><tr><td rowspan=1 colspan=1>辅材</td><td rowspan=1 colspan=1>缓冲泡棉/干燥剂/防护挡条</td></tr><tr><td rowspan=1 colspan=1>托盘</td><td rowspan=1 colspan=1>32”乐扣盒</td></tr><tr><td rowspan=2 colspan=1>外包装</td><td rowspan=1 colspan=1>固定</td><td rowspan=1 colspan=1>打包带/缠绕膜</td></tr><tr><td rowspan=1 colspan=1>承载</td><td rowspan=1 colspan=1>1.4*1.1*0.15m塑胶栈板</td></tr></table>

# 7.2.3 包装规格

膜面朝向：保膜面朝上

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

8.个别规格书  

<table><tr><td rowspan=1 colspan=2>特性项目</td><td rowspan=1 colspan=1>单位</td><td rowspan=1 colspan=1>VW2-AGA-Z0003</td><td rowspan=1 colspan=1>VW2-Z0003</td></tr><tr><td rowspan=10 colspan=1>光学</td><td rowspan=1 colspan=1>单体透过率</td><td rowspan=1 colspan=1>%</td><td rowspan=1 colspan=1>≥42</td><td rowspan=1 colspan=1>≥42</td></tr><tr><td rowspan=1 colspan=1>垂直透过率</td><td rowspan=1 colspan=1>%</td><td rowspan=1 colspan=1>≤0.012</td><td rowspan=1 colspan=1>≤0.012</td></tr><tr><td rowspan=1 colspan=1>平行透过率</td><td rowspan=1 colspan=1>%</td><td rowspan=1 colspan=1>≥34</td><td rowspan=1 colspan=1>≥34</td></tr><tr><td rowspan=1 colspan=1>偏光度</td><td rowspan=1 colspan=1>%</td><td rowspan=1 colspan=1>≥99.99</td><td rowspan=1 colspan=1>≥99.99</td></tr><tr><td rowspan=1 colspan=1>雾度</td><td rowspan=1 colspan=1>%</td><td rowspan=1 colspan=1>2.4±2.0</td><td rowspan=1 colspan=1>-</td></tr><tr><td rowspan=1 colspan=1>色相a</td><td rowspan=1 colspan=1>NBS</td><td rowspan=1 colspan=1>-1.5±1.5</td><td rowspan=1 colspan=1>-1.5±1.5</td></tr><tr><td rowspan=1 colspan=1>色相b</td><td rowspan=1 colspan=1>NBS</td><td rowspan=1 colspan=1>3.5±1.5</td><td rowspan=1 colspan=1>3.5±1.5</td></tr><tr><td rowspan=1 colspan=1>380nm透过度</td><td rowspan=1 colspan=1>%</td><td rowspan=1 colspan=1>≤3.0</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>R0</td><td rowspan=1 colspan=1>nm</td><td rowspan=1 colspan=1>55±3.5</td><td rowspan=1 colspan=1>55±3.5</td></tr><tr><td rowspan=1 colspan=1>Rth</td><td rowspan=1 colspan=1>nm</td><td rowspan=1 colspan=1>135±7.0</td><td rowspan=1 colspan=1>135±7.0</td></tr><tr><td rowspan=13 colspan=1>物理性质</td><td rowspan=1 colspan=1>保护膜剥离力</td><td rowspan=1 colspan=1>N/25mm</td><td rowspan=1 colspan=1>≤0.2</td><td rowspan=1 colspan=1>≤0.2</td></tr><tr><td rowspan=1 colspan=1>保护膜高速剥离力30m/min</td><td rowspan=1 colspan=1>gf/25mm</td><td rowspan=1 colspan=1>≤100</td><td rowspan=1 colspan=1>≤100</td></tr><tr><td rowspan=1 colspan=1>离型膜剥离力</td><td rowspan=1 colspan=1>N/25mm</td><td rowspan=1 colspan=1>≤0.3</td><td rowspan=1 colspan=1>≤0.3</td></tr><tr><td rowspan=1 colspan=1>glass剥离力</td><td rowspan=1 colspan=1>N/25mm</td><td rowspan=1 colspan=1>&gt; 0.49</td><td rowspan=1 colspan=1>&gt; 0.49</td></tr><tr><td rowspan=1 colspan=1>保护膜撕膜带电</td><td rowspan=1 colspan=1>kV</td><td rowspan=1 colspan=1>±1.5</td><td rowspan=1 colspan=1>±1.5</td></tr><tr><td rowspan=1 colspan=1>表面阻抗 (PSA)</td><td rowspan=1 colspan=1>/□</td><td rowspan=1 colspan=1>≤1012</td><td rowspan=1 colspan=1>≤1012</td></tr><tr><td rowspan=1 colspan=1>保护膜表面阻抗</td><td rowspan=1 colspan=1>0/</td><td rowspan=1 colspan=1>106~1010</td><td rowspan=1 colspan=1>106~1010</td></tr><tr><td rowspan=1 colspan=1>尺寸收缩率</td><td rowspan=1 colspan=1>%</td><td rowspan=1 colspan=1>±3</td><td rowspan=1 colspan=1>±3</td></tr><tr><td rowspan=1 colspan=1>size (L)</td><td rowspan=1 colspan=1>mm</td><td rowspan=1 colspan=1>710.835±0.2</td><td rowspan=1 colspan=1>703.685±0.2</td></tr><tr><td rowspan=1 colspan=1>size(W)</td><td rowspan=1 colspan=1>mm</td><td rowspan=1 colspan=1>406.085±0.2</td><td rowspan=1 colspan=1>402.57±0.2</td></tr><tr><td rowspan=1 colspan=1>吸收轴角度</td><td rowspan=1 colspan=1>。</td><td rowspan=1 colspan=1>0±0.5</td><td rowspan=1 colspan=1>90±0.5</td></tr><tr><td rowspan=1 colspan=1>直角度</td><td rowspan=1 colspan=1>°</td><td rowspan=1 colspan=1>Φ=90±0.05</td><td rowspan=1 colspan=1>Φ=90±0.05</td></tr><tr><td rowspan=1 colspan=1>铅笔硬度</td><td rowspan=1 colspan=1>H</td><td rowspan=1 colspan=1>3</td><td rowspan=1 colspan=1>1</td></tr></table>

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

# 产品图面：

![](/098726b7f00895c2a22341b82a7b696f96dd57652c4af51cd1385bf5d516bb44.jpg)

HMO_(PMMA+COP) PT320AT02-5_(022)_023260&023290_简易规格书_20240628

备注：图纸仅作为料号/Mark确认，不作为规格等参考。

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

ECOA内容定义  

<table><tr><td rowspan=1 colspan=1>No.</td><td rowspan=1 colspan=1>检测维度</td><td rowspan=1 colspan=1>项目代码</td><td rowspan=1 colspan=1>检验项目</td><td rowspan=1 colspan=1>不良代码</td><td rowspan=1 colspan=1>类型</td><td rowspan=1 colspan=1>单位</td></tr><tr><td rowspan=1 colspan=1>1</td><td rowspan=1 colspan=1>寸法</td><td rowspan=1 colspan=1>POL001</td><td rowspan=1 colspan=1>宽</td><td rowspan=1 colspan=1>NGP001</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>MM</td></tr><tr><td rowspan=1 colspan=1>2</td><td rowspan=1 colspan=1>寸法</td><td rowspan=1 colspan=1>POL002</td><td rowspan=1 colspan=1>长</td><td rowspan=1 colspan=1>NGP002</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>MM</td></tr><tr><td rowspan=1 colspan=1>3</td><td rowspan=1 colspan=1>寸法</td><td rowspan=1 colspan=1>POL003</td><td rowspan=1 colspan=1>直角度</td><td rowspan=1 colspan=1>NGP003</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>：</td></tr><tr><td rowspan=1 colspan=1>4</td><td rowspan=1 colspan=1>寸法</td><td rowspan=1 colspan=1>POL004</td><td rowspan=1 colspan=1>整体厚度</td><td rowspan=1 colspan=1>NGP004</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>m</td></tr><tr><td rowspan=1 colspan=1>5</td><td rowspan=1 colspan=1>法</td><td rowspan=1 colspan=1>POL005</td><td rowspan=1 colspan=1>有效原度</td><td rowspan=1 colspan=1>NGP005</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>m</td></tr><tr><td rowspan=1 colspan=1>6</td><td rowspan=1 colspan=1>寸法</td><td rowspan=1 colspan=1>POL006</td><td rowspan=1 colspan=1>PSA原度</td><td rowspan=1 colspan=1>NGP006</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>m</td></tr><tr><td rowspan=1 colspan=1>7</td><td rowspan=1 colspan=1>寸法</td><td rowspan=1 colspan=1>POL007</td><td rowspan=1 colspan=1>正负翘</td><td rowspan=1 colspan=1>NGP007</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>MM</td></tr><tr><td rowspan=1 colspan=1>8</td><td rowspan=1 colspan=1>寸法</td><td rowspan=1 colspan=1>POL008</td><td rowspan=1 colspan=1>波浪翘</td><td rowspan=1 colspan=1>NGP008</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>9</td><td rowspan=1 colspan=1>光学</td><td rowspan=1 colspan=1>POL009</td><td rowspan=1 colspan=1>单体透过率</td><td rowspan=1 colspan=1>NGP009</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>%</td></tr><tr><td rowspan=1 colspan=1>10</td><td rowspan=1 colspan=1>光学</td><td rowspan=1 colspan=1>POL010</td><td rowspan=1 colspan=1>平行这过宰</td><td rowspan=1 colspan=1>NGP010</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>%</td></tr><tr><td rowspan=1 colspan=1>11</td><td rowspan=1 colspan=1>光学</td><td rowspan=1 colspan=1>POL011</td><td rowspan=1 colspan=1>交叉这过宰</td><td rowspan=1 colspan=1>NGP011</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>%</td></tr><tr><td rowspan=1 colspan=1>12</td><td rowspan=1 colspan=1>光学</td><td rowspan=1 colspan=1>POL012</td><td rowspan=1 colspan=1>380nm运过率</td><td rowspan=1 colspan=1>NGP012</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>%</td></tr><tr><td rowspan=1 colspan=1>13</td><td rowspan=1 colspan=1>光学</td><td rowspan=1 colspan=1>POL013</td><td rowspan=1 colspan=1>RO</td><td rowspan=1 colspan=1>NGP013</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>m</td></tr><tr><td rowspan=1 colspan=1>14</td><td rowspan=1 colspan=1>光学</td><td rowspan=1 colspan=1>POL014</td><td rowspan=1 colspan=1>Rth</td><td rowspan=1 colspan=1>NGP014</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>m</td></tr><tr><td rowspan=1 colspan=1>15</td><td rowspan=1 colspan=1>光学</td><td rowspan=1 colspan=1>POL015</td><td rowspan=1 colspan=1>皖振度</td><td rowspan=1 colspan=1>NGP015</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>%</td></tr><tr><td rowspan=1 colspan=1>16</td><td rowspan=1 colspan=1>光学</td><td rowspan=1 colspan=1>POL016</td><td rowspan=1 colspan=1>色调值</td><td rowspan=1 colspan=1>NGP016</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>NBS</td></tr><tr><td rowspan=1 colspan=1>17</td><td rowspan=1 colspan=1>光学</td><td rowspan=1 colspan=1>POL017</td><td rowspan=1 colspan=1>色调b值</td><td rowspan=1 colspan=1>NGP017</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>NBS</td></tr><tr><td rowspan=1 colspan=1>18</td><td rowspan=1 colspan=1>光学</td><td rowspan=1 colspan=1>POL018</td><td rowspan=1 colspan=1>吸收轴角度</td><td rowspan=1 colspan=1>NGP018</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>：</td></tr><tr><td rowspan=1 colspan=1>19</td><td rowspan=1 colspan=1>光学</td><td rowspan=1 colspan=1>POL019</td><td rowspan=1 colspan=1>度</td><td rowspan=1 colspan=1>NGP019</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>%</td></tr><tr><td rowspan=1 colspan=1>20</td><td rowspan=1 colspan=1>特性</td><td rowspan=1 colspan=1>POL020</td><td rowspan=1 colspan=1>3H硬度</td><td rowspan=1 colspan=1>NGP020</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>21</td><td rowspan=1 colspan=1>特性</td><td rowspan=1 colspan=1>POL021</td><td rowspan=1 colspan=1>保护膜剥离力</td><td rowspan=1 colspan=1>NGP021</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1> N25mm</td></tr><tr><td rowspan=1 colspan=1>2</td><td rowspan=1 colspan=1>特性</td><td rowspan=1 colspan=1>POL022</td><td rowspan=1 colspan=1>高速剥离力(30Mmin)</td><td rowspan=1 colspan=1>NGP022</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1> gf25mm</td></tr><tr><td rowspan=1 colspan=1>23</td><td rowspan=1 colspan=1>特性</td><td rowspan=1 colspan=1>POL023</td><td rowspan=1 colspan=1>离型膜剥离力</td><td rowspan=1 colspan=1>NGP023</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1> N/25mm</td></tr><tr><td rowspan=1 colspan=1>24</td><td rowspan=1 colspan=1>特性</td><td rowspan=1 colspan=1>POL024</td><td rowspan=1 colspan=1>对基板剥离力</td><td rowspan=1 colspan=1>NGP024</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1> N/25mm</td></tr><tr><td rowspan=1 colspan=1>25</td><td rowspan=1 colspan=1>特性</td><td rowspan=1 colspan=1>POL025</td><td rowspan=1 colspan=1>保护膜表面阻抗</td><td rowspan=1 colspan=1>NGP025</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>□</td></tr><tr><td rowspan=1 colspan=1>26</td><td rowspan=1 colspan=1>特性</td><td rowspan=1 colspan=1>POL026</td><td rowspan=1 colspan=1>PSA表面阻抗</td><td rowspan=1 colspan=1>NGP026</td><td rowspan=1 colspan=1>定量</td><td rowspan=1 colspan=1>□</td></tr><tr><td rowspan=1 colspan=1>27</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL027</td><td rowspan=1 colspan=1>片反</td><td rowspan=1 colspan=1>NGP027</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>28</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL028</td><td rowspan=1 colspan=1>粘片</td><td rowspan=1 colspan=1>NGP028</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>29</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL029</td><td rowspan=1 colspan=1>断面异常</td><td rowspan=1 colspan=1>NGP029</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>30</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL030</td><td rowspan=1 colspan=1>压点</td><td rowspan=1 colspan=1>NGP030</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>31</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL031</td><td rowspan=1 colspan=1>折伤</td><td rowspan=1 colspan=1>NGP031</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>32</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL032</td><td rowspan=1 colspan=1>缺残胶</td><td rowspan=1 colspan=1>NGP032</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>33</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL033</td><td rowspan=1 colspan=1>保离膜脏污</td><td rowspan=1 colspan=1>NGP033</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>34</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL034</td><td rowspan=1 colspan=1>保离膜气泡</td><td rowspan=1 colspan=1>NGP034</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>35</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL035</td><td rowspan=1 colspan=1>保离膜异物</td><td rowspan=1 colspan=1>NGP035</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>36</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL036</td><td rowspan=1 colspan=1>本体气泡</td><td rowspan=1 colspan=1>NGP036</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>37</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL037</td><td rowspan=1 colspan=1>本体异物</td><td rowspan=1 colspan=1>NGP037</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>38</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL038</td><td rowspan=1 colspan=1>本体划伤</td><td rowspan=1 colspan=1>NGP038</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>39</td><td rowspan=1 colspan=1>外观</td><td rowspan=1 colspan=1>POL039</td><td rowspan=1 colspan=1>其他外观不良</td><td rowspan=1 colspan=1>NGP039</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>40</td><td rowspan=1 colspan=1>包装外观</td><td rowspan=1 colspan=1>POL040</td><td rowspan=1 colspan=1>包装破损</td><td rowspan=1 colspan=1>NGP040</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>41</td><td rowspan=1 colspan=1>包装外观</td><td rowspan=1 colspan=1>POL041</td><td rowspan=1 colspan=1>标签标识</td><td rowspan=1 colspan=1>NGP041</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>42</td><td rowspan=1 colspan=1>包装外观</td><td rowspan=1 colspan=1>POL042</td><td rowspan=1 colspan=1>有效期</td><td rowspan=1 colspan=1>NGP042</td><td rowspan=1 colspan=1>定性</td><td rowspan=1 colspan=1></td></tr></table>

# 备注：以规格书签核规格判定

文件存管：本材料承认书签署 1 式两份，一份由供应商存管，一份由滁州惠科光电科技有限公司存管

# 产品GP要求:

(1) 符合《HKC绿色产品有害物质管控标准》，提供管控标准的第三方检测报告；(2) GP标签：标识为圆形/椭圆形、绿底，含有GP字样，字体宋体，黑色/白色，样式参考如下，标识大小可根据原材外箱大小调整；

![](/dcfe70876d2653db11e53f347b07c02fab7cb79b0ce5260a3117efb77ed906b4.jpg)
'''
    optimize_and_compare(markdown_text, "gpt-3.5-turbo")