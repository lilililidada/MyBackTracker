import re
from typing import Tuple, Optional

# 交易所枚举（可用中文或英文）
EXCHANGE = {
    "SSE": "上交所",
    "SZSE": "深交所",
    "BSE": "北交所",
}

# 证券类型枚举
SEC_TYPE = {
    "STOCK": "股票",
    "ETF": "ETF",
    "INDEX": "指数",
    "UNKNOWN": "未知",
}



def get_stock_exchange(code: str) -> Tuple[str, str]:
    """
    判断股票/ETF/指数代码所属交易所及证券类型

    Args:
        code (str): 代码，支持 "600000"、"159915.SZ"、"000300.SH" 等格式

    Returns:
        Tuple[str, str]: (交易所代码, 证券类型)
            - 交易所: 'SSE', 'SZSE', 'BSE', 'Unknown'
            - 类型: 'STOCK', 'ETF', 'INDEX', 'UNKNOWN'
    """
    # 提取字符串中的连续数字部分
    match = re.search(r'(\d+)', code)
    if not match:
        return "Unknown", "UNKNOWN"

    num = match.group(1)

    # ---------- 1. 判断是否为 ETF ----------
    if num.startswith('159'):
        return "SZSE", "ETF"       # 深交所ETF
    elif num.startswith('588'):
        return "SSE", "ETF"        # 上交所科创板ETF[reference:16]
    elif num.startswith(('51', '58')):
        return "SSE", "ETF"        # 上交所ETF（主板/科创板50）[reference:17][reference:18]

    # ---------- 2. 判断是否为 指数 ----------
    # 上证指数：000 开头（000001 上证指数等）[reference:19]
    if num.startswith('000'):
        return "SSE", "INDEX"

    # 深证指数：399 开头（399001 深证成指等）[reference:20]
    if num.startswith('399'):
        return "SZSE", "INDEX"

    # 中证指数：部分中证指数也用 000/399，已由上述规则覆盖
    # 若代码带 CSI/SW/CNI 前缀，可在提取数字前额外判断，见下方增强版

    # ---------- 3. 判断是否为 股票（原有逻辑） ----------
    if num.startswith(('60', '688', '900')):
        return "SSE", "STOCK"
    elif num.startswith(('000', '001', '002', '003', '200', '300')):
        return "SZSE", "STOCK"
    elif num.startswith(('8', '920')):
        return "BSE", "STOCK"
    else:
        return "Unknown", "UNKNOWN"


def get_stock_exchange_detailed(code: str) -> dict:
    """
    增强版：支持 CSI/SW/CNI 等前缀的指数识别，返回更详细的信息

    Args:
        code (str): 代码

    Returns:
        dict: {
            'exchange_code': str,   # SSE / SZSE / BSE / Unknown
            'exchange_name': str,   # 上交所 / 深交所 / 北交所 / 未知
            'sec_type': str,        # STOCK / ETF / INDEX / UNKNOWN
            'sec_type_name': str,   # 股票 / ETF / 指数 / 未知
        }
    """
    # 先尝试从纯数字前缀判断
    exchange, sec_type = get_stock_exchange(code)

    # 如果已识别出 ETF 或 INDEX，直接返回
    if sec_type in ("ETF", "INDEX"):
        pass
    else:
        # 额外检查是否带有指数公司前缀（如 CSI000300、SW801010、CNI480018）
        # 注意：这些前缀可能出现在代码开头，而非数字部分
        code_upper = code.upper()
        if code_upper.startswith("CSI"):
            # 中证指数：行情数据来源中证指数公司[reference:21][reference:22]
            # 但具体交易所取决于代码数字部分（000 为沪市，399 为深市）
            num_match = re.search(r'(\d+)', code)
            if num_match:
                num = num_match.group(1)
                if num.startswith('000'):
                    exchange = "SSE"
                elif num.startswith('399'):
                    exchange = "SZSE"
                else:
                    exchange = "Unknown"
            sec_type = "INDEX"
        elif code_upper.startswith("SW"):
            # 申万指数[reference:23]
            sec_type = "INDEX"
            # 申万指数无固定交易所归属，保留原 exchange 或设为 Unknown
            exchange = "Unknown"
        elif code_upper.startswith("CNI"):
            # 国证指数[reference:24]
            sec_type = "INDEX"
            exchange = "Unknown"

    # 映射为中文名称
    exchange_name = {
        "SSE": "上交所",
        "SZSE": "深交所",
        "BSE": "北交所",
        "Unknown": "未知"
    }.get(exchange, "未知")

    sec_type_name = {
        "STOCK": "股票",
        "ETF": "ETF",
        "INDEX": "指数",
        "UNKNOWN": "未知"
    }.get(sec_type, "未知")

    return {
        "exchange_code": exchange,
        "exchange_name": exchange_name,
        "sec_type": sec_type,
        "sec_type_name": sec_type_name,
    }


# ---------- 使用示例 ----------
if __name__ == "__main__":
    test_codes = [
        # 股票
        ("600519", "贵州茅台"),
        ("000001", "平安银行"),
        ("300750", "宁德时代"),
        ("688001", "华兴源创"),
        ("870001", "北交所股票"),

        # ETF
        ("159915", "创业板ETF"),          # 深交所
        ("159825", "农业ETF"),            # 深交所[reference:26]
        ("510050", "上证50ETF"),          # 上交所[reference:27]
        ("588000", "科创板50ETF"),        # 上交所科创板[reference:28]
        ("513100", "纳指ETF"),            # 上交所[reference:29]

        # 指数
        ("000001", "上证指数"),            # 上交所[reference:30]
        ("399001", "深证成指"),            # 深交所[reference:31]
        ("000300", "沪深300(沪)"),         # 上交所[reference:32]
        ("399300", "沪深300(深)"),         # 深交所[reference:33]
        ("CSI000300", "中证沪深300"),      # 中证指数[reference:34]
        ("SW801010", "申万农林牧渔"),      # 申万指数[reference:35]

        # 带后缀
        ("159915.SZ", "带后缀的ETF"),
        ("000300.SH", "带后缀的指数"),

        # 无效
        ("ABC", "无效输入"),
    ]

    print(f"{'代码':<14} {'名称':<12} {'交易所':<8} {'类型':<6}")
    print("-" * 48)
    for code, name in test_codes:
        result = get_stock_exchange_detailed(code)
        print(f"{code:<14} {name:<12} {result['exchange_name']:<8} {result['sec_type_name']:<6}")